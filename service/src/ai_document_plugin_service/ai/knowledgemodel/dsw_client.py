import logging
from uuid import UUID

import httpx

from ai_document_plugin_service.ai.common.logging_payloads import summarize_payload
from ai_document_plugin_service.ai.knowledgemodel.project_version import sort_project_versions

logger = logging.getLogger(__name__)


# Stands for "event 0" of a questionnaire without any events.
NO_EVENTS_UUID = UUID(int=0)

# The questionnaire detail carries the whole knowledge model, which DSW can take several seconds to build.
DSW_REQUEST_TIMEOUT_SECONDS = 15


def parse_latest_event_uuid(payload: object) -> UUID:
    """Read the newest event UUID from a ``/projects/{uuid}/events?size=1&sort=createdAt,desc`` response.

    A questionnaire without events gives ``NO_EVENTS_UUID``.

    Raises:
        TypeError: If the payload is not the expected page of events. A malformed event also raises KeyError or
            ValueError.
    """
    if not isinstance(payload, dict):
        msg = 'Unexpected events response: not an object'
        raise TypeError(msg)

    embedded = payload.get('_embedded')
    events = embedded.get('projectEvents') if isinstance(embedded, dict) else None
    if not isinstance(events, list):
        msg = 'Unexpected events response: no projectEvents list'
        raise TypeError(msg)
    if not events:
        return NO_EVENTS_UUID
    return UUID(events[0]['uuid'])


class DSWClient:
    def __init__(self, token: str, api_url: str) -> None:
        self.token = token
        self.api_url = api_url.rstrip('/')

    async def get_questionnaire_detail(self, questionnaire_uuid: UUID) -> dict:
        url = f'{self.api_url}/projects/{questionnaire_uuid}/questionnaire'
        logger.info(
            'Fetching questionnaire detail from DSW',
            extra={'url.full': url, 'questionnaire_uuid': str(questionnaire_uuid)},
        )

        headers: dict[str, str] = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            async with httpx.AsyncClient(timeout=DSW_REQUEST_TIMEOUT_SECONDS) as client:
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

    async def get_latest_event_uuid(self, project_uuid: str | UUID) -> UUID:
        # One event, newest first. DSW applies no default order, so the sort is required.
        url = f'{self.api_url}/projects/{project_uuid}/events'
        logger.info(
            'Fetching latest questionnaire event from DSW',
            extra={'url.full': url, 'project_uuid': str(project_uuid)},
        )

        headers: dict[str, str] = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            async with httpx.AsyncClient(timeout=DSW_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(url, headers=headers, params={'size': 1, 'sort': 'createdAt,desc'})
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(
                'Failed to fetch latest questionnaire event from DSW',
                extra={'url.full': url, 'project_uuid': str(project_uuid)},
            )
            raise

        return parse_latest_event_uuid(response.json())

    async def get_project_versions(self, project_uuid: str | UUID) -> list[dict]:
        # Fetch versions once and return them newest first for all consumers.
        url = f'{self.api_url}/projects/{project_uuid}/versions'
        logger.info(
            'Fetching project versions from DSW',
            extra={'url.full': url, 'project_uuid': str(project_uuid)},
        )

        headers: dict[str, str] = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            async with httpx.AsyncClient(timeout=DSW_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(
                'Failed to fetch project versions from DSW',
                extra={'url.full': url, 'project_uuid': str(project_uuid)},
            )
            raise

        payload = response.json()
        if not isinstance(payload, list):
            logger.warning(
                'Project versions response was not a list',
                extra={'url.full': url, 'project_uuid': str(project_uuid)},
            )
            return []

        return sort_project_versions([version for version in payload if isinstance(version, dict)])
