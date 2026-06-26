# Especificação — logging estruturado e correlação de requisições

Status: implementado; hardening operacional validado em Docker

Modo: implementação assistida por IA

## Objetivo

Adicionar logging estruturado ao Moira com cobertura dos limites técnicos e dos
fluxos de negócio mais críticos, permitindo responder com rapidez:

- qual requisição falhou e em qual rota;
- qual etapa crítica do fluxo foi concluída, rejeitada ou entrou em conflito;
- quais dependências técnicas estavam degradadas;
- quais entidades foram afetadas, sem registrar dados pessoais ou credenciais;
- quanto tempo a requisição levou e qual status HTTP foi devolvido;
- exportar os mesmos eventos para Grafana Loki ou outro backend distribuído sem
  alterar routers, use cases ou o catálogo de eventos.

## Contexto atual

- `LOG_LEVEL` já existe em `Settings`, mas ainda não configura o logging.
- O Uvicorn mantém seus logs padrão, sem contrato de campos do Moira.
- Não existe `request_id` nem `correlation_id` na aplicação.
- O adaptador Redis possui warnings em texto livre e é o único ponto com logging
  explícito.
- Exceções HTTP conhecidas têm envelope padronizado, mas exceções inesperadas
  ainda não possuem resposta `500` e evento estruturado definidos pelo projeto.
- O fluxo de booking concentra idempotência, disponibilidade, transação e defesa
  contra double booking; ele é o principal fluxo a observar.
- O checkpoint mais recente do livedoc descreve o cache em PR draft, enquanto o
  repositório já contém o merge do PR 15 em `main` (`3fa3fbb`).

## Escopo

### Incluído

- configuração central do logging;
- saída JSON Lines em `stdout`;
- formato legível opcional para desenvolvimento local;
- contexto de requisição com `request_id` e `correlation_id`;
- access log HTTP estruturado, sem duplicidade com `uvicorn.access`;
- tratamento e logging de exceções inesperadas;
- eventos de negócio nos fluxos críticos;
- eventos de degradação de PostgreSQL e Redis;
- contrato lógico compatível com o OpenTelemetry Logs Data Model;
- composição plugável de exporters `stdout` e OTLP;
- configuração de referência com OpenTelemetry Collector, Loki e Grafana;
- identidade de serviço e regras de cardinalidade reutilizáveis por uma futura
  instrumentação Prometheus;
- testes de formato, contexto, correlação, níveis e proteção de dados;
- teste de contrato do exporter e smoke test opcional do pipeline distribuído;
- documentação operacional das variáveis e do catálogo de eventos.

### Fora do escopo

- implementação de métricas, endpoint `/metrics` e scrape pelo Prometheus nesta
  entrega;
- criação de spans, tracing distribuído e propagação de `traceparent`;
- SDK ou API proprietária de Grafana, Datadog, Elastic, CloudWatch ou outro
  fornecedor dentro da aplicação;
- dashboards, alertas e política de retenção;
- operação e alta disponibilidade do collector/backend em produção;
- auditoria legal ou trilha imutável de alterações;
- logging de queries SQL, payloads HTTP ou cache hit/miss em `INFO`;
- alteração dos contratos de negócio ou das regras transacionais.

## Decisões técnicas

### Biblioteca e dependências

Usar `logging` da biblioteca padrão como API consumida pela aplicação. Não
adicionar `structlog`, `loguru` nem SDK proprietário de fornecedor.

Adicionar o OpenTelemetry SDK e o exporter OTLP/HTTP somente na infraestrutura
para o modo opcional `otlp`. As versões serão fixadas no `uv.lock`; a API de
logging dos use cases não dependerá de tipos OpenTelemetry.

Motivos:

- o escopo da aplicação cabe em records do `logging`, formatter, contexto e
  middleware;
- handlers são o ponto natural de extensão para `stdout` e OTLP;
- OTLP fornece transporte neutro para collectors e backends diferentes;
- o exporter pode evoluir sem alterar o catálogo de eventos.

### Limites arquiteturais

- `app/shared/infrastructure/observability/logging/` conterá somente mecanismos
  genéricos de logs: configuração, formatter, contexto e exporters.
