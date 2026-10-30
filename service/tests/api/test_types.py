import pytest

from ai_document_plugin_service.api.types import ErrorType


@pytest.mark.parametrize('error_type', list(ErrorType))
def test_every_error_type_has_message(error_type: ErrorType) -> None:
    assert error_type.message


def test_pipeline_timezone_is_validated():
    from uuid import uuid4
    from pydantic import ValidationError
    from ai_document_plugin_service.api.types import PipelineRunRequest

    payload = dict(questionnaireUuid=str(uuid4()), templateUuid=str(uuid4()),
                   llmModel='test', llmApiKey='test', llmApiUrl='https://example.org')
    assert PipelineRunRequest.model_validate({**payload, 'timeZone': 'Europe/Prague'}).time_zone == 'Europe/Prague'
    assert PipelineRunRequest.model_validate(payload).time_zone == 'UTC'
    with pytest.raises(ValidationError):
        PipelineRunRequest.model_validate({**payload, 'timeZone': 'not-a-timezone'})
