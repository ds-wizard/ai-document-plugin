from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ai_document_plugin_service.ai.persistence.database import PostgresDB, TemplateRecord
from ai_document_plugin_service.ai.persistence.schema import create_persistence_schema
from ai_document_plugin_service.ai.common.types import TemplateContent


@pytest.mark.parametrize('operation', ['create', 'update', 'save'])
async def test_template_writes_json_and_reads_typed_content(operation):
    database = PostgresDB.__new__(PostgresDB)
    schema = create_persistence_schema('test')
    database.schema_name = 'test'
    database.template_table = schema.template_table
    database.assignment_table = schema.assignment_table
    database._ensure_schema = AsyncMock()
    connection = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)))

    @asynccontextmanager
    async def connect():
        yield connection

    database._connect = connect
    raw = {'description': 'Metadata', 'sections': [{'title': 'Parent', 'sections': [{'title': 'Child'}]}]}
    content = TemplateContent.model_validate(raw)
    tenant_uuid = uuid4()
    template_uuid = uuid4()
    if operation == 'create':
        template_uuid = await database.create_template('Template', content, tenant_uuid, None)
    elif operation == 'update':
        await database.update_template(template_uuid, tenant_uuid, 'Template', content)
    else:
        await database.save_template(template_uuid, 'Template', content, tenant_uuid)

    parameters = connection.execute.await_args.args[0].compile().params
    assert parameters['content'] == raw
    assert content.model_dump(mode='json', exclude_unset=True) == raw
    record = TemplateRecord.from_row(SimpleNamespace(
        uuid=template_uuid, title='Template', content=parameters['content'],
        tenant_uuid=tenant_uuid, user_uuid=None, cover_page_version=None,
    ))
    assert record.content == content