- Uma futura integração Prometheus ficará em
  `app/shared/infrastructure/observability/metrics/`, sem transformar logging
  em uma abstração genérica para todos os sinais.
- `app/api/middleware/request_logging.py` será responsável pelo limite HTTP:
  IDs, tempo de execução, status e resposta `500` inesperada.
- Use cases críticos registrarão eventos pertencentes ao próprio módulo usando
  `logging.getLogger(__name__)` e `extra`.
- O domínio continuará sem imports ou conhecimento de logging.
- Routers não duplicarão eventos já emitidos pelo middleware ou use case.
- O logger/exporter não será injetado no `RequestContainer`; isso evita uma
  cascata de dependências por todos os módulos.
- A composição `stdout`/OTLP ocorrerá uma vez no composition root. Nenhum módulo
  de negócio conhecerá Loki, Grafana, Collector, endpoints ou credenciais.
- Cache keys, políticas de cache e detalhes de cada domínio continuarão em seus
  módulos donos. O logging compartilhado não poderá virar um registro central de
  políticas de negócio.
- Métricas de domínio futuras serão definidas pelo módulo dono do comportamento;
  `shared` poderá conter apenas provider, registry e primitives técnicas.

### Contrato portátil e destinos

O `LogRecord` do Python é o formato interno. Cada handler adapta esse record
para um destino:

```text
use cases / middleware
        -> logging.LogRecord
             -> stdout JSON
             -> OTLP/HTTP batch exporter -> Collector/Alloy -> backend
```

Regras:

- `stdout` é obrigatório e funciona como fallback operacional.
- Produção emite um objeto JSON por linha em `stdout`, codificado em UTF-8.
- Desenvolvimento pode usar `LOG_FORMAT=console`, mantendo nomes e atributos.
- `otlp` é opcional e pode ser ativado junto de `stdout`.
- O endpoint OTLP recomendado é um OpenTelemetry Collector ou Grafana Alloy,
  não uma API proprietária chamada diretamente pelo core.
- O collector decide se envia para Loki, Grafana Cloud, Elastic, Datadog,
  CloudWatch ou múltiplos destinos.
- O exporter OTLP usa batch e fila limitada; nenhuma requisição HTTP da
  aplicação aguarda uma chamada de rede de logging.
- Indisponibilidade remota não altera a resposta da aplicação nem `/ready`.
- Configuração OTLP inválida ou incompleta falha no startup quando o exporter
  foi explicitamente habilitado; indisponibilidade após o startup é fail-open.
- Em um ambiente, escolher somente uma rota de ingestão para cada evento: se a
  aplicação envia OTLP diretamente, o collector não deve reingerir o mesmo
  `stdout`, evitando duplicidade.
- Timestamps sempre em UTC, no formato RFC 3339 com precisão de milissegundos.
- O formatter deve serializar com segurança `UUID`, `date`, `datetime`, enums e
  valores desconhecidos, sem causar falha na requisição.
- `uvicorn.error` deve propagar para a configuração central.
- `uvicorn.access` deve ser desativado quando o access log do Moira estiver
  ativo, evitando duas linhas para a mesma requisição.

### Configuração

Variáveis:

