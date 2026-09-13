import threading
from collections.abc import Mapping

from pydantic import BaseModel

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_WRITE_LOCK = threading.Lock()


def make_json_safe(value: object) -> JsonValue:
    result: JsonValue
    if value is None or isinstance(value, str | int | float | bool):
        result = value
    elif isinstance(value, BaseModel):
        result = make_json_safe(value.model_dump(mode='json'))
    elif isinstance(value, Mapping):
        result = {str(key): make_json_safe(item) for key, item in value.items()}
    elif isinstance(value, list | tuple | set):
        result = [make_json_safe(item) for item in value]
    else:
        result = repr(value)
    return result
