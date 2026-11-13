from dataclasses import dataclass

from ai_document_plugin_service.cover_page.cover_page_definition import (
    CoverPageDefinition,
    CoverPageField,
    CoverPageHistory,
    CoverPageLabel,
    CoverPageMetadata,
)
from ai_document_plugin_service.data.languages import get_translation


@dataclass(frozen=True)
class _CoverPageTranslator:
    language: str
    translations: dict[str, str]

    def text(self, key: str) -> str:
        try:
            return self.translations[key]
        except KeyError as error:
            msg = f'Missing translation for {self.language}: {key}'
            raise ValueError(msg) from error

    def label[T: CoverPageLabel](self, label: T, key: str) -> T:
        return label.model_copy(update={'text': self.text(f'{key}.text')})

    def field[T: CoverPageField](self, field: T, key: str) -> T:
        return field.model_copy(update={'label': self.text(f'{key}.{field.id}.label')})

    def metadata(self, metadata: CoverPageMetadata) -> CoverPageMetadata:
        return metadata.model_copy(
            update={
                'title': self.label(metadata.title, 'metadata.title'),
                'columns': [self.label(column, f'metadata.columns.{column.id}') for column in metadata.columns],
                'fields': [self.field(field, 'metadata.fields') for field in metadata.fields],
                'attribution': self.text('metadata.attribution'),
            }
        )

    def history(self, history: CoverPageHistory) -> CoverPageHistory:
        return history.model_copy(
            update={
                'title': self.label(history.title, 'history.title'),
                'columns': [self.label(column, f'history.columns.{column.id}') for column in history.columns],
            }
        )


def translate_cover_page(definition: CoverPageDefinition, language: str) -> CoverPageDefinition:
    translator = _CoverPageTranslator(language, get_translation(language).cover_page)
    return definition.model_copy(
        update={
            'metadata': translator.metadata(definition.metadata),
            'history': translator.history(definition.history),
        }
    )