| Variável | Valores | Padrão | Regra |
| --- | --- | --- | --- |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` | normalizar para maiúsculas e rejeitar valor inválido no startup |
| `LOG_FORMAT` | `json`, `console` | `json` | `console` é destinado ao desenvolvimento local |
| `LOG_EXPORTERS` | `stdout` ou `stdout,otlp` | `stdout` | `stdout` é obrigatório no MVP |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | URL HTTP(S) | vazio | obrigatório quando `otlp` estiver habilitado |
| `OTEL_EXPORTER_OTLP_HEADERS` | headers codificados conforme OTLP | vazio | secret; nunca registrar |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | segundos positivos | `5` | timeout do exporter, não da request |
| `OTEL_SERVICE_NAME` | string | valor de `APP_NAME` | recurso `service.name` |

Não haverá configuração para habilitar logging de dados sensíveis.

### Contexto HTTP

Para cada requisição:

1. gerar um `request_id` UUID novo no servidor;
2. aceitar `X-Correlation-ID` válido do chamador;
3. na ausência dele, aceitar `X-Request-ID` válido apenas como correlação;
4. se nenhum for válido, usar o novo `request_id` também como `correlation_id`;
5. aceitar somente `[A-Za-z0-9._:-]`, com 1 a 128 caracteres;
6. devolver `X-Request-ID` e `X-Correlation-ID` na resposta;
7. disponibilizar ambos via `ContextVar` durante toda a requisição;
8. limpar os contextos em `finally`, inclusive em erro e cancelamento.

O `request_id` identifica uma execução. O `correlation_id` agrupa uma operação
que pode atravessar retries e, futuramente, outros serviços.

### Access log

Emitir exatamente um evento terminal por requisição:

- `http.request.completed` para uma resposta HTTP conhecida;
- `http.request.failed` para exceção inesperada convertida em `500`.

Campos específicos:

- `http.request.method`;
- `http.route`, usando o template da rota e nunca a query string;
- `http.response.status_code`;
- `duration_ms`;
- `request.id`;
- `correlation.id`.

Para rotas não reconhecidas, usar `http.route="unmatched"`. Não registrar o
path bruto para evitar exposição futura de tokens em URLs.

Requisições bem-sucedidas a `/v1/health` e `/v1/ready` ficam em `DEBUG` para não
dominar os logs. Falhas de readiness permanecem em `WARNING`.

### Resposta para erro inesperado

Uma exceção não tratada deve:

- gerar `http.request.failed` em `ERROR`, uma única vez;
- manter `request_id` e `correlation_id` no evento e nos headers;
- devolver status `500` com o envelope:

```json
{
  "error": {
    "code": "internal_server_error",
    "message": "internal server error",
    "details": null
  }
}
```

- não expor classe, mensagem interna, SQL ou stack trace ao cliente.

### Níveis

| Nível | Uso |
| --- | --- |
| `DEBUG` | health/readiness bem-sucedidos, cache hit/miss e detalhes diagnósticos desabilitados por padrão |
| `INFO` | requisição concluída, operação crítica concluída, replay idempotente e rejeição de negócio esperada |
| `WARNING` | acesso proibido, conflito de idempotência, double booking, dependência degradada e payload de cache inválido |
| `ERROR` | exceção inesperada, falha de startup ou violação de invariante sem recuperação segura |
| `CRITICAL` | falha que impede o processo de iniciar ou continuar; não usar para erros comuns de requisição |

Status `4xx` não sobe automaticamente o access log para `WARNING`. O evento de
negócio específico define o nível e evita transformar erros esperados em ruído.

## Esquema canônico

O esquema lógico segue o OpenTelemetry Logs Data Model. O JSON de `stdout` e o
exporter OTLP devem representar a mesma informação:

| Campo lógico | JSON `stdout` | OTLP | Descrição |
| --- | --- | --- | --- |
| Timestamp | `timestamp` | `Timestamp` | UTC/RFC 3339 no JSON |
| SeverityText | `severity_text` | `SeverityText` | nível original normalizado |
| SeverityNumber | `severity_number` | `SeverityNumber` | faixa OTLP correspondente |
| Body | `body` | `Body` | descrição humana curta |
| EventName | `event_name` | `EventName` | nome estável `dominio.acao_resultado` |
| Resource | `resource` | `Resource` | identidade estável do serviço |
| Attributes | `attributes` | `Attributes` | contexto variável do evento |
| TraceId | `trace_id` opcional | `TraceId` | reservado para tracing futuro |
| SpanId | `span_id` opcional | `SpanId` | reservado para tracing futuro |

Resource attributes mínimos:

- `service.name`;
- `service.namespace=moira`;
- `service.version` quando disponível no build;
- `deployment.environment.name`;
- `service.instance.id` quando fornecido pelo runtime.

Attributes condicionais:

- `request.id`, `correlation.id` em contexto HTTP;
- `provider.id`, `offering.id`, `appointment.id`, `rule.id`, `user.id` quando
  conhecidos e necessários;
- `reason` como categoria estável;
- `duration_ms` para operações temporizadas;
- atributos semânticos HTTP, como `http.request.method`, `http.route` e
  `http.response.status_code`;
- `exception.type` e stack trace sanitizado para falhas inesperadas.

`request.id` e `correlation.id` não devem ser convertidos em `TraceId`. Quando
tracing for implementado, os três identificadores coexistirão com semânticas
distintas.

Nomes de evento e atributos fazem parte do contrato operacional. Mensagens
humanas podem evoluir; testes e consultas dependem de `event_name`, `reason` e
IDs.

### Mapeamento para Grafana Loki

- Usar OTLP/HTTP por meio do Collector/Alloy; Loki possui endpoint OTLP nativo.
- `service.name`, `service.namespace` e `deployment.environment.name` podem ser
  labels de baixa cardinalidade.
- `request.id`, `correlation.id`, IDs de domínio, `event_name`, rota e detalhes
  de exceção permanecem structured metadata, não index labels.
- O collector deve controlar explicitamente a promoção de labels.
- Pontos em nomes OTLP são normalizados para underscore no Loki; consultas Loki
  usam, por exemplo, `service_name` e `request_id`.
- `allow_structured_metadata` deve estar habilitado no Loki de referência.

### Preparação para Prometheus futuro

Logs e métricas são sinais diferentes. Esta entrega não deve tentar derivar
métricas lendo logs nem usar labels Prometheus como atributos obrigatórios dos
eventos.

Diretrizes já congeladas para a etapa futura:

- Prometheus fará scrape de um endpoint `/metrics` dedicado, fora do prefixo de
  negócio `/v1`.
- A exposição pública do endpoint não será presumida; rede, autenticação ou
  proxy de observabilidade serão definidos no deploy.
- Métricas reutilizarão a identidade estável `service.name`,
  `service.namespace` e `deployment.environment.name`.
- Nomes usarão snake_case, unidade base e sufixos Prometheus convencionais,
  como `_total`, `_seconds` e `_bytes`.
- Labels aceitarão apenas conjuntos limitados, como template de rota, método,
  classe de status, outcome, reason, dependency, operation e cache namespace.
- Nunca serão labels: `request.id`, `correlation.id`, trace/span ids, IDs de
  domínio, slug, path bruto, mensagem de exceção, e-mail, telefone ou qualquer
  valor fornecido livremente pelo usuário.
- Histograms de duração terão buckets definidos por comportamento observado;
  não serão criadas séries por ID ou timestamp.
- A indisponibilidade do scraper Prometheus não afetará requests nem readiness.

Primeiro catálogo candidato, a ser refinado em tarefa própria:

- `moira_http_requests_total`;
- `moira_http_request_duration_seconds`;
- `moira_appointment_bookings_total`;
- `moira_cache_operations_total`;
- `moira_dependency_ready`;
- `moira_log_exporter_dropped_records_total`.

A biblioteca, buckets, segurança do endpoint e integração direta versus
OpenTelemetry Metrics exigirão uma especificação e ADR próprios antes da
implementação.

## Política de dados sensíveis

Nunca registrar:

- senha, hash de senha, JWT, header `Authorization` ou cookies;
- telefone, e-mail, nome de customer/provider ou notas;
- payload ou corpo completo de requisição/resposta;
- valor de `Idempotency-Key` ou fingerprint;
- `DATABASE_URL`, `REDIS_URL` ou outros secrets;
- query string completa;
- valor armazenado no cache;
- parâmetros SQL.

É permitido registrar IDs técnicos, slug público, data/horário do slot e a
presença booleana de uma chave de idempotência.

O formatter deve redigir recursivamente chaves conhecidas como `password`,
`token`, `authorization`, `cookie`, `email`, `phone`, `notes`,
`idempotency_key`, `idempotency.key`, `database_url`, `database.url`,
`redis_url` e `redis.url`. Essa defesa não substitui a regra de não enviar esses
valores ao logger.

## Catálogo de eventos

### Fundação e infraestrutura — P0

| Evento | Nível | Campos principais | Emissor |
| --- | --- | --- | --- |
| `application.started` | `INFO` | `service.name`, `deployment.environment.name`, `log_format`, `log_exporters`, `cache_backend` | lifespan |
| `application.stopped` | `INFO` | `service.name`, `deployment.environment.name` | lifespan |
| `cache.backend_ready` | `INFO` | `backend=redis` | adapter Redis |
| `cache.backend_degraded` | `WARNING` | `reason`, `operation` opcional | adapter Redis |
| `cache.payload_invalid` | `WARNING` | `cache_namespace`, `reason` | cache do módulo dono |
| `readiness.dependency_failed` | `WARNING` | `dependency=postgresql`, `reason` | health adapter/router |
| `http.request.completed` | `DEBUG/INFO` | método, rota, status, duração | middleware |
| `http.request.failed` | `ERROR` | método, rota, status, duração, exceção sanitizada | middleware |

Falhas de operação Redis devem registrar `cache_namespace` (`public_provider`,
`public_offerings`, `available_slots`, `schedule_version` ou `day_version`) em
vez da cache key completa.

### Booking público — P0

| Evento | Nível | Campos principais |
| --- | --- | --- |
| `appointment.booking_succeeded` | `INFO` | `appointment.id`, `provider.id`, `offering.id`, `appointment.start_at`, `offering.duration_minutes`, `idempotency.provided` |
| `appointment.booking_replayed` | `INFO` | `appointment.id`, `provider.id`, `offering.id`, `idempotency.provided=true` |
| `appointment.booking_rejected` | `INFO` | IDs conhecidos, `reason=provider_not_found|offering_not_found|offering_mismatch|invalid_start|outside_availability` |
| `appointment.booking_conflict` | `WARNING` | IDs conhecidos, `reason=slot_conflict|idempotency_mismatch` |

Regras:

- sucesso só é emitido depois do commit;
- replay é diferente de novo sucesso;
- conflito transacional é emitido depois do rollback;
- falha de invalidação de cache permanece evento do adapter, pois não desfaz o
  booking já confirmado;
- não registrar customer, payload ou chave de idempotência.

### Autenticação e cadastro — P0

| Evento | Nível | Campos principais |
| --- | --- | --- |
| `auth.login_succeeded` | `INFO` | `user.id`, `provider.id` |
| `auth.login_rejected` | `INFO` | `reason=user_not_found|password_mismatch|provider_not_found` |
| `auth.access_rejected` | `INFO/WARNING` | `reason=missing_credentials|invalid_token|user_not_found|provider_not_found` |
| `provider.signup_succeeded` | `INFO` | `user_id`, `provider_id` |
| `provider.signup_rejected` | `INFO/WARNING` | `reason=email_exists|slug_conflict_exhausted` |

`auth.access_rejected` usa `WARNING` apenas para ownership/acesso proibido; token
ausente ou inválido permanece `INFO` para reduzir ruído e limitar log flooding.

### Mutações administrativas — P1

| Evento | Nível | Campos principais |
| --- | --- | --- |
| `offering.created` | `INFO` | `provider.id`, `offering.id` |
| `offering.updated` | `INFO` | `provider.id`, `offering.id`, `changed_fields`, `schedule_changed` |
| `offering.update_rejected` | `INFO/WARNING` | IDs conhecidos, `reason=not_found|access_forbidden` |
| `availability_rule.created` | `INFO` | `provider.id`, `rule.id`, `weekday` |
| `availability_rule.updated` | `INFO` | `provider.id`, `rule.id`, `changed_fields` |
| `availability_rule.update_rejected` | `INFO/WARNING` | IDs conhecidos, `reason=not_found|access_forbidden` |

Leituras públicas de catálogo e slots não geram evento de negócio em `INFO`.
Se necessário durante diagnóstico, cache hit/miss e quantidade de slots podem ser
habilitados em `DEBUG`.

## Plano de implementação

### Fase 1 — Fundação

1. Adicionar e validar `LOG_FORMAT`, `LOG_LEVEL` e `LOG_EXPORTERS`.
2. Criar `app/shared/infrastructure/observability/logging/` com:
   - `JsonFormatter` alinhado ao esquema canônico;
   - serialização e redação segura;
   - contexto por `ContextVar`;
   - composição idempotente de handlers;
   - adapter OTLP/HTTP com batch e shutdown limitado.
3. Manter `stdout` obrigatório e habilitar OTLP somente por configuração.
4. Atualizar `.env.example` e README com variáveis e exemplos.
5. Converter os warnings atuais de Redis para eventos estruturados.

### Fase 2 — Limite HTTP

1. Criar middleware ASGI puro em `app/api/middleware/request_logging.py`.
2. Implementar validação, geração, propagação e limpeza dos IDs.
3. Emitir access log por template de rota e duração monotônica.
4. Padronizar a resposta `500` sem vazar detalhes.
5. Registrar middleware e configuração em `app/main.py`.
6. Registrar falha de readiness sem logar sucesso em `INFO`.

Usar middleware ASGI puro evita os efeitos de buffering e propagação de contexto
associados a `BaseHTTPMiddleware`.

### Fase 3 — Eventos críticos

1. Instrumentar `BookPublicAppointmentUseCase` em todos os caminhos terminais.
2. Instrumentar `LoginProviderUseCase` e `get_current_provider`.
3. Instrumentar `SignupProviderUseCase`.
4. Instrumentar create/update de offering e availability rule.
5. Converter payload inválido dos caches de domínio em warning estruturado.
6. Revisar cada caminho para garantir um único evento de resultado e ausência de
   PII.

### Fase 4 — Pipeline distribuído de referência

1. Adicionar `docker-compose.observability.yaml` com OpenTelemetry Collector,
   Loki e Grafana, fora do compose básico da aplicação.
2. Configurar receiver OTLP/HTTP no collector e exporter `otlphttp` para o
   endpoint `/otlp` do Loki.
3. Configurar Loki com structured metadata habilitado.
4. Provisionar o data source Loki no Grafana.
5. Documentar uma consulta por `event_name` e `correlation_id`, considerando a
   normalização de pontos realizada pelo Loki.
6. Garantir que IDs de alta cardinalidade não sejam labels.
7. Manter a composição preparada para receber Prometheus como serviço e data
   source em um perfil futuro, sem adicioná-lo ao escopo desta entrega.

### Fase 5 — Validação e documentação

1. Adicionar testes unitários do formatter, configuração e middleware.
2. Adicionar asserts de eventos aos testes unitários dos use cases críticos.
3. Adicionar testes de contrato para `stdout` e exporter OTLP.
4. Adicionar testes de integração para headers, correlação e erro `500`.
5. Adicionar smoke test opt-in do pipeline Collector -> Loki -> Grafana.
6. Atualizar README e livedoc com contrato, validação e riscos restantes.

## Arquivos previstos

### Novos

- `app/shared/infrastructure/observability/__init__.py`
- `app/shared/infrastructure/observability/logging/__init__.py`
- `app/shared/infrastructure/observability/logging/context.py`
- `app/shared/infrastructure/observability/logging/formatters.py`
- `app/shared/infrastructure/observability/logging/setup.py`
- `app/shared/infrastructure/observability/logging/otlp.py`
- `app/api/middleware/__init__.py`
- `app/api/middleware/request_logging.py`
- `tests/unit/shared/infrastructure/observability/logging/test_formatters.py`
- `tests/unit/shared/infrastructure/observability/logging/test_setup.py`
- `tests/unit/shared/infrastructure/observability/logging/test_otlp.py`
- `tests/unit/api/middleware/test_request_logging.py`
- `docker-compose.observability.yaml`
- `observability/otel-collector.yaml`
- `observability/loki.yaml`
- `observability/grafana/provisioning/datasources/loki.yaml`
- `docs/adr/0015-use-vendor-neutral-structured-logging-and-otlp.md`

### Alterados

- `app/config.py`
- `app/main.py`
- `app/database.py`
- `app/api/deps.py`
- `app/modules/appointments/application/use_cases.py`
- `app/modules/auth/application/use_cases.py`
- `app/modules/providers/application/use_cases.py`
- `app/modules/offerings/application/use_cases.py`
- `app/modules/availability/application/use_cases.py`
- caches de aplicação dos módulos e `app/shared/infrastructure/cache.py`
- `.env.example`
- `pyproject.toml`
- `uv.lock`
- `README.md`
- `docs/adr/README.md`
- testes unitários e de integração correspondentes

## Estratégia de testes

### Unitários

- JSON emitido é válido e contém o esquema canônico;
- o mesmo `LogRecord` preserva `event_name`, resource e attributes em `stdout`
  e OTLP;
- UUID, datas e exceções não quebram serialização;
- campos sensíveis são redigidos;
- configuração repetida não duplica handlers;
- `LOG_LEVEL` e `LOG_FORMAT` inválidos falham na configuração;
- cada request recebe `request_id` novo;
- correlação válida é preservada e valor inválido é substituído;
- headers são devolvidos em `2xx`, `4xx` e `500`;
- contexto é limpo entre requisições concorrentes;
- rota usa template e não query string;
- erro inesperado gera um único `http.request.failed` e envelope seguro;
- Uvicorn access log não duplica o evento;
- habilitar `stdout,otlp` cria os dois handlers uma única vez;
- endpoint OTLP ausente falha na configuração quando `otlp` foi solicitado;
- envio OTLP usa batch e não realiza I/O de rede na coroutine da request;
- falha remota preserva `stdout`, não altera `/ready` e não cria recursão de
  logs internos do exporter;
- booking emite eventos distintos para sucesso, replay e conflito;
- testes negativos garantem ausência de senha, JWT, e-mail, telefone, notes e
  `Idempotency-Key` no texto capturado.

### Integração

- booking bem-sucedido inclui os mesmos IDs de correlação no log e resposta;
- retry idempotente emite `appointment.booking_replayed`;
- payload diferente com a mesma chave emite conflito sem registrar a chave;
- double booking emite conflito após rollback;
- login inválido emite categoria sem registrar e-mail/senha;
- Redis indisponível mantém fallback e emite degradação;
- readiness de PostgreSQL indisponível devolve `503` e warning correlacionado;
- rota de teste que lança exceção comprova o contrato `500` sem criar endpoint
  de produção;
- receiver OTLP falso comprova o payload sem exigir fornecedor externo;
- smoke test opt-in comprova ingestão no Loki e consulta pelo Grafana;
- teste de configuração comprova que IDs de alta cardinalidade ficam como
  structured metadata.

### Comandos de validação

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests/unit
uv run pytest -m "not integration"
uv run python scripts/run_integration_tests.py
```

