from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / 'docker-compose.test.yaml'
SERVICE_NAME = 'postgres-test'
POSTGRES_USER = 'moira'
POSTGRES_PASSWORD = 'moira'
POSTGRES_DB = 'moira_test'


def _compose_command(project_name: str, *args: str) -> list[str]:
    return [
        'docker',
        'compose',
        '-p',
        project_name,
        '-f',
        str(COMPOSE_FILE),
        *args,
    ]


def _run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, env=env, check=check, text=True)


def _capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _host_port(project_name: str) -> str:
    result = _capture(_compose_command(project_name, 'port', SERVICE_NAME, '5432'))
    mapping = result.stdout.strip().splitlines()[0]
    return mapping.rsplit(':', maxsplit=1)[-1]


def _wait_until_ready(project_name: str) -> None:
    deadline = time.monotonic() + 30
    command = _compose_command(
        project_name,
        'exec',
        '-T',
        SERVICE_NAME,
        'pg_isready',
        '-U',
        POSTGRES_USER,
        '-d',
        POSTGRES_DB,
    )

    while time.monotonic() < deadline:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return

        time.sleep(0.5)

    raise RuntimeError('Timed out waiting for PostgreSQL integration test container')


def _integration_env(host_port: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            'APP_ENV': 'test',
            'DATABASE_URL': (
                f'postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}'
                f'@localhost:{host_port}/{POSTGRES_DB}'
            ),
            'JWT_SECRET_KEY': 'integration-test-secret-at-least-32-bytes',
            'MOIRA_ALLOW_INTEGRATION_DATABASE': '1',
        }
    )
    return env


def main() -> int:
    project_name = os.environ.get(
        'MOIRA_TEST_COMPOSE_PROJECT',
        f'moira-test-{uuid4().hex[:12]}',
    )
    pytest_args = sys.argv[1:]

    try:
        _run(_compose_command(project_name, 'up', '-d', SERVICE_NAME))
        _wait_until_ready(project_name)
        env = _integration_env(_host_port(project_name))

        _run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=env)
        tests = _run(
            [sys.executable, '-m', 'pytest', '-m', 'integration', *pytest_args],
            env=env,
            check=False,
        )
        return tests.returncode
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Integration test setup failed: {error}', file=sys.stderr)
        return 1
    finally:
        _run(
            _compose_command(project_name, 'down', '-v', '--remove-orphans'),
            check=False,
        )


if __name__ == '__main__':
    raise SystemExit(main())
