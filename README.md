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
curl http://127.0.0.1:8000/v1/health
curl http://127.0.0.1:8000/v1/ready
```

Respostas esperadas:

```json
{"status":"ok"}
```

```json
{"status":"ready"}
```

`/health` valida apenas que a aplicacao esta viva. `/ready` tambem valida a conexao com o PostgreSQL.

## Regras de cadastro

O cadastro inicial de provider (`POST /v1/providers/signup`) aceita senhas de
8 a 64 caracteres.

A senha nunca deve ser retornada pela API. O backend armazena apenas
`users.password_hash`, gerado com bcrypt.

O login do provider e feito em `POST /v1/auth/login`. Endpoints
administrativos exigem `Authorization: Bearer <access_token>`.

## Contratos HTTP

A API atual e exposta somente sob `/v1`.

Rotas publicas para clientes finais ficam sob `/v1/public`, por exemplo:

- `GET /v1/public/providers/{slug}`
- `GET /v1/public/providers/{slug}/offerings`
- `GET /v1/public/providers/{slug}/available-slots`
- `POST /v1/public/providers/{slug}/appointments`

Rotas administrativas autenticadas ficam sob recursos administrativos diretos.
Nelas, o provider alvo e inferido do token bearer, por exemplo:

- `POST /v1/offerings`
- `GET /v1/offerings`
- `PATCH /v1/offerings/{offering_id}`
- `POST /v1/availability-rules`
- `GET /v1/availability-rules`
- `PATCH /v1/availability-rules/{rule_id}`
- `GET /v1/appointments`

Erros HTTP seguem o envelope:

```json
{
  "error": {
    "code": "provider_not_found",
    "message": "provider not found",
    "details": null
  }
}
```

## Qualidade

```powershell
make lint
make test
```

## Testes

Rodar tudo:

```powershell
make test
```

Rodar somente unitarios:

```powershell
make test-unit
```

Rodar somente integracao:

```powershell
make test-integration
```

Em ambientes sem `make`, o runner de integracao pode ser chamado diretamente:

```powershell
uv run python scripts/run_integration_tests.py
```

Os testes de integracao exigem Docker disponivel. O alvo `make test-integration`
usa `docker-compose.test.yaml` para subir um PostgreSQL efemero, aplica as
migrations, executa `pytest -m integration` e remove o container e volumes ao
final da suite. O container local `moira-postgres`, usado via Docker Compose
para desenvolvimento, nao e reutilizado nem alterado pelos testes.

Executar `uv run pytest -m integration` diretamente e bloqueado por seguranca,
porque essa suite precisa receber explicitamente a `DATABASE_URL` efemera criada
pelo comando de teste.

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
