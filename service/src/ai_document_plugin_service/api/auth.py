import logging
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import fastapi
import httpx

from ai_document_plugin_service.ai.common.config import WILDCARD, AllowedApi, Config, normalize_project_url
from ai_document_plugin_service.ai.common.logging_payloads import summarize_headers
from ai_document_plugin_service.api.jwt import extract_identity_from_token

DSW_API_URL_HEADER = 'X-Dsw-Api-Url'
DSW_USER_VALIDATION_TIMEOUT_SECONDS = 10.0
DSW_USER_VALIDATION_SUCCESS_STATUS = 200
DSW_ADMIN_ROLE = 'admin'
DSW_ADMIN_PERMISSION = 'SettingsManageRolePermission'
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedUser:
    token: str
    api_url: str
    user_uuid: UUID
    tenant_uuid: UUID
    is_admin: bool


def is_allowed_request(api_url: str, tenant_uuid: UUID, allowed_apis: tuple[AllowedApi, ...]) -> bool:
    normalized_api_url = normalize_project_url(api_url)
    tenant_uuid_str = str(tenant_uuid)

    for entry in allowed_apis:
        url_matches = entry.url in {WILDCARD, normalized_api_url}
        tenant_matches = entry.tenant_uuid in {WILDCARD, tenant_uuid_str}
        if not (url_matches and tenant_matches):
            continue
        return True
    return False


def _parse_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    scheme, _, credentials = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not credentials.strip():
        return None

    return credentials.strip()


def _fetch_dsw_user(api_url: str, token: str) -> dict[str, object] | None:
    """Validate the token against DSW and return the current user, or None if rejected."""
    url = f'{normalize_project_url(api_url)}/users/current'
    logger.debug('Validating DSW user against current-user endpoint', extra={'url.full': url})
    try:
        response = httpx.get(
            url,
            headers={'Authorization': f'Bearer {token}'},
            timeout=DSW_USER_VALIDATION_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        logger.warning('DSW user validation request failed', extra={'url.full': url}, exc_info=True)
        return None

    if response.status_code != DSW_USER_VALIDATION_SUCCESS_STATUS:
        return None

    try:
        user = response.json()
    except ValueError:
        return None

    if not isinstance(user, dict):
        return None

    return user


def _is_admin(user: dict[str, object], api_url: str) -> bool:
    role = user.get('role')
    if isinstance(role, str):
        # DSW version < 0.4.33
        return role == DSW_ADMIN_ROLE
    if isinstance(role, dict):
        # DSW version >= 0.4.33
        permissions = role.get('permissions')
        if isinstance(permissions, list):
            return DSW_ADMIN_PERMISSION in permissions
    msg = (
        f'Unexpected response from DSW at {api_url}: the /users/current payload '
        f'did not include a valid "role" string or a "role" object with a "permissions" list. '
        f'The tenant may be running an incompatible DSW version. Received payload: {user}'
    )
    raise ValueError(msg)


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

    try:
        user_uuid, tenant_uuid = extract_identity_from_token(token)
    except ValueError as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error)) from error

    if not is_allowed_request(normalized_api_url, tenant_uuid, config.allowed_apis):
        logger.warning(
            'Authentication failed: request target is not allowed by configuration',
            extra={
                'request.id': request_id,
                'tenant_uuid': str(tenant_uuid),
                'url.full': normalized_api_url,
            },
        )
        raise fastapi.HTTPException(status_code=401, detail='Unauthorized')

    user = _fetch_dsw_user(normalized_api_url, token)
    if user is None:
        raise fastapi.HTTPException(status_code=401, detail='Unauthorized')

    return AuthenticatedUser(
        token=token,
        api_url=normalized_api_url,
        user_uuid=user_uuid,
        tenant_uuid=tenant_uuid,
        is_admin=_is_admin(user, normalized_api_url),
    )
