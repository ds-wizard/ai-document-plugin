"""Compare the question paths of two assignment result files, section by section.

Takes two files written by run_partial_assignments.py (baseline.json or combination_NNN.json, from the same
or different experiments) and compares the sections present in both. A combination file only holds its
missing sections, so comparing it with a baseline compares exactly the reassigned sections.

Similarity per section is the Jaccard index of the two sets of question paths: |A & B| / |A | B|, so 1.0
means identical and 0.0 means nothing in common. Two empty sets count as identical (1.0).

From the service directory:

    uv run python evals/assignments/compare_assignments.py \
        data/results/assignments/my-experiment/baseline.json \
        data/results/assignments/my-experiment/combination_001.json
"""

import argparse
import json
from pathlib import Path
from typing import Any

from tabulate import tabulate


def _load_question_paths(path: Path) -> dict[str, set[str]]:
    data = json.loads(path.read_text(encoding='utf-8'))
    return {section_id: set(paths) for section_id, paths in data['question_paths'].items()}


def _load_titles(result_file: Path) -> tuple[dict[str, str], dict[str, int]]:
    """Section titles and indices from the sections.json next to a result file, if there is one."""
    sections_file = result_file.parent / 'sections.json'
    if not sections_file.exists():
        return {}, {}
    sections: list[dict[str, Any]] = json.loads(sections_file.read_text(encoding='utf-8'))
    titles = {
        section['section_id']: ' / '.join(' '.join(title.split()) for title in section['title_path'])
        for section in sections
    }
    indices = {section['section_id']: index for index, section in enumerate(sections)}
    return titles, indices


def jaccard(first: set[str], second: set[str]) -> float:
    union = first | second
    return len(first & second) / len(union) if union else 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('first', type=Path, help='First result file (e.g. baseline.json).')
    parser.add_argument('second', type=Path, help='Second result file (e.g. combination_001.json).')
    parser.add_argument('--title-width', type=int, default=60, help='Truncate section titles to this width.')
    args = parser.parse_args()

    first = _load_question_paths(args.first)
    second = _load_question_paths(args.second)
    titles, indices = _load_titles(args.first)
    shared = sorted(first.keys() & second.keys(), key=lambda section_id: indices.get(section_id, len(indices)))
    if not shared:
        raise SystemExit('The two files have no sections in common.')

    rows = []
    for section_id in shared:
        a, b = first[section_id], second[section_id]
        title = titles.get(section_id, section_id)
        rows.append(
            [
                indices.get(section_id, ''),
                title if len(title) <= args.title_width else title[: args.title_width - 1] + '…',
                len(a),
                len(b),
                len(a & b),
                len(a | b),
                f'{jaccard(a, b):.2f}',
            ]
        )
    print(tabulate(rows, headers=['#', 'section', 'first', 'second', 'both', 'either', 'jaccard']))

    mean = sum(jaccard(first[section_id], second[section_id]) for section_id in shared) / len(shared)
    intersections = sum(len(first[section_id] & second[section_id]) for section_id in shared)
    unions = sum(len(first[section_id] | second[section_id]) for section_id in shared)
    pooled = intersections / unions if unions else 1.0
    print()
    print(f'sections compared: {len(shared)}')
    print(f'mean jaccard:      {mean:.3f}  (every section counts equally)')
    print(f'pooled jaccard:    {pooled:.3f}  (all question paths together; large sections weigh more)')


if __name__ == '__main__':
    main()
