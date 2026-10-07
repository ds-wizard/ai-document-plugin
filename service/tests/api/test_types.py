import pytest

from ai_document_plugin_service.api.types import ErrorType


@pytest.mark.parametrize('error_type', list(ErrorType))
def test_every_error_type_has_message(error_type: ErrorType) -> None:
    assert error_type.message
