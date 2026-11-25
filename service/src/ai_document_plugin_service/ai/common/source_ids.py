"""Run-local, lossless source identifiers used only inside LLM prompts and responses."""

import re
from collections.abc import Iterable, Mapping
from html import escape

_SOURCE_ATTRIBUTE = re.compile(r"""(<statement\s+source\s*=\s*)(["'])(.*?)(\2)""", re.DOTALL)
_STATEMENT_TAG = re.compile(r'</?statement\b[^>]*>', re.DOTALL)
_OPEN_STATEMENT = re.compile(r"""<statement\s+source\s*=\s*(["'])(.*?)\1\s*>""", re.DOTALL)


class SourceValidationError(ValueError):
    """The generated statement markup cannot be safely mapped to input sources."""


def extract_source_ids(markdown: str) -> set[str]:
    """Read IDs from statement tags.

    Raises:
        SourceValidationError: Source tags are malformed, empty, nested or unbalanced.
    """
    identifiers: set[str] = set()
    opened = False
    tags = list(_STATEMENT_TAG.finditer(markdown))
    if len(tags) != len(re.findall(r'</?statement\b', markdown)):
        msg = 'Incomplete statement tag'
        raise SourceValidationError(msg)
    for match in tags:
        tag = match.group()
        if re.fullmatch(r'</statement\s*>', tag):
            if not opened:
                msg = 'Closing statement tag without an opening tag'
                raise SourceValidationError(msg)
            opened = False
            continue
        opening = _OPEN_STATEMENT.fullmatch(tag)
        if opening is None or opened:
            msg = 'Malformed or nested statement tag; use <statement source="q1">text</statement>'
            raise SourceValidationError(msg)
        sources = opening.group(2).split()
        if not sources:
            msg = 'Statement has an empty source attribute'
            raise SourceValidationError(msg)
        identifiers.update(sources)
        opened = True
    if opened:
        msg = 'Statement tag is not closed'
        raise SourceValidationError(msg)
    return identifiers


def validate_source_ids(markdown: str, allowed_ids: set[str], *, require_sources: bool = False) -> None:
    identifiers = extract_source_ids(markdown)
    unknown = identifiers - allowed_ids
    if unknown:
        msg = f'Unknown statement source IDs: {", ".join(sorted(unknown))}'
        raise SourceValidationError(msg)
    if require_sources and not identifiers:
        msg = 'Source annotations were removed; preserve statement tags and their supporting IDs'
        raise SourceValidationError(msg)


def build_source_ids(paths: Iterable[str]) -> dict[str, str]:
    """Assign deterministic IDs to concrete reply paths, including list item UUIDs."""
    return {path: f'q{index}' for index, path in enumerate(sorted(set(paths)), start=1)}


def restore_source_paths(markdown: str, source_ids: Mapping[str, str]) -> str:
    """Expand only statement source attributes; reject missing or unknown identifiers."""
    paths_by_id = {source_id: path for path, source_id in source_ids.items()}
    validate_source_ids(markdown, set(paths_by_id))

    def replace(match: re.Match[str]) -> str:
        identifiers = match.group(3).split()
        paths = ' '.join(paths_by_id[source_id] for source_id in dict.fromkeys(identifiers))
        return f'{match.group(1)}{match.group(2)}{escape(paths, quote=True)}{match.group(2)}'

    return _SOURCE_ATTRIBUTE.sub(replace, markdown)
