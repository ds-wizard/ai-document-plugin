"""Drives one service container through a full pipeline run over HTTP and records when each phase happened."""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import httpx

USER_UUID = '44444444-4444-4444-8444-444444444444'
TENANT_UUID = '11111111-1111-4111-8111-111111111111'
QUESTIONNAIRE_UUID = '55555555-5555-4555-8555-555555555555'
DSW_API_URL = 'http://fake-upstream:9000/wizard-api'
LLM_API_URL = 'http://fake-upstream:9000/v1'
UPSTREAM_URL = 'http://fake-upstream:9000'
SERVICE_URL = 'http://bench-service:8010'
MAX_LLM_WORKERS = 4
POLL_SECONDS = 1.0


def now_ms() -> int:
    return round(time.time() * 1000)


def fake_token() -> str:
    """The service reads identity from the JWT payload and validates the token against the fake DSW."""
    claims = {'user_uuid': USER_UUID, 'tenant_uuid': TENANT_UUID}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return f'benchmark.{payload}.benchmark'


def wait_until_healthy(client: httpx.Client, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if client.get('/health').status_code == httpx.codes.OK:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.2)
    sys.exit(f'Service was not healthy within {timeout} seconds.')


def checked(response: httpx.Response) -> dict:
    if response.is_error:
        sys.exit(f'{response.request.method} {response.url} returned {response.status_code}: {response.text}')
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mode', required=True)
    parser.add_argument('--round', type=int, required=True)
    parser.add_argument('--idle-before', type=float, default=20.0)
    parser.add_argument('--idle-after', type=float, default=20.0)
    parser.add_argument('--timeout', type=float, default=1800.0)
    args = parser.parse_args()

    headers = {'Authorization': f'Bearer {fake_token()}', 'X-Dsw-Api-Url': DSW_API_URL}
    template = json.loads(Path(__file__).with_name('template.json').read_text())

    with (
        httpx.Client(base_url=SERVICE_URL, headers=headers, timeout=60.0) as service,
        httpx.Client(base_url=UPSTREAM_URL, timeout=60.0) as upstream,
    ):
        wait_until_healthy(upstream, timeout=60.0)
        checked(upstream.post('/reset'))
        wait_until_healthy(service, timeout=180.0)
        ready_ms = now_ms()
        time.sleep(args.idle_before)

        checked(
            service.put(
                '/settings/llm',
                json={'model': 'fake', 'apiUrl': LLM_API_URL, 'apiKey': 'fake', 'maxWorkers': MAX_LLM_WORKERS},
            )
        )
        template_uuid = checked(service.post('/templates', json={'title': 'RAM benchmark', 'content': template}))['uuid']

        pipeline_start_ms = now_ms()
        status = checked(
            service.post('/pipelines/run', json={'questionnaireUuid': QUESTIONNAIRE_UUID, 'templateUuid': template_uuid})
        )
        deadline = time.monotonic() + args.timeout
        while status['status'] in {'queued', 'running'}:
            if time.monotonic() > deadline:
                sys.exit(f'Pipeline did not finish within {args.timeout} seconds.')
            time.sleep(POLL_SECONDS)
            status = checked(service.get(f'/pipelines/status/{status["runId"]}'))
        pipeline_end_ms = now_ms()

        if status['status'] != 'succeeded':
            sys.exit(f'Pipeline finished as {status["status"]}: {status.get("error")}')

        calls = checked(upstream.get('/stats'))
        if calls['assignment'] == 0:
            sys.exit('The pipeline made no assignment calls, so the token counter never ran.')

        time.sleep(args.idle_after)

    args.out.write_text(
        json.dumps(
            {
                'mode': args.mode,
                'round': args.round,
                'ready_ms': ready_ms,
                'pipeline_start_ms': pipeline_start_ms,
                'pipeline_end_ms': pipeline_end_ms,
                'end_ms': now_ms(),
                'assignment_calls': calls['assignment'],
                'generation_calls': calls['generation'],
                'polishing_calls': calls['polishing'],
            },
            indent=2,
        )
    )
    print(
        f'{args.mode} round {args.round}: pipeline took {(pipeline_end_ms - pipeline_start_ms) / 1000:.1f}s, '
        f'LLM calls {calls}'
    )


if __name__ == '__main__':
    main()
