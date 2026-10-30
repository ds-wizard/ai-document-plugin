"""Stands in for both external systems the service talks to: the DSW API and an OpenAI-compatible LLM.

Everything it returns is deterministic and independent of how the questions were chunked, so the two
token counters only differ in chunk boundaries, never in the content of the assignments.
"""

import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

QUESTIONNAIRE_RE = re.compile(r'^/wizard-api/projects/[^/]+/questionnaire$')
VERSIONS_RE = re.compile(r'^/wizard-api/projects/[^/]+/versions$')
QUESTION_ID_RE = re.compile(r'<question id="(\d+)">')
LEAF_SECTION_RE = re.compile(r'<section id="([A-Z]+)">')

ITEM_UUID = '22222222-2222-4222-8222-222222222222'
PACKAGE_UUID = '33333333-3333-4333-8333-333333333333'
SECTION_TEXT = ('This section summarises the answers given in the questionnaire. ' * 25).strip()


def _add_question_replies(km: dict, question_uuid: str, path: str, replies: dict) -> None:
    """Answer one question, following the first answer of options questions and one item of list questions."""
    entities = km['entities']
    question = entities['questions'][question_uuid]
    question_type = question.get('questionType')

    if question_type == 'ValueQuestion':
        replies[path] = {'value': {'type': 'StringReply', 'value': f'Sample answer to: {question["title"]}'}}
    elif question_type == 'OptionsQuestion':
        answer_uuids = question.get('answerUuids', [])
        if not answer_uuids:
            return
        answer_uuid = answer_uuids[0]
        replies[path] = {'value': {'type': 'AnswerReply', 'value': answer_uuid}}
        for follow_up_uuid in entities['answers'][answer_uuid].get('followUpUuids', []):
            _add_question_replies(km, follow_up_uuid, f'{path}.{answer_uuid}.{follow_up_uuid}', replies)
    elif question_type == 'ListQuestion':
        replies[path] = {'value': {'type': 'ItemListReply', 'value': [ITEM_UUID]}}
        for nested_uuid in question.get('itemTemplateQuestionUuids', []):
            _add_question_replies(km, nested_uuid, f'{path}.{ITEM_UUID}.{nested_uuid}', replies)


def build_questionnaire(km: dict) -> dict:
    replies: dict = {}
    for chapter_uuid in km['chapterUuids']:
        for question_uuid in km['entities']['chapters'][chapter_uuid].get('questionUuids', []):
            _add_question_replies(km, question_uuid, f'{chapter_uuid}.{question_uuid}', replies)
    return {
        'name': 'RAM benchmark project',
        'language': 'en',
        'knowledgeModel': km,
        'knowledgeModelPackage': {'uuid': PACKAGE_UUID, 'name': 'Benchmark KM', 'version': '1.0.0'},
        'replies': replies,
    }


def assignment_response(user_message: str) -> str:
    """Map each question to one leaf section, chosen only by the question's id."""
    sections = LEAF_SECTION_RE.findall(user_message)
    question_ids = QUESTION_ID_RE.findall(user_message)
    return json.dumps({qid: [sections[int(qid) % len(sections)]] for qid in question_ids})


class Upstream:
    def __init__(self, km_path: Path, llm_delay: float) -> None:
        self.questionnaire = json.dumps(build_questionnaire(json.loads(km_path.read_text()))).encode()
        self.llm_delay = llm_delay
        self.lock = threading.Lock()
        self.calls = {'assignment': 0, 'generation': 0, 'polishing': 0}

    def count(self, kind: str) -> None:
        with self.lock:
            self.calls[kind] += 1

    def reset(self) -> None:
        with self.lock:
            self.calls = dict.fromkeys(self.calls, 0)

    def completion(self, messages: list[dict]) -> str:
        system_message = messages[0]['content']
        user_message = messages[-1]['content']
        time.sleep(self.llm_delay)
        if '<sections>' in user_message:
            self.count('assignment')
            return assignment_response(user_message)
        if system_message.startswith('You are a data management plan writer'):
            self.count('generation')
            return SECTION_TEXT
        self.count('polishing')
        return user_message


def make_handler(upstream: Upstream) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

        def _send(self, body: bytes, status: int = 200) -> None:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: object, status: int = 200) -> None:
            self._send(json.dumps(payload).encode(), status)

        def do_GET(self) -> None:
            if self.path == '/health':
                self._send_json({'status': 'ok'})
            elif self.path == '/stats':
                self._send_json(upstream.calls)
            elif self.path == '/wizard-api/users/current':
                self._send_json({'role': 'admin'})
            elif QUESTIONNAIRE_RE.match(self.path):
                self._send(upstream.questionnaire)
            elif VERSIONS_RE.match(self.path):
                self._send_json([])
            else:
                self._send_json({'detail': f'Unknown path {self.path}'}, 404)

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            if self.path == '/reset':
                upstream.reset()
                self._send_json({})
            elif self.path == '/v1/chat/completions':
                request = json.loads(body)
                content = upstream.completion(request['messages'])
                self._send_json(
                    {
                        'id': 'chatcmpl-benchmark',
                        'object': 'chat.completion',
                        'created': int(time.time()),
                        'model': request.get('model', 'fake'),
                        'choices': [
                            {
                                'index': 0,
                                'finish_reason': 'stop',
                                'message': {'role': 'assistant', 'content': content},
                            }
                        ],
                        'usage': {
                            'prompt_tokens': len(body) // 4,
                            'completion_tokens': len(content) // 4,
                            'total_tokens': (len(body) + len(content)) // 4,
                        },
                    }
                )
            else:
                self._send_json({'detail': f'Unknown path {self.path}'}, 404)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--km', type=Path, default=Path('/bench/km.json'))
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--llm-delay', type=float, default=0.3, help='Seconds each fake LLM call takes.')
    args = parser.parse_args()

    upstream = Upstream(args.km, args.llm_delay)
    ThreadingHTTPServer(('0.0.0.0', args.port), make_handler(upstream)).serve_forever()


if __name__ == '__main__':
    main()
