import logging
from uuid import UUID

import httpx

from ai_document_plugin_service.ai.common.logging_payloads import summarize_payload

logger = logging.getLogger(__name__)


class DSWClient:
    def __init__(self, token: str, api_url: str) -> None:
        self.token = token
        self.api_url = api_url.rstrip('/')

    async def get_questionnaire_detail(self, questionnaire_uuid: str | UUID) -> dict:
        url = f'{self.api_url}/projects/{questionnaire_uuid}/questionnaire'
        logger.info(
            'Fetching questionnaire detail from DSW',
            extra={'url.full': url, 'questionnaire_uuid': str(questionnaire_uuid)},
        )

        headers: dict[str, str] = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(
                'Failed to fetch questionnaire detail from DSW',
                extra={'url.full': url, 'questionnaire_uuid': str(questionnaire_uuid)},
            )
            raise

        payload = response.json()
        logger.info(
            'Fetched questionnaire detail successfully',
            extra={
                'url.full': url,
                'questionnaire_uuid': str(questionnaire_uuid),
                'http.response.status_code': response.status_code,
            },
        )
        logger.debug(
            'DSW questionnaire detail payload',
            extra={
                'questionnaire_uuid': str(questionnaire_uuid),
                'dsw.response.body': summarize_payload(payload),
            },
        )
        return payload
