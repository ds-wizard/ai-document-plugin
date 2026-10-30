import json
from functools import cache
from pathlib import Path

ISO_639_1 = '639-1'
ISO_639_2 = '639-2'
LANGUAGE_CODE = 'code'
LANGUAGE_ISO_639_2 = 'iso6392'
LANGUAGE_NAME = 'name'
LANGUAGE_NATIVE_NAME = 'nativeName'
LANGUAGE_FAMILY = 'family'
LANGUAGES_FILE = 'languages.json'


@cache
def get_available_languages() -> list[dict[str, str]]:
    resource = Path(__file__).parent / LANGUAGES_FILE
    definitions = json.loads(resource.read_text(encoding='utf-8'))
    return [
        {
            LANGUAGE_CODE: definition[ISO_639_1],
            LANGUAGE_ISO_639_2: definition[ISO_639_2],
            LANGUAGE_NAME: definition[LANGUAGE_NAME],
            LANGUAGE_NATIVE_NAME: definition[LANGUAGE_NATIVE_NAME],
            LANGUAGE_FAMILY: definition[LANGUAGE_FAMILY],
        }
        for definition in definitions.values()
    ]


@cache
def _language_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for definition in get_available_languages():
        names[definition[LANGUAGE_CODE]] = definition[LANGUAGE_NAME]
        for code in definition[LANGUAGE_ISO_639_2].split('/'):
            names[code] = definition[LANGUAGE_NAME]
    return names


def get_language_name(code: str) -> str:
    language, separator, region = code.partition('-')
    name = _language_names().get(language, language)
    return f'{name} ({region})' if separator else name
