"""Finding the list an item-select reply points to."""

from collections.abc import Iterable


def find_list_path(list_question_uuid: str, item_uuid: str, replies: Iterable[tuple[str, object]]) -> str | None:
    """The path of the reply to the list question that holds the item, or None when no list reply holds it.

    ``replies`` yields ``(path, value)`` with the value as DSW sends it (``{type, value}``). The list question can
    be anywhere in the knowledge model, not only next to the item-select question, so its reply is found by the
    list question's UUID at the end of its path and the item among its items.
    """
    suffix = f'.{list_question_uuid}'
    for path, value in replies:
        if (
            path.endswith(suffix)
            and isinstance(value, dict)
            and value.get('type') == 'ItemListReply'
            and item_uuid in (value.get('value') or [])
        ):
            return path
    return None
