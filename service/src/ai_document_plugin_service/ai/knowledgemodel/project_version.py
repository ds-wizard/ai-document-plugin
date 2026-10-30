"""Shared project-version ordering for generation labels and History of Changes."""

from typing import Any


def sort_project_versions(versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return versions newest first without changing the supplied list."""

    def updated_at(version: dict[str, Any]) -> str:
        value = version.get('updatedAt')
        return value if isinstance(value, str) else ''

    return sorted(versions, key=updated_at, reverse=True)


def resolve_named_version(versions: list[dict[str, Any]]) -> str | None:
    """Select the first named version from a newest-first list supplied by DSWClient."""
    for version in versions:
        name = version.get('name')
        if isinstance(name, str) and name.strip():
            return name
    return None
