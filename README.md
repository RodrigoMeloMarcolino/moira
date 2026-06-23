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

Suba o PostgreSQL e o Redis local:

```powershell
docker compose up -d postgres redis
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

## Logging estruturado

A aplicacao emite um evento por linha em `stdout`. O formato padrao e JSON e
segue um contrato compativel com o OpenTelemetry Logs Data Model. Toda resposta
HTTP inclui `X-Request-ID` e `X-Correlation-ID`; um `X-Correlation-ID` valido
recebido do chamador e preservado.

Configuracao principal:

```text
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_EXPORTERS=stdout
OTEL_SERVICE_NAME=moira
```

Para desenvolvimento local, `LOG_FORMAT=console` produz uma saida legivel com
os mesmos nomes de evento e atributos. Para exportar em batch via OTLP/HTTP:

```text
LOG_EXPORTERS=stdout,otlp
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://localhost:4318/v1/logs
OTEL_EXPORTER_OTLP_HEADERS=
OTEL_EXPORTER_OTLP_TIMEOUT=5
```

`stdout` permanece obrigatorio. Falhas remotas do exporter nao afetam requests
nem readiness. Headers OTLP, credenciais, tokens, payloads, dados pessoais,
URLs de banco/cache e chaves de idempotencia nunca devem ser registrados.

O access log proprio do Moira substitui `uvicorn.access`, evitando duplicidade.
Os campos `event_name`, `request.id`, `correlation.id` e IDs de dominio sao
metadata estruturada, nao labels do Loki.

### Pipeline local Collector, Loki e Grafana

Suba a stack de observabilidade separadamente:

```powershell
docker compose -f docker-compose.observability.yaml up -d
```

Inicie a API com `LOG_EXPORTERS=stdout,otlp`. O Collector recebe OTLP em
`localhost:4318`, o Loki responde em `localhost:3100` e o Grafana em
`http://localhost:3000` (`admin`/`admin` apenas para desenvolvimento).

Uma consulta LogQL por correlacao pode usar:

```logql
{service_name="moira"} | correlation_id="operation-123"
```

Com a API e a stack ativas, valide o caminho completo por meio do proxy de data
source do Grafana:

```powershell
uv run python scripts/smoke_observability.py
```

Cada ambiente deve escolher OTLP direto ou coleta de `stdout` para um mesmo
backend, nunca os dois, para evitar ingestao duplicada.

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
usa `docker-compose.test.yaml` para subir um PostgreSQL e um Redis efemeros, aplica as
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
