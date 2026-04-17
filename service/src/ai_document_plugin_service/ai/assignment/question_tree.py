from typing import Any
from xml.sax.saxutils import escape

from ai_document_plugin_service.ai.assignment.tree_chunker import TreeChunker
from ai_document_plugin_service.ai.knowledgemodel.direct_subquestion_visitor import (
    DirectSubquestionVisitor,
)
from ai_document_plugin_service.ai.knowledgemodel.types import (
    BlankQuestion,
    Chapter,
    QuestionData,
)


def build_question_chunks(
    top_level_questions: list[QuestionData],
    max_chunk_tokens: int = 500,
) -> tuple[list[str], dict[str, str]]:
    """Convert questionnaire data into chunked XML prompts for assignment matching.

    The function builds a question tree from the provided top-level questions, assigns
    string IDs to leaf questions to make it easier for LLMs to process (compared to question path from DSW), and chunks the resulting tree by token budget.

    Args:
        top_level_questions: Parsed KM chapter-level questions.
        max_chunk_tokens: Approximate per-chunk token budget used by `TreeChunker`.

    Returns:
        A tuple of:
        - `chunk_xml`: XML snippets where each item is one question-tree chunk.
        - `question_id_to_path`: Mapping from generated leaf question IDs to KM paths.

    """
    root = BlankQuestion(top_level_questions)
    child_questions = root.accept(DirectSubquestionVisitor()) or []

    question_id_to_path: dict[str, str] = {}
    xml_nodes = [
        _question_to_xml_node(question, question_id_to_path)
        for question in child_questions
    ]
    tree_root = {'tag': 'root', 'children': xml_nodes}

    chunker = TreeChunker(tree_root, max_tokens=max_chunk_tokens)
    chunks = chunker.chunk()
    chunk_xml: list[str] = []
    for chunk in chunks:
        parts: list[str] = []
        for chunk_root in chunk:
            parts.extend(
                _xml_node_to_string(child) for child in chunk_root['children']
            )
        chunk_xml.append('\n'.join(parts))

    return chunk_xml, question_id_to_path


def _question_to_xml_node(
    question: QuestionData,
    question_id_to_path: dict[str, str],
) -> dict[str, Any]:
    """Recursively convert a `QuestionData` node into an XML-ready dictionary.

    Leaf questions become `<question id="...">` nodes and are registered in
    `question_id_to_path`; non-leaf nodes become `<chapter>` or `<section>`
    containers based on runtime type.
    """
    child_questions = question.accept(DirectSubquestionVisitor()) or []
    title = question.title or ''
    text = question.text

    if not child_questions:
        question_id = str(len(question_id_to_path) + 1)
        question_id_to_path[question_id] = question.path
        node = {'tag': 'question', 'id': question_id, 'title': title}
        if text:
            node['text'] = text
        return node

    tag = 'chapter' if isinstance(question, Chapter) else 'section'
    node: dict[str, Any] = {
        'tag': tag,
        'title': title,
        'children': [
            _question_to_xml_node(child, question_id_to_path)
            for child in child_questions
        ],
    }
    if text:
        node['text'] = text
    return node


def _xml_node_to_string(node: dict[str, Any]) -> str:
    """Serialize an XML-node dictionary into an escaped XML string.

    Supported fields:
    - `tag` (required)
    - `id` (used only for question tags)
    - `title`
    - `text` (serialized as `<context>`)
    - `children` (recursive)
    """
    tag = node['tag']
    title = node.get('title', '')
    text = node.get('text')
    children = node.get('children', [])
    attrs = (
        f' id="{escape(str(node["id"]))}"'
        if tag == 'question' and 'id' in node
        else ''
    )

    parts = [f'<{tag}{attrs}>']
    if title:
        parts.append(f'<title>{escape(title)}</title>')
    if text:
        parts.append(f'<context>{escape(text)}</context>')
    parts.extend(_xml_node_to_string(child) for child in children)
    parts.append(f'</{tag}>')
    return '\n'.join(parts)
