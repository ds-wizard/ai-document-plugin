import json
from functools import cache
from pathlib import Path

ISO_639_1 = '639-1'
ISO_639_2 = '639-2'
LANGUAGE_NAME = 'name'
LANGUAGES_FILE = 'languages.json'


@cache
def get_available_languages() -> list[dict[str, str]]:
    resource = Path(__file__).parent / LANGUAGES_FILE
    definitions = json.loads(resource.read_text(encoding='utf-8'))
    return [
        {
            'code': definition[ISO_639_1],
            'iso6392': definition[ISO_639_2],
            'name': definition[LANGUAGE_NAME],
            'nativeName': definition['nativeName'],
            'family': definition['family'],
        }
        for definition in definitions.values()
    ]


@cache
def _language_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for definition in get_available_languages():
        names[definition[ISO_639_1]] = definition[LANGUAGE_NAME]
        for code in definition[ISO_639_2].split('/'):
            names[code] = definition[LANGUAGE_NAME]
    return names


def get_language_name(code: str) -> str:
    language, separator, region = code.partition('-')
    name = _language_names().get(language, language)
    return f'{name} ({region})' if separator else name