## Critérios de aceite

- Todo log da aplicação é estruturado conforme `LOG_FORMAT`.
- O schema é mapeável sem perda relevante para o OpenTelemetry Logs Data Model.
- `LOG_EXPORTERS=stdout` opera sem OpenTelemetry remoto.
- `LOG_EXPORTERS=stdout,otlp` exporta em batch para um endpoint OTLP genérico.
- Trocar Loki por outro backend compatível exige somente configuração de
  collector/exporter, sem mudança nos módulos de negócio.
- Toda resposta HTTP possui `X-Request-ID` e `X-Correlation-ID`.
- Existe exatamente um access log terminal por requisição.
- Exceções inesperadas geram `500` seguro e `ERROR` correlacionado.
- Booking, login e signup possuem eventos de sucesso e rejeição/conflito.
- Mutações de offering e availability possuem eventos após commit.
- Redis/PostgreSQL degradados podem ser diagnosticados pelos eventos definidos.
- Logs não contêm os dados sensíveis enumerados nesta especificação.
- IDs de requisição, correlação e domínio não são index labels no Loki.
- O desenho não exige usar IDs de alta cardinalidade como labels Prometheus
  quando métricas forem adicionadas.
- Indisponibilidade do collector/backend não afeta requests nem readiness.
- A aplicação continua funcionando com cache desabilitado ou Redis indisponível.
- Ruff, format, Mypy, testes unitários e integração passam.

