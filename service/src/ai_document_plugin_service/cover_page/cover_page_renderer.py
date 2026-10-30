import math
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from ai_document_plugin_service.cover_page.cover_page_resolvers import CoverDataSources, resolve_cover_data


def _cell(value: object | None, formatter: str = 'text', pipe_escape: str = '&#124;') -> str:
    if formatter == 'date' and isinstance(value, str):
        try:
            value = datetime.fromisoformat(value).strftime('%d.%m.%Y')
        except ValueError:
            value = str(value)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ''
    return ' '.join(str(value).splitlines()).replace('|', pipe_escape).strip()


def _table(columns: list[dict], rows: list[list[str]]) -> str:
    df = pd.DataFrame(rows, columns=[column['text'] for column in columns])
    return df.to_markdown(index=False, disable_numparse=True)


@dataclass(frozen=True)
class CoverPageRenderer:
    definition: dict

    def render(self, sources: CoverDataSources) -> str:
        metadata = self.definition['metadata']
        history = self.definition['history']

        history_items = resolve_cover_data(history['resolver'], sources)
        if not isinstance(history_items, list):
            msg = f"Cover history resolver '{history['resolver']}' must return a list"
            raise TypeError(msg)

        metadata_rows = [
            [field['label'], _cell(resolve_cover_data(field['resolver'], sources), pipe_escape='\\|')]
            for field in metadata['fields']
        ]
        history_rows = [
            [_cell(item.get(column['value_key']), column.get('formatter', 'text')) for column in history['columns']]
            for item in history_items
        ]

        return '\n'.join(
            [
                f'# {metadata["title"]["text"]}',
                '',
                _table(metadata['columns'], metadata_rows),
                '',
                metadata['attribution'],
                '',
                f'## {history["title"]["text"]}',
                '',
                _table(history['columns'], history_rows),
            ]
        )
