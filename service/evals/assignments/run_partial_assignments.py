"""Run question-to-section assignment fully and then with only some sections missing, and save the results.

First runs the assignment with nothing stored (every leaf section is assigned). With --sections, it then
runs it once more with exactly the given sections missing and all others stored with their baseline paths.
Nothing is evaluated here; every run is saved for later comparison.

From the service directory, baseline only:

    uv run --env-file .env python evals/assignments/run_partial_assignments.py --experiment my-experiment \
        --template data/templates/science-europe.json

One run with sections 5 and 7 missing together (indices of the leaf sections in tree order, as in sections.json):

    uv run --env-file .env python evals/assignments/run_partial_assignments.py --experiment my-experiment-5-7 \
        --template data/templates/science-europe.json --sections 5 7

LLM settings come from --api-url/--api-key/--model or the LLM_API_URL, LLM_API_KEY and
LLM_MODEL environment variables. Results go to data/results/assignments/<experiment>/ (gitignored).
Run with --help for all options.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from ai_document_plugin_service.ai.assignment.assignment_component import AssignmentComponent
from ai_document_plugin_service.ai.assignment.compatibility_utils import collect_leaf_question_paths
from ai_document_plugin_service.ai.assignment.mappers import template_sections_to_records
from ai_document_plugin_service.ai.assignment.types import SectionQuestionPaths, SectionRecord
from ai_document_plugin_service.ai.common.config import load_config
from ai_document_plugin_service.ai.common.llm_client import LLMClient
from ai_document_plugin_service.ai.common.types import AssignmentStats, TemplateContent
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent

SERVICE_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = SERVICE_DIR / 'data' / 'results' / 'assignments'


def _leaf_sections(sections: list[SectionRecord], titles: list[str] | None = None) -> list[dict[str, Any]]:
    """Leaf sections in tree order with their title path, one entry per distinct section id."""
    leaves: dict[UUID, dict[str, Any]] = {}
    for section in sections:
        title_path = [*(titles or []), section.title]
        if section.children is None:
            leaves.setdefault(section.id, {'section_id': str(section.id), 'title_path': title_path})
            continue
        for leaf in _leaf_sections(section.children, title_path):
            leaves.setdefault(UUID(leaf['section_id']), leaf)
    return list(leaves.values())


def _redact_api_key(argv: list[str]) -> list[str]:
    """Command line with the value of --api-key replaced, so run.json never contains the key."""
    redacted: list[str] = []
    for index, arg in enumerate(argv):
        if index > 0 and argv[index - 1] == '--api-key':
            redacted.append('<redacted>')
        elif arg.startswith('--api-key='):
            redacted.append('--api-key=<redacted>')
        else:
            redacted.append(arg)
    return redacted


def _paths_json(paths: SectionQuestionPaths) -> dict[str, list[str]]:
    return {str(section_id): question_paths for section_id, question_paths in paths.items()}


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


async def _assign(
    component: AssignmentComponent,
    questions: list[Any],
    template: TemplateContent,
    km: dict[str, Any],
    stored: SectionQuestionPaths | None,
) -> tuple[SectionQuestionPaths, AssignmentStats | None]:
    result = await component.run_async(questions, template, km, stored_question_paths=stored)
    return collect_leaf_question_paths(result['assignments']), result['stats']


async def _run(
    experiment_dir: Path,
    template: TemplateContent,
    km_data: dict[str, Any],
    component: AssignmentComponent,
    selected_indices: list[int] | None,
) -> None:
    km = km_data['knowledgeModel']
    questions = ParserComponent().run(km_data)['data']
    leaves = _leaf_sections(template_sections_to_records(template.sections))
    _write_json(experiment_dir / 'sections.json', leaves)

    print(f'Baseline: assigning all {len(leaves)} leaf sections')
    baseline, stats = await _assign(component, questions, template, km, stored=None)
    _write_json(
        experiment_dir / 'baseline.json',
        {'question_paths': _paths_json(baseline), 'stats': stats.to_dict() if stats else None},
    )

    if selected_indices is None:
        return

    missing = [UUID(leaves[index]['section_id']) for index in selected_indices]
    print(f'Combination: assigning {len(missing)} missing section(s)')
    stored = {section_id: paths for section_id, paths in baseline.items() if section_id not in missing}
    paths, stats = await _assign(component, questions, template, km, stored=stored)
    _write_json(
        experiment_dir / 'combination_001.json',
        {
            'missing_section_ids': [str(section_id) for section_id in missing],
            'question_paths': _paths_json({section_id: paths[section_id] for section_id in missing}),
            'stats': stats.to_dict() if stats else None,
        },
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--experiment',
        required=True,
        help='Experiment name; results go to data/results/assignments/<experiment>/.',
    )
    parser.add_argument('--template', required=True, type=Path, help='Template content JSON ({"sections": [...]}).')
    parser.add_argument(
        '--km',
        type=Path,
        default=SERVICE_DIR / 'tests/resources/dsw_root_km.json.json',
        help='Knowledge model JSON, or a questionnaire detail with "knowledgeModel" and "replies".',
    )
    parser.add_argument('--api-url', default=os.environ.get('LLM_API_URL', 'https://api.openai.com/v1'))
    parser.add_argument('--api-key', default=os.environ.get('LLM_API_KEY'), help='Default: LLM_API_KEY.')
    parser.add_argument('--model', default=os.environ.get('LLM_MODEL', 'gpt-4o-mini'))
    parser.add_argument('--parallel-workers', type=int, default=int(os.environ.get('LLM_PARALLEL_WORKERS', '4')))
    parser.add_argument(
        '--sections',
        type=int,
        nargs='+',
        metavar='INDEX',
        help='Run once with exactly these sections missing, by index of the leaf sections in tree order '
        '(as listed in sections.json). Default: only the baseline run.',
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=SERVICE_DIR / 'config.test.yaml',
        help='Service config; provides the assignment prompts.',
    )
    args = parser.parse_args()

    if not args.template.exists():
        parser.error(f'template {args.template} does not exist')
    if not args.api_key:
        parser.error('set --api-key or LLM_API_KEY')
    if (RESULTS_DIR / args.experiment).exists():
        parser.error(f'{RESULTS_DIR / args.experiment} already exists')
    return args


def main() -> None:
    args = _parse_args()
    template_content = TemplateContent.model_validate(json.loads(args.template.read_text(encoding='utf-8')))
    leaves = _leaf_sections(template_sections_to_records(template_content.sections))
    if args.sections is not None:
        invalid = [index for index in args.sections if not 0 <= index < len(leaves)]
        if invalid:
            msg = (
                f'--sections {invalid} out of range; the template has {len(leaves)} leaf sections (0-{len(leaves) - 1})'
            )
            raise SystemExit(msg)
        args.sections = sorted(set(args.sections))

    experiment_dir = RESULTS_DIR / args.experiment
    service_config = load_config(str(args.config))
    raw_km = json.loads(args.km.read_text(encoding='utf-8'))
    km_data = raw_km if 'knowledgeModel' in raw_km else {'knowledgeModel': raw_km, 'replies': {}}

    llm_client = LLMClient(uuid4())
    llm_client.update_config(args.model, args.api_key, args.api_url, args.parallel_workers)
    component = AssignmentComponent(llm_client, service_config)

    experiment_dir.mkdir(parents=True)
    _write_json(
        experiment_dir / 'run.json',
        {
            'started_at': datetime.now(tz=UTC).isoformat(),
            'command': _redact_api_key(sys.argv),
            'arguments': {name: str(value) if isinstance(value, Path) else value for name, value in vars(args).items()}
            | {'api_key': '<redacted>'},
            'assignment_prompt': {
                'system_message': service_config.assignment.system_message,
                'user_message': service_config.assignment.user_message,
                'temperature': service_config.assignment.temperature,
            },
        },
    )
    asyncio.run(
        _run(
            experiment_dir,
            template_content,
            km_data,
            component,
            args.sections,
        )
    )
    print(f'Results saved to {experiment_dir}')


if __name__ == '__main__':
    main()
