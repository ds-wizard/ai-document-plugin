from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_have_exactly_one_head() -> None:
    service_dir = Path(__file__).resolve().parents[2]
    config = Config(str(service_dir / 'alembic.ini'))
    config.set_main_option(
        'script_location',
        str(service_dir / 'src' / 'ai_document_plugin_service' / 'migrations'),
    )
    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1, (
        f'Expected exactly one Alembic head, found {len(heads)}: {heads}. '
        'Create a merge migration with `uv run alembic merge -m "Merge migration heads" heads`.'
    )