## Riscos e mitigação

- **Duplicação de logs:** centralizar access log no middleware e desativar
  `uvicorn.access`.
- **PII em exceções:** usar categorias estáveis, não logar payloads e sanitizar
  exceções inesperadas.
- **Ruído e custo:** health/readiness de sucesso e cache hit/miss ficam em
  `DEBUG`; erros esperados não viram `ERROR`.
- **Alta cardinalidade:** não registrar path bruto, query string, cache key
  completa ou idempotency key.
- **Falha do formatter:** serialização possui fallback seguro e nunca interrompe
  o fluxo de negócio.
- **Backend distribuído indisponível:** OTLP usa fila/batch limitados, timeout e
  fail-open; `stdout` permanece disponível.
- **Perda de logs por fila cheia:** emitir diagnóstico rate-limited no handler
  local, documentar capacidade e acompanhar futuramente com métrica.
- **Duplicação de ingestão:** cada ambiente escolhe OTLP direto ou coleta de
  `stdout`, nunca ambos para o mesmo backend.
- **Explosão de cardinalidade no Loki:** somente resource attributes estáveis
  viram labels; IDs e eventos ficam em structured metadata.
- **Maturidade do OTel Logs SDK Python:** fixar versões, esconder o SDK no
  adapter e manter testes de contrato para permitir substituição.
