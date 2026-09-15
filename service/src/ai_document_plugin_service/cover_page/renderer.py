import math
from dataclasses import dataclass
from datetime import datetime

from ai_document_plugin_service.cover_page.resolvers import CoverDataSources, resolve_cover_data
from ai_document_plugin_service.cover_page.schema import CoverPageDefinition, HistoryColumnDefinition


def _table_cell(value: object | None) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    text = str(value)
    return text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace('|', '&#124;').strip()


def _metadata_value(value: object) -> str:
    return str(value).replace('|', '\\|')


def _history_value(value: object | None, column: HistoryColumnDefinition) -> str:
    if column.formatter != 'date' or not isinstance(value, str):
        return _table_cell(value)
    try:
        return datetime.fromisoformat(value).strftime('%d.%m.%Y')
    except ValueError:
        return _table_cell(value)


@dataclass(frozen=True)
class CoverPageRenderer:
    definition: CoverPageDefinition

    def render(self, sources: CoverDataSources, labels: dict[str, str] | None = None) -> str:
        translated = labels or {}
        metadata = self.definition.metadata
        history = self.definition.history

        lines = [
            f'# {translated.get(metadata.title.id, metadata.title.text)}',
            '',
            '| ' + ' | '.join(translated.get(column.id, column.text) for column in metadata.columns) + ' |',
            '| ' + ' | '.join('---' for _column in metadata.columns) + ' |',
        ]
        for field in metadata.fields:
            value = resolve_cover_data(field.resolver, sources)
            lines.append(f'| {translated.get(field.id, field.label)} | {_metadata_value(value)} |')

        lines.extend(
            [
                '',
                metadata.attribution,
                '',
                f'## {translated.get(history.title.id, history.title.text)}',
                '',
                '| ' + ' | '.join(translated.get(column.id, column.text) for column in history.columns) + ' |',
                '| ' + ' | '.join('---' for _column in history.columns) + ' |',
            ]
        )

        history_items = resolve_cover_data(history.resolver, sources)
        if not isinstance(history_items, list):
            msg = f"Cover history resolver '{history.resolver}' must return a list"
            raise TypeError(msg)
        lines.extend(
            '| ' + ' | '.join(_history_value(item.get(column.value_key), column) for column in history.columns) + ' |'
            for item in history_items
        )

        return '\n'.join(lines)
