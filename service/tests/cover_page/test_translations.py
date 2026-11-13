from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_document_plugin_service.ai.common import config as config_module
from ai_document_plugin_service.ai.common.config import load_config
from ai_document_plugin_service.api.auth import verify_authenticated
from ai_document_plugin_service.api.language_routes import languages_router
from ai_document_plugin_service.api.template_routes import templates_router
from ai_document_plugin_service.api.types import PipelineRunRequest
from ai_document_plugin_service.cover_page.translations import translate_cover_page
from ai_document_plugin_service.data import languages


@pytest.fixture
def config():
    return load_config(str(Path(__file__).resolve().parents[2] / 'config.test.yaml'))


@pytest.fixture
def client(config):
    app = FastAPI()
    app.state.config = config
    app.dependency_overrides[verify_authenticated] = lambda: None
    app.include_router(languages_router)
    app.include_router(templates_router)
    return TestClient(app)


def test_languages(client):
    response = client.get('/languages')
    assert response.status_code == 200
    assert {item['code']: item['name'] for item in response.json()} == {'en': 'English', 'cs': 'Czech'}


@pytest.mark.parametrize(('language', 'heading'), [('en', 'Data Management Plan'), ('cs', 'Plán správy dat')])
def test_translates_cover_page(config, language, heading):
    assert translate_cover_page(config.cover_definition, language).metadata.title.text == heading


def test_preview_is_untranslated(client, config):
    preview = client.get('/cover-page/preview')
    assert preview.status_code == 200
    assert preview.json()['metadata']['title']['text'] == config.cover_definition.metadata.title.text


@pytest.mark.parametrize('language', ['de', 'en-US', 'ces', '../en', ''])
def test_generation_rejects_unsupported_language(language):
    with pytest.raises(ValidationError):
        PipelineRunRequest(questionnaire_uuid=uuid4(), template_uuid=uuid4(), language=language)


@pytest.mark.parametrize('language', ['en', 'cs'])
def test_generation_accepts_supported_language(language):
    request = PipelineRunRequest(questionnaire_uuid=uuid4(), template_uuid=uuid4(), language=language)
    assert request.language == language


def test_missing_translation_fails_without_fallback(config, monkeypatch):
    translation = languages.get_translation('cs').model_copy(deep=True)
    del translation.cover_page['metadata.title.text']
    monkeypatch.setattr(languages, 'get_translations', lambda: {'cs': translation})
    with pytest.raises(ValueError, match=r'Missing translation for cs: metadata\.title\.text'):
        translate_cover_page(config.cover_definition, 'cs')


def test_missing_translation_fails_on_config_load(monkeypatch):
    translation = languages.get_translation('cs').model_copy(deep=True)
    del translation.cover_page['metadata.title.text']
    monkeypatch.setattr(languages, 'get_translations', lambda: {'cs': translation})
    monkeypatch.setattr(config_module, 'get_translations', lambda: {'cs': translation})
    with pytest.raises(ValueError, match=r'Missing translation for cs: metadata\.title\.text'):
        load_config(str(Path(__file__).resolve().parents[2] / 'config.test.yaml'))


def test_translations_do_not_mutate_shared_definition(config):
    original = config.cover_definition.model_dump()
    translated = translate_cover_page(config.cover_definition, 'cs')
    assert translated.sections[0].title == config.cover_definition.sections[0].title
    assert translated.history.preview == config.cover_definition.history.preview
    assert translated.sections[0].preview == config.cover_definition.sections[0].preview
    assert translated.metadata.fields[0].resolver == config.cover_definition.metadata.fields[0].resolver
    assert config.cover_definition.model_dump() == original
