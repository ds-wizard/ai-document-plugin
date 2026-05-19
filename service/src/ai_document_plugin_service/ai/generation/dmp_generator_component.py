import logging
import math
import re
from collections.abc import Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, TypedDict

import pandas as pd
from haystack import component
from tqdm import tqdm

from ai_document_plugin_service.ai.assignment.types import SerializedSectionAssignment
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.generation.llm import (
    GenerationLLM,
    OpenAIGenerationLLM,
)
from ai_document_plugin_service.ai.generation.parse_answers import parse_answer

logger = logging.getLogger(__name__)

# From this depth, include all neighbouring replies at level in prompt (not just those in questions)
DEPTH_INCLUDE_ALL_ANSWERS = 2


class DmpGeneratorComponentResult(TypedDict):
    markdown: str
    debug_markdown: str
    stats: AssignmentStats


@dataclass
class _ScheduledSection:
    heading: str
    future: Future[tuple[str, str]] | None = None
    children: list['_ScheduledSection'] = field(default_factory=list)
    no_data: bool = False


@component
class DmpGeneratorComponent:
    @component.output_types(markdown=str, debug_markdown=str, stats=AssignmentStats)
    def run(
        self,
        replies: dict,
        km: dict,
        llm: GenerationLLM | None = None,
        workers: int = 1,
        new_assignments: list[SerializedSectionAssignment] | None = None,
        db_assignments: list[SerializedSectionAssignment] | None = None,
    ) -> DmpGeneratorComponentResult:
        """Generate full DMP markdown from nested assignments tree.

        Returns (markdown, debug_markdown, stats). Use markdown for the polished DMP;
        debug_markdown includes source-question tables for debugging.
        """
        logger.debug('Step 2: Generating DMP markdown...')
        assignments = db_assignments or new_assignments or []
        replies = self._filter_reachable_replies(replies, km)

        stats = AssignmentStats()

        if llm is None:
            llm = OpenAIGenerationLLM()

        worker_count = max(1, workers)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            scheduled_sections = [
                self._schedule_section(
                    node=node,
                    depth=0,
                    replies=replies,
                    km=km,
                    llm=llm,
                    stats=stats,
                    executor=executor,
                )
                for node in assignments
            ]
            leaf_futures = []
            for scheduled in scheduled_sections:
                leaf_futures.extend(self._collect_leaf_futures(scheduled))
            for _ in tqdm(
                as_completed(leaf_futures),
                total=len(leaf_futures),
                desc=f'Generating sections ({worker_count} workers)',
            ):
                pass
            parts = [self._render_scheduled_section(scheduled) for scheduled in scheduled_sections]
        markdown = '\n\n'.join([s for s, _ in parts])
        debug_markdown = '\n\n'.join([d for _, d in parts])
        return {
            'markdown': markdown,
            'debug_markdown': debug_markdown,
            'stats': stats,
        }

    @staticmethod
    def _filter_reachable_replies(
        replies: dict[str, Any],
        km: dict[str, Any],
    ) -> dict[str, Any]:
        """Keep only replies that are reachable in the current questionnaire state.

        DSW can keep stale descendants in the raw questionnaire JSON when a user
        changes an earlier answer (for example `YES -> NO`) or removes a list
        item. Generation should ignore those historical branches and only use
        replies that can be reached from the current KM roots via the currently
        selected option answers and existing list-item UUIDs.
        """
        chapter_uuids = km.get('chapterUuids')
        entities = km.get('entities', {})
        chapters = entities.get('chapters', {})
        questions = entities.get('questions', {})
        answers = entities.get('answers', {})
        if not chapter_uuids or not chapters or not questions:
            return replies

        reachable_paths: set[str] = set()

        for chapter_uuid in chapter_uuids:
            chapter = chapters.get(chapter_uuid)
            if chapter is None:
                continue
            for question_uuid in chapter.get('questionUuids', []):
                DmpGeneratorComponent._walk_reachable_question(
                    question_uuid,
                    f'{chapter_uuid}.{question_uuid}',
                    replies,
                    questions,
                    answers,
                    reachable_paths,
                )

        return {key: value for key, value in replies.items() if key in reachable_paths}

    @staticmethod
    def _walk_reachable_options_question(
        path: str,
        replies: dict[str, Any],
        answers: dict[str, Any],
    ) -> list[tuple[str, str]]:
        selected_answer_uuid = replies.get(path, {}).get('value', {}).get('value')
        if not selected_answer_uuid:
            return []

        answer = answers.get(selected_answer_uuid)
        if answer is None:
            return []

        return [
            (
                follow_up_uuid,
                f'{path}.{selected_answer_uuid}.{follow_up_uuid}',
            )
            for follow_up_uuid in answer.get('followUpUuids', [])
        ]

    @staticmethod
    def _walk_reachable_list_question(
        question: dict[str, Any],
        path: str,
        replies: dict[str, Any],
    ) -> list[tuple[str, str]]:
        list_items = replies.get(path, {}).get('value', {}).get('value', [])
        if not isinstance(list_items, list):
            logger.warning('Expected list items at %s, got %s', path, type(list_items).__name__)
            return []

        return [
            (
                nested_question_uuid,
                f'{path}.{item_uuid}.{nested_question_uuid}',
            )
            for item_uuid in list_items
            for nested_question_uuid in question.get('itemTemplateQuestionUuids', [])
        ]

    @staticmethod
    def _walk_reachable_question(
        question_uuid: str,
        path: str,
        replies: dict[str, Any],
        questions: dict[str, Any],
        answers: dict[str, Any],
        reachable_paths: set[str],
    ) -> None:
        question = questions.get(question_uuid)
        if question is None:
            return

        if path in replies:
            reachable_paths.add(path)

        question_type = question.get('questionType')
        if question_type == 'OptionsQuestion':
            child_questions = DmpGeneratorComponent._walk_reachable_options_question(
                path,
                replies,
                answers,
            )
        elif question_type == 'ListQuestion':
            child_questions = DmpGeneratorComponent._walk_reachable_list_question(
                question,
                path,
                replies,
            )
        else:
            child_questions = []

        for child_question_uuid, child_path in child_questions:
            DmpGeneratorComponent._walk_reachable_question(
                child_question_uuid,
                child_path,
                replies,
                questions,
                answers,
                reachable_paths,
            )

    @staticmethod
    def _get_reply_keys_at_level(replies: dict[str, Any], prefix: str) -> list[str]:
        """Return reply keys that are prefix + exactly one more segment (neighbouring replies)."""
        if not prefix:
            return [k for k in replies if '.' not in k]
        prefix_dot = prefix + '.'
        expected_dots = prefix.count('.') + 1
        return [k for k in replies if k.startswith(prefix_dot) and k.count('.') == expected_dots]

    @staticmethod
    def get_wildcard_uuids(template: str, paths: Iterable[str]) -> list[str]:
        """Extract the UUIDs that fill each ``*`` wildcard in *template* by matching against *paths*."""
        pattern = '^' + re.escape(template).replace(r'\*', r'([^.]+)') + '$'

        uuids = []
        for path in paths:
            match = re.match(pattern, path)
            if match:
                # Extract the content of the capturing group (what replaced the *)
                uuids.append(match.group(1))

        return uuids

    @staticmethod
    def is_multianswer_question(path: str) -> bool:
        """Checks if the current path contains *."""
        return '*' in path

    @staticmethod
    def get_question_path(question: dict[str, Any], override_uuids: list[str]) -> str:
        """Gets question_path from question, overrides wildcards with uuids."""
        path = question['question_path']
        for replacement in override_uuids:
            path = re.sub(r'\*', replacement, path, count=1)
        return path

    def match_replies_selection(
        self,
        questions: dict[str, Any],
        replies: dict[str, Any],
        km: dict[str, Any],
        depth: int = 0,
        override_uuids: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Recursively match questionnaire replies to the assigned question tree.

        The assignment tree stores question paths with ``*`` wildcards for list
        (ItemListReply) questions — e.g. ``ch.listQ.*.itemQ``.  The *replies* dict
        uses fully-resolved paths with concrete UUIDs — e.g.
        ``ch.listQ.uuid1.itemQ``.  This function bridges the two representations
        by progressively replacing each ``*`` with every UUID that appears in
        *replies*, then looking up the actual reply value.

        Args:
            questions: Dict of assigned question items keyed by question UUID.
                Each item has ``question_path`` (may contain ``*``), ``children``
                (nested dict of the same shape), and metadata.
            replies: Flat dict of all questionnaire replies keyed by
                fully-resolved path (no wildcards).
            km: Knowledge-model dict (``knowledgeModel`` from the DSW export).
            depth: Current recursion depth (0 = top-level assigned questions).
            override_uuids: Accumulated list of concrete UUIDs that replace
                successive ``*`` wildcards as we recurse into list questions.

        Returns:
            ``(matched_items, has_answer)`` — *matched_items* is a list of dicts,
            each either ``type: "question"`` (with ``reply``, ``children``, etc.)
            or ``type: "wrapper"`` (grouping one list-item's children).
            *has_answer* is True when at least one reply was found anywhere in the
            subtree.

        Dispatch logic:
            If the (partially resolved) path of the first question still contains
            a ``*``, all questions at this level are list questions and we call
            ``handle_multi_replies``.  Otherwise we call ``handle_single_reply``.

        """
        if override_uuids is None:
            override_uuids = []
        if len(questions) == 0:
            return [], False
        if self.is_multianswer_question(
            self.get_question_path(next(iter(questions.values())), override_uuids),
        ):
            return self.handle_multi_replies(
                questions,
                replies,
                km,
                depth,
                override_uuids,
            )
        return self.handle_single_reply(
            questions,
            replies,
            km,
            depth,
            override_uuids,
        )

    def handle_multi_replies(
        self,
        questions: dict[str, Any],
        replies: dict[str, Any],
        km: dict[str, Any],
        depth: int,
        override_uuids: list[str],
    ) -> tuple[list[dict[str, Any]], bool]:
        """Handle list (ItemListReply) questions whose path still contains a ``*``.

        A list question lets the user create multiple items (e.g. "add another
        dataset").  In the reply paths the ``*`` is replaced by the item's UUID,
        so the same question template appears once per item::

            template path:  ch.datasets.*.datasetName
            reply paths:    ch.datasets.uuid1.datasetName
                            ch.datasets.uuid2.datasetName

        This function finds every UUID that fills the next ``*`` by scanning
        *replies* keys, then recursively calls ``match_replies_selection`` for
        each UUID (appending it to *override_uuids* so the ``*`` is resolved).
        Each UUID's results are wrapped in a ``type: "wrapper"`` dict that groups
        that item's children together.  Items without any answered children are
        silently dropped.
        """
        result_items = []
        has_answer = False
        for uuid in self.get_wildcard_uuids(
            self.get_question_path(next(iter(questions.values())), override_uuids),
            replies.keys(),
        ):
            children, child_has_answer = self.match_replies_selection(
                questions,
                replies,
                km,
                depth + 1,
                [*override_uuids, uuid],
            )
            if not child_has_answer:
                continue
            result_items.append(
                {
                    'question_path': None,
                    'question_title': None,
                    'status': None,
                    'type': 'wrapper',
                    'children': children,
                },
            )
            has_answer = True
        return result_items, has_answer

    def handle_single_reply(
        self,
        questions: dict[str, Any],
        replies: dict[str, Any],
        km: dict[str, Any],
        depth: int,
        override_uuids: list[str],
    ) -> tuple[list[dict[str, Any]], bool]:
        """Handle questions whose path is fully resolved (no remaining ``*``).

        Iterates over each assigned question at this level, resolves its path,
        looks up the reply in *replies*, and recurses into its children.  A
        question is included in the output only if it has a direct reply **or**
        at least one answered child.

        Neighbouring-reply enrichment (depth >= ``DEPTH_INCLUDE_ALL_ANSWERS``):
            At deeper levels the assignment may not have explicitly listed every
            sibling question, but their replies can still provide useful context
            for the LLM.  When ``depth >= 2`` this function scans *replies* for
            any keys at the same path level (same parent prefix, one more
            segment) that weren't already covered by the assigned questions.
            For each such "neighbouring" reply a synthetic question item is
            created from the knowledge model and appended to the result.
        """
        result_items = []
        has_answer = False
        question_paths_covered: set[str] = set()

        for item in questions.values():
            question_path = self.get_question_path(item, override_uuids)
            question_paths_covered.add(question_path)
            res, child_has_answer = self._build_single_question_result(
                item=item,
                question_path=question_path,
                replies=replies,
                km=km,
                depth=depth,
                override_uuids=override_uuids,
            )
            reply_has_answer = res.get('reply') is not None
            if reply_has_answer or child_has_answer:
                result_items.append(res)
                has_answer = True

        # From depth 2: include all neighbouring replies (parent path + any uuid)
        if depth >= DEPTH_INCLUDE_ALL_ANSWERS:
            synthetic_items = self._collect_neighbouring_reply_items(
                questions=questions,
                replies=replies,
                km=km,
                override_uuids=override_uuids,
                question_paths_covered=question_paths_covered,
            )
            if synthetic_items:
                result_items.extend(synthetic_items)
                has_answer = True

        return result_items, has_answer

    def _build_single_question_result(
        self,
        item: dict[str, Any],
        question_path: str,
        replies: dict[str, Any],
        km: dict[str, Any],
        depth: int,
        override_uuids: list[str],
    ) -> tuple[dict[str, Any], bool]:
        """Build a result dict for one question and recurse into children.

        Raises:
            RuntimeError: If a multi-answer question appears in a single-answer branch.
        """
        res = {
            'question_path': question_path,
            'question_title': item['question_title'],
            'question_text': item['question_text'],
            'include': item.get('include'),
            'type': 'question',
        }
        if self.is_multianswer_question(question_path):
            msg = 'There is multianswer question among non-multianswer questions at path'
            raise RuntimeError(
                msg,
                question_path,
            )
        if question_path in replies:
            res['reply'] = parse_answer(
                replies[question_path]['value'],
                km,
                replies=replies,
                question_path=question_path,
            )
        children, child_has_answer = self.match_replies_selection(
            item['children'],
            replies,
            km,
            depth + 1,
            override_uuids,
        )
        res['children'] = children
        return res, child_has_answer

    def _get_neighbour_prefix(
        self,
        questions: dict[str, Any],
        override_uuids: list[str],
    ) -> str:
        """Derive the dot-separated parent prefix shared by all questions at this level."""
        first_q = next(iter(questions.values()))
        first_path = self.get_question_path(first_q, override_uuids)
        if '.' in first_path:
            return first_path.rsplit('.', 1)[0]
        if override_uuids:
            return '.'.join(override_uuids)
        return ''

    def _collect_neighbouring_reply_items(
        self,
        questions: dict[str, Any],
        replies: dict[str, Any],
        km: dict[str, Any],
        override_uuids: list[str],
        question_paths_covered: set[str],
    ) -> list[dict[str, Any]]:
        """Create synthetic items for replies at the same level not explicitly assigned."""
        prefix = self._get_neighbour_prefix(questions, override_uuids)
        keys_at_level = self._get_reply_keys_at_level(replies, prefix)
        synthetic_items = []
        for key in keys_at_level:
            if key in question_paths_covered:
                continue
            synthetic = self._build_synthetic_question_item(key, replies, km)
            if synthetic is not None:
                synthetic_items.append(synthetic)
        return synthetic_items

    @staticmethod
    def _build_synthetic_question_item(
        key: str,
        replies: dict,
        km: dict,
    ) -> dict | None:
        """Create a question-result dict for a reply that was not part of the original assignment.

        Returns ``None`` if the reply is empty, unparseable, or the question UUID
        is missing from the knowledge model.
        """
        try:
            parsed = parse_answer(
                replies[key]['value'],
                km,
                replies=replies,
                question_path=key,
            )
        except (KeyError, TypeError):
            return None
        if parsed is None or (isinstance(parsed, str) and not parsed.strip()):
            return None
        km_questions = km['entities']['questions']
        question_uuid = key.rsplit('.', maxsplit=1)[-1]
        if question_uuid not in km_questions:
            logger.debug(
                'Question %s from %s not found in the KM',
                question_uuid,
                key,
            )
            return None
        question = km_questions[question_uuid]
        return {
            'question_path': key,
            'question_title': question['title'],
            'question_text': question['text'],
            'include': None,
            'type': 'question',
            'debug-info': 'Question added because of being on same level as selected question',
            'reply': parsed,
            'children': [],
        }

    @staticmethod
    def sanitize(text: str | None) -> str | None:
        """Replace newlines with spaces, pass through ``None`` unchanged."""
        if text is None:
            return None
        return text.replace('\n', ' ')

    @staticmethod
    def _sanitize_table_cell(text: object | None) -> str:
        """Sanitize text for use in a markdown table cell (avoid breaking rows/columns)."""
        if text is None:
            return ''
        if isinstance(text, float) and math.isnan(text):
            return ''
        s = str(text)
        s = s.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        s = s.replace('|', '&#124;')  # pipe would break column
        return s.strip()

    def construct_chapter_prompt(
        self,
        chapter_name: str,
        replies: list[dict[str, Any]],
    ) -> str | None:
        """Build the LLM user prompt for one section from its matched question/answer tree.

        Returns ``None`` when there are no replies to include.
        """
        if len(replies) == 0:
            return None

        def construct_question_answers(question: dict[str, Any], level: int) -> str:
            if question['type'] == 'wrapper':
                groups = [construct_question_answers(q, level + 1) for q in question['children']]
                return '\t' * level + 'SUBQUESTIONS GROUP: \n' + ''.join(groups)
            result = ('\t' * level) + ' - Question: ' + (self.sanitize(question['question_title']) or '') + '\n'
            if question.get('reply') is not None:
                result += ('\t' * level) + '   Answer: ' + question['reply'] + '\n'
            for child in question['children']:
                result += construct_question_answers(child, level + 1)
            return result

        system_prompt = 'Chapter name: ' + chapter_name + '\n'
        system_prompt += 'Questions and answers: \n'
        qs = [construct_question_answers(q, 0) for q in replies]
        return system_prompt + '\n'.join(qs) + '\n'

    @staticmethod
    def llm_section_from_qa(
        llm: GenerationLLM,
        prompt: str,
        stats: AssignmentStats | None = None,
        previously_generated: str = '',
    ) -> str:
        """Generate DMP section content from questions and answers."""
        return llm.section_from_qa(
            prompt=prompt,
            stats=stats,
            previously_generated=previously_generated,
        )

    @staticmethod
    def _heading(depth: int, title: str) -> str:
        """Markdown heading with # count based on depth (depth 0 -> #, depth 1 -> ##, ...)."""
        return '#' * (depth + 1) + ' ' + title

    def _flatten_matched_questions(
        self,
        matches: list[dict],
        section_key: str,
    ) -> list[dict]:
        """Extract all leaf questions from match_replies_selection result for one section."""
        rows = []

        def walk(items: list[dict[str, Any]]) -> None:
            for item in items:
                if item.get('type') == 'wrapper':
                    walk(item.get('children', []))
                elif item.get('type') == 'question':
                    reply = item.get('reply')
                    rows.append(
                        {
                            'section': section_key,
                            'question_path': item.get('question_path') or '',
                            'question_title': self.sanitize(item.get('question_title')) or '',
                            'question_text': self.sanitize(item.get('question_text')) or '',
                            'has_reply': reply is not None,
                            'reply': reply or '',
                        },
                    )
                    walk(item.get('children', []))

        walk(matches)
        return rows

    def _source_questions_table(self, rows: list[dict]) -> str:
        """Format source-question rows as a markdown table for debugging."""
        if not rows:
            return ''
        df = pd.DataFrame(rows)
        df = df.loc[df['has_reply']].copy()
        if df.empty:
            return ''
        df = df[['question_path', 'question_title', 'question_text', 'reply']]
        for col in df.columns:
            df[col] = df[col].apply(self._sanitize_table_cell)
        # Make path column visually small but still copyable
        df['question_path'] = '<span style="font-size: 0.65em">' + df['question_path'].astype(str) + '</span>'
        df = df.rename(
            columns={
                'question_path': 'Question path',
                'question_title': 'Question title',
                'question_text': 'Question text',
                'reply': 'Reply',
            },
        )
        table_md = df.to_markdown(index=False)
        return '<details>\n<summary>Source questions</summary>\n\n' + table_md + '\n\n</details>'

    def _schedule_section(
        self,
        node: SerializedSectionAssignment,
        depth: int,
        replies: dict,
        km: dict,
        llm: GenerationLLM,
        executor: ThreadPoolExecutor,
        stats: AssignmentStats | None = None,
    ) -> _ScheduledSection:
        """Recursively schedule leaf-section jobs using a shared executor."""
        title = node['title']
        heading = self._heading(depth, title)

        if self._is_leaf_section(node):
            return self._handle_leaf_section(executor, heading, km, llm, node, replies, stats)
        return self._handle_children_section(depth, executor, heading, km, llm, node, replies, stats)

    def _handle_children_section(
        self,
        depth: int,
        executor: ThreadPoolExecutor,
        heading: str,
        km: dict,
        llm: GenerationLLM,
        node: SerializedSectionAssignment,
        replies: dict,
        stats: AssignmentStats | None,
    ) -> _ScheduledSection:
        return _ScheduledSection(
            heading=heading,
            children=[
                self._schedule_section(
                    node=child,
                    depth=depth + 1,
                    replies=replies,
                    km=km,
                    llm=llm,
                    stats=stats,
                    executor=executor,
                )
                for child in (node.get('children') or [])
            ],
        )

    def _handle_leaf_section(
        self,
        executor: ThreadPoolExecutor,
        heading: str,
        km: dict,
        llm: GenerationLLM,
        node: SerializedSectionAssignment,
        replies: dict,
        stats: AssignmentStats | None,
    ) -> _ScheduledSection:
        if node.get('assignments') is not None:
            return _ScheduledSection(
                heading=heading,
                future=executor.submit(
                    self._generate_leaf_section,
                    node,
                    heading,
                    replies,
                    km,
                    llm,
                    stats,
                ),
            )
        return _ScheduledSection(heading=heading, no_data=True)

    @staticmethod
    def _is_leaf_section(node: SerializedSectionAssignment) -> bool:
        return not node.get('children')

    def _generate_leaf_section(
        self,
        node: SerializedSectionAssignment,
        heading: str,
        replies: dict,
        km: dict,
        llm: GenerationLLM,
        stats: AssignmentStats | None = None,
    ) -> tuple[str, str]:
        """Generate markdown/debug markdown for a leaf node with assignments.

        Raises:
            ValueError: If a leaf section is missing its assignments payload.
        """
        title = node['title']
        assignments = node['assignments']
        if assignments is None:
            msg = f"Leaf section '{title}' is missing assignments"
            raise ValueError(msg)
        matches, _ = self.match_replies_selection(assignments, replies, km)
        rows = self._flatten_matched_questions(matches, title)
        table = self._source_questions_table(rows)
        prompt = self.construct_chapter_prompt(title, matches)
        content = self.llm_section_from_qa(llm, prompt, stats) if prompt else 'No data'
        debug_body = (table + '\n\n' + content) if table else content
        section = heading + '\n\n' + content
        return section, heading + '\n\n' + debug_body

    def _collect_leaf_futures(
        self,
        scheduled: _ScheduledSection,
    ) -> list[Future[tuple[str, str]]]:
        if scheduled.future is not None:
            return [scheduled.future]
        futures = []
        for child in scheduled.children:
            futures.extend(self._collect_leaf_futures(child))
        return futures

    def _render_scheduled_section(
        self,
        scheduled: _ScheduledSection,
    ) -> tuple[str, str]:
        if scheduled.future is not None:
            return scheduled.future.result()
        if scheduled.no_data:
            res = scheduled.heading + '\nNo data'
            return res, res
        children_parts = [self._render_scheduled_section(child) for child in scheduled.children]
        children_markdown = '\n\n'.join([s for s, _ in children_parts])
        children_markdown_debug = '\n\n'.join([d for _, d in children_parts])
        section = scheduled.heading + '\n\n' + children_markdown
        debug_section = scheduled.heading + '\n\n' + children_markdown_debug
        return section, debug_section
