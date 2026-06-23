from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4


def _request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main() -> int:
    api_url = os.getenv('MOIRA_BASE_URL', 'http://127.0.0.1:8000')
    grafana_url = os.getenv('GRAFANA_URL', 'http://127.0.0.1:3000')
    grafana_user = os.getenv('GRAFANA_USER', 'admin')
    grafana_password = os.getenv('GRAFANA_PASSWORD', 'admin')
    correlation_id = f'observability-smoke-{uuid4().hex}'

    status, _ = _request(
        f'{api_url}/v1/observability-smoke-unmatched',
        headers={'X-Correlation-ID': correlation_id},
    )
    if status != 404:
        raise RuntimeError(f'Expected API 404 smoke event, got {status}')

    credentials = base64.b64encode(
        f'{grafana_user}:{grafana_password}'.encode()
    ).decode()
    headers = {'Authorization': f'Basic {credentials}'}
    query = f'{{service_name="moira"}} | correlation_id="{correlation_id}"'
    params = urllib.parse.urlencode({'query': query, 'limit': 20})
    query_url = (
        f'{grafana_url}/api/datasources/proxy/uid/loki/loki/api/v1/query_range?{params}'
    )

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        query_status, body = _request(query_url, headers=headers)
        if query_status == 200:
            payload = json.loads(body)
            if payload.get('data', {}).get('result'):
                print(f'Observed correlation_id={correlation_id} through Grafana/Loki')
                return 0
        time.sleep(1)

    raise RuntimeError(
        f'Log with correlation_id={correlation_id} was not found through Grafana'
    )


if __name__ == '__main__':
    raise SystemExit(main())
