from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import fastapi
import httpx

from ai_document_plugin_service.ai.common.config import Config, normalize_project_url
from ai_document_plugin_service.api.jwt import extract_identity_from_token

DSW_API_URL_HEADER = 'X-Dsw-Api-Url'
DSW_USER_VALIDATION_TIMEOUT_SECONDS = 10.0
DSW_USER_VALIDATION_SUCCESS_STATUS = 200


@dataclass(frozen=True)
class AuthenticatedUser:
    token: str
    api_url: str
    user_uuid: UUID
    tenant_uuid: UUID


def is_allowed_project_url(api_url: str, allowed_project_urls: tuple[str, ...]) -> bool:
    return normalize_project_url(api_url) in allowed_project_urls


def _parse_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    scheme, _, credentials = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not credentials.strip():
        return None

    return credentials.strip()


def _validate_dsw_user(api_url: str, token: str) -> bool:
    url = f'{normalize_project_url(api_url)}/users/current'
    try:
        response = httpx.get(
            url,
            headers={'Authorization': f'Bearer {token}'},
            timeout=DSW_USER_VALIDATION_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        return False

    return response.status_code == DSW_USER_VALIDATION_SUCCESS_STATUS


def verify_authenticated(
    request: fastapi.Request,
    authorization: Annotated[str | None, fastapi.Header()] = None,
    dsw_api_url: Annotated[str | None, fastapi.Header(alias=DSW_API_URL_HEADER)] = None,
) -> AuthenticatedUser:
    token = _parse_bearer_token(authorization)
    if token is None:
        raise fastapi.HTTPException(status_code=401, detail='Unauthorized')

    if dsw_api_url is None or not dsw_api_url.strip():
        raise fastapi.HTTPException(status_code=401, detail='Unauthorized')

    config: Config = request.app.state.config
    normalized_api_url = normalize_project_url(dsw_api_url)

    if not is_allowed_project_url(normalized_api_url, config.allowed_project_urls):
        raise fastapi.HTTPException(status_code=401, detail='Unauthorized')

    if not _validate_dsw_user(normalized_api_url, token):
        raise fastapi.HTTPException(status_code=401, detail='Unauthorized')

    try:
        user_uuid, tenant_uuid = extract_identity_from_token(token)
    except ValueError as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error)) from error

    return AuthenticatedUser(token=token, api_url=normalized_api_url, user_uuid=user_uuid, tenant_uuid=tenant_uuid)
