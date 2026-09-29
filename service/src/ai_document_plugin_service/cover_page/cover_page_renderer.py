import math
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from ai_document_plugin_service.cover_page.cover_page_resolvers import CoverDataSources, resolve_cover_data


def _table_cell(value: object | None) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    text = str(value)
    return text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace('|', '&#124;').strip()


def _metadata_value(value: object) -> str:
    return str(value).replace('|', '\\|')


def _history_value(value: object | None, column: dict[str, str]) -> str:
    if column.get('formatter', 'text') != 'date' or not isinstance(value, str):
        return _table_cell(value)
    try:
        return datetime.fromisoformat(value).strftime('%d.%m.%Y')
    except ValueError:
        return _table_cell(value)


def _metadata_table(rows: list[list[str]]) -> str:
    if not rows:
        return ''

    header, *body = rows
    return pd.DataFrame(body, columns=header).to_markdown(
        index=False,
        tablefmt='github',
        disable_numparse=True,
    )


@dataclass(frozen=True)
class CoverPageRenderer:
    definition: dict

    def render(self, sources: CoverDataSources) -> str:
        metadata = self.definition['metadata']
        history = self.definition['history']

        metadata_rows = [
            [field['label'], _metadata_value(resolve_cover_data(field['resolver'], sources))]
            for field in metadata['fields']
        ]
        lines = [
            f'# {metadata["title"]["text"]}',
            '',
            _metadata_table(metadata_rows),
        ]

        lines.extend(
            [
                '',
                metadata['attribution'],
                '',
                f'## {history["title"]["text"]}',
                '',
                '| ' + ' | '.join(column['text'] for column in history['columns']) + ' |',
                '| ' + ' | '.join('---' for _column in history['columns']) + ' |',
            ]
        )

        history_items = resolve_cover_data(history['resolver'], sources)
        if not isinstance(history_items, list):
            msg = f"Cover history resolver '{history['resolver']}' must return a list"
            raise TypeError(msg)
        lines.extend(
            '| '
            + ' | '.join(_history_value(item.get(column['value_key']), column) for column in history['columns'])
            + ' |'
            for item in history_items
        )

        return '\n'.join(lines)
