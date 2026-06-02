# Moira

Backend do SaaS de agendamento Moira.

## Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x async
- Alembic
- Pytest
- Ruff
- Mypy
- Docker Compose
- uv

## Setup local

Instale as ferramentas:

- Python 3.12
- Git
- Docker Desktop
- uv

Instale as dependencias do projeto:

```powershell
uv sync
```

Crie o arquivo de ambiente local:

```powershell
Copy-Item .env.example .env
```

Suba o PostgreSQL:

```powershell
docker compose up -d postgres
```

Aplique migrations:

```powershell
uv run alembic upgrade head
```

Suba a API:

```powershell
uv run uvicorn app.main:app --reload
```

## Health checks

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Respostas esperadas:

```json
{"status":"ok"}
```

```json
{"status":"ready"}
```

`/health` valida apenas que a aplicacao esta viva. `/ready` tambem valida a conexao com o PostgreSQL.

## Qualidade

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

## Testes

Rodar tudo:

```powershell
uv run pytest
```

Rodar somente unitarios:

```powershell
uv run pytest -m "not integration"
```

Rodar somente integracao:

```powershell
uv run pytest -m integration
```

Os testes de integracao esperam que o PostgreSQL esteja rodando via Docker Compose.

## Alembic

Ver revision atual:

```powershell
uv run alembic current
```

Aplicar migrations:

```powershell
uv run alembic upgrade head
```

Criar nova migration futuramente:

```powershell
uv run alembic revision -m "describe change"
```

Quando os models SQLAlchemy forem criados, o `target_metadata` do Alembic devera apontar para `Base.metadata`.

## Fonte de verdade

As decisoes de produto e arquitetura deste backend seguem o documento
[Livedoc - SaaS de Agendamento MVP](https://docs.google.com/document/d/1JV_6vdwBUYo6V1Pj9qsVaRVxhXeZv_ZDWFQVpfXgdb4) e as
[Architecture Decision Records](docs/adr/README.md).
