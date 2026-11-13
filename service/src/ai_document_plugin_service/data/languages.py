import json
from functools import cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

TRANSLATIONS_DIRECTORY = Path(__file__).parents[1] / 'translations'


class Translation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    native_name: str = Field(alias='nativeName')
    iso6392: str
    family: str
    cover_page: dict[str, str] = Field(alias='coverPage')


@cache
def get_translations() -> dict[str, Translation]:
    translations = {}
    for resource in sorted(TRANSLATIONS_DIRECTORY.glob('*.json')):
        translation = Translation.model_validate(json.loads(resource.read_text(encoding='utf-8')))
        if translation.code != resource.stem:
            msg = f'Translation code must match filename: {resource.name}'
            raise ValueError(msg)
        translations[translation.code] = translation
    return translations


def get_translation(code: str) -> Translation:
    try:
        return get_translations()[code]
    except KeyError as error:
        msg = f'Unsupported language: {code}'
        raise ValueError(msg) from error


def get_available_languages() -> list[Translation]:
    return list(get_translations().values())


def get_language_name(code: str) -> str:
    return get_translation(code).name