- **Acoplamento entre sinais:** manter logging e métricas em adapters irmãos;
  compartilhar somente identidade estável do serviço e contexto neutro.
- **Acoplamento transversal:** não injetar logger em todos os use cases nem
  centralizar eventos de vários domínios em um serviço compartilhado.

## Hardening operacional — 2026-06-26

O runtime de logging foi endurecido sem alterar o contrato público de logs.

- O handler OTLP depreciado do pacote `opentelemetry.sdk._logs` foi substituído
  pelo handler suportado de `opentelemetry-instrumentation-logging`.
- A integração OTLP continua isolada no adapter de infraestrutura e preserva
  `event_name`, resource, attributes, redaction, batching, timeout e fail-open.
- O ciclo de vida deixou de depender de `_active_runtime`: cada aplicação encerra
  apenas o `LoggingRuntime` armazenado em seu próprio `app.state`.
- `shutdown()` é idempotente e não remove handlers pertencentes a uma instância
  mais nova da aplicação no mesmo processo.
- A validação Docker Collector -> Loki -> Grafana foi executada com sucesso via
  `scripts/smoke_observability.py`, com ingestão consultada pelo proxy do
  Grafana usando `correlation_id`.

Validação executada:

```powershell
uv run pytest tests/unit/shared/infrastructure/observability/logging -q -p no:cacheprovider
uv run pytest tests/unit/api/middleware/test_request_logging.py -q -p no:cacheprovider
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests/unit
uv run pytest -m "not integration" -q -p no:cacheprovider
uv run python scripts/run_integration_tests.py
docker compose -f docker-compose.observability.yaml up -d
uv run python scripts/smoke_observability.py
docker compose -f docker-compose.observability.yaml down
```

