"""Run-local, lossless source identifiers used only inside LLM prompts and responses."""

import re
from collections.abc import Iterable, Mapping
from html import escape

_SOURCE_ATTRIBUTE = re.compile(r"""(<statement\s+source\s*=\s*)(["'])(.*?)(\2)""", re.DOTALL)


def build_source_ids(paths: Iterable[str]) -> dict[str, str]:
    """Assign deterministic IDs to concrete reply paths, including list item UUIDs."""
    return {path: f'q{index}' for index, path in enumerate(sorted(set(paths)), start=1)}


def restore_source_paths(markdown: str, source_ids: Mapping[str, str]) -> str:
    """Expand only statement source attributes; reject missing or unknown identifiers."""
    paths_by_id = {source_id: path for path, source_id in source_ids.items()}

    def replace(match: re.Match[str]) -> str:
        identifiers = match.group(3).split()
        if not identifiers:
            msg = 'Statement has an empty source attribute'
            raise ValueError(msg)
        unknown = set(identifiers) - paths_by_id.keys()
        if unknown:
            msg = f'Unknown statement source IDs: {", ".join(sorted(unknown))}'
            raise ValueError(msg)
        paths = ' '.join(paths_by_id[source_id] for source_id in dict.fromkeys(identifiers))
        return f'{match.group(1)}{match.group(2)}{escape(paths, quote=True)}{match.group(2)}'

    return _SOURCE_ATTRIBUTE.sub(replace, markdown)
