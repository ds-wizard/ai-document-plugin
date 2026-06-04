import httpx

from ai_document_plugin_service.ai.common.config import Config


def get_questionnaire_detail(
    questionnaire_uuid: str,
    config: Config,
    token: str | None = None,
    api_url: str | None = None,
) -> dict:
    base_url = (api_url or config.dsw_api_url).rstrip('/')
    url = f'{base_url}/projects/{questionnaire_uuid}/questionnaire'

    headers: dict[str, str] = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'

    response = httpx.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
