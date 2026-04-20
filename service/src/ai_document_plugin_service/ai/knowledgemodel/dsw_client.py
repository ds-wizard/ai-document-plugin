import httpx

from ai_document_plugin_service.ai.common.config import load_config


def get_questionnaire_detail(questionnaire_uuid: str, token: str | None = None) -> dict:
    config = load_config()
    base_url = config.dsw_api_url.rstrip("/")
    url = f"{base_url}/projects/{questionnaire_uuid}/questionnaire"

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = httpx.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
