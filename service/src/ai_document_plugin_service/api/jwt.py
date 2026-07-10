import base64
import json
import uuid
from uuid import UUID

JWT_PART_COUNT = 2


def decode_jwt_payload(token: str) -> dict[str, object]:
    parts = token.split('.')
    if len(parts) < JWT_PART_COUNT:
        msg = 'Invalid JWT token format.'
        raise ValueError(msg)

    payload = parts[1]
    padding = '=' * ((4 - len(payload) % 4) % 4)

    try:
        decoded = base64.urlsafe_b64decode(f'{payload}{padding}')
        parsed = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        msg = 'Invalid JWT token payload.'
        raise ValueError(msg) from exc

    if not isinstance(parsed, dict):
        msg = 'Invalid JWT token payload.'
        raise TypeError(msg)

    return parsed


def _get_required_uuid_claim(payload: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            try:
                # TODO: https://github.com/ds-wizard/ai-document-plugin/issues/61
                return str(UUID(value))
            except ValueError:
                continue

    msg = f'Missing required JWT claim: {", ".join(keys)}'
    raise ValueError(msg)


def extract_identity_from_token(token: str) -> tuple[UUID, UUID]:
    payload = decode_jwt_payload(token)
    user_uuid = _get_required_uuid_claim(payload, 'user_uuid', 'userUuid')
    tenant_uuid = _get_required_uuid_claim(payload, 'tenant_uuid', 'tenantUuid')
    return uuid.UUID(user_uuid), uuid.UUID(tenant_uuid)