O README e o ADR 0015 não exigiram alteração: comandos, variáveis de ambiente,
contrato operacional e decisão arquitetural permaneceram os mesmos.

## ADR e follow-ups

A interoperabilidade OTLP e a regra de manter fornecedores fora do core são uma
decisão arquitetural nova. O ADR 0015 deve registrar:

- `logging` padrão como API interna;
- schema lógico alinhado ao OpenTelemetry Logs Data Model;
- `stdout` obrigatório e OTLP opcional;
- collector como fronteira de roteamento para backends;
- fail-open, batch, cardinalidade e proteção de dados;
- proibição de SDK proprietário nos módulos de negócio.

Sincronização do livedoc: a leitura do checkpoint foi concluída no início e no
fim da implementação. A tentativa de escrita no Google Docs foi recusada pelo
conector por política de segurança contra exportação de detalhes privados do
repositório para destino externo. A sincronização permanece como follow-up e
exige aprovação explícita do usuário no próprio fluxo do conector.

Follow-ups posteriores:

- métricas RED por rota e métricas de booking;
- especificação e ADR de métricas Prometheus, incluindo `/metrics`, nomes,
  labels, buckets, segurança e testes de scrape;
- tracing OpenTelemetry e propagação W3C;
- alertas e SLOs sobre os eventos distribuídos;
- política de retenção e classificação de dados;
- rate limiting e detecção de abuso em autenticação.

## Referências técnicas

- [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)
- [OpenTelemetry Python — Logs](https://opentelemetry.io/docs/languages/python/instrumentation/#logs)
- [Grafana Loki — ingestão de logs via OpenTelemetry Collector](https://grafana.com/docs/loki/latest/send-data/otel/)
- [Prometheus — metric and label naming](https://prometheus.io/docs/practices/naming/)
