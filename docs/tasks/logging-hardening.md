# Task — endurecer o runtime de logging estruturado

Status: pendente

Prioridade: média

Origem: revisão pós-implementação do logging estruturado

Referências:

- `docs/specs/structured-logging.md`
- `docs/adr/0015-use-vendor-neutral-structured-logging-and-otlp.md`

## Objetivo

Concluir o endurecimento operacional do logging estruturado sem alterar seu
contrato público: JSON em `stdout` permanece obrigatório, OTLP continua opcional
e assíncrono, e os módulos de negócio continuam usando apenas `logging` da
biblioteca padrão.

## Contexto

A implementação atual está funcional e coberta por testes, mas a validação
identificou três pontos de manutenção:

1. `opentelemetry.sdk._logs.LoggingHandler` emite aviso de depreciação e deve ser
   substituído por uma integração suportada pelas versões fixadas no projeto;
2. o runtime ativo é mantido em `_active_runtime` global, o que pode fazer uma
   nova instância da aplicação encerrar os handlers de outra instância no mesmo
   processo;
3. a validação completa do pipeline Collector -> Loki -> Grafana em Docker ainda
   está pendente.

## Escopo

### Incluído

- pesquisar e adotar o substituto suportado para o handler OTLP depreciado;
- preservar `event_name`, atributos, resource, redação de dados sensíveis,
  batching, fila limitada, timeout e comportamento fail-open;
- tornar o ciclo de vida do runtime explícito e seguro para múltiplas chamadas
  de `create_app()` no mesmo processo;
- garantir que `shutdown()` seja idempotente, faça flush limitado e não encerre
  handlers pertencentes a outra aplicação;
- executar o smoke test do pipeline Docker e registrar o resultado;
- atualizar testes, documentação operacional, spec e livedoc com o estado real.

### Fora do escopo

- métricas Prometheus;
- tracing e propagação de `traceparent`;
- novos eventos de negócio;
- alteração do esquema canônico ou dos nomes dos eventos;
- SDK proprietário de Loki, Grafana ou outro fornecedor;
- injeção de logger ou exporter em use cases, routers ou `RequestContainer`.

## Regras arquiteturais

- `app/shared/infrastructure/observability/logging/` deve continuar contendo
  apenas mecanismos genéricos de observabilidade.
- A composição dos handlers ocorre somente no composition root.
- Use cases continuam donos dos eventos de seus respectivos domínios.
- O domínio não deve importar `logging`, OpenTelemetry ou adapters de
  observabilidade.
- A migração não deve criar uma dependência transversal nova nem um registro
  central de políticas de negócio.

## Plano de implementação

### 1. Migrar o handler OTLP

- Confirmar a API recomendada e compatível com as versões OpenTelemetry fixadas
  no `uv.lock`.
- Substituir a herança de `opentelemetry.sdk._logs.LoggingHandler` em
  `app/shared/infrastructure/observability/logging/otlp.py`.
- Manter o mapeamento canônico de `event_name` sem duplicá-lo em attributes.
- Justificar e fixar qualquer dependência nova necessária à integração.
- Adicionar teste que falhe caso a configuração emita `DeprecationWarning` da
  API de logging adotada.

### 2. Isolar o ciclo de vida do runtime

- Remover a dependência funcional de `_active_runtime` global ou limitar seu uso
  estritamente à substituição de handlers pertencentes à mesma configuração.
- Fazer cada `FastAPI` possuir e encerrar apenas o `LoggingRuntime` armazenado em
  seu próprio `app.state`.
- Preservar a proteção contra duplicação de handlers quando a configuração for
  repetida.
- Cobrir duas aplicações criadas no mesmo processo e provar que encerrar uma
  não desativa o logging da outra.
- Cobrir chamadas repetidas de `shutdown()`.

### 3. Validar o pipeline distribuído

- Subir `docker-compose.observability.yaml`.
- Iniciar a API com `LOG_EXPORTERS=stdout,otlp`.
- Executar `uv run python scripts/smoke_observability.py`.
- Confirmar ingestão única, consulta por `correlation_id` e ausência de IDs de
  alta cardinalidade como labels.
- Confirmar que indisponibilidade do destino OTLP não altera requests nem
  readiness e que `stdout` continua disponível.

### 4. Sincronizar documentação

- Atualizar `docs/specs/structured-logging.md` com a migração e a validação
  efetivamente realizadas.
- Atualizar o README apenas se comandos, variáveis ou comportamento operacional
  mudarem.
- Reavaliar o ADR 0015; atualizá-lo somente se a decisão arquitetural mudar, e
  não por mera troca interna de API.
- Atualizar o livedoc referenciado pelo README com implementação, validações,
  riscos restantes e modo de desenvolvimento utilizado.

## Testes e validação

Executar, no mínimo:

```powershell
uv run pytest tests/unit/shared/infrastructure/observability/logging -q
uv run pytest tests/unit/api/middleware/test_request_logging.py -q
uv run ruff check .
uv run mypy app
uv run python scripts/smoke_observability.py
```

Adicionar ou ajustar testes para:

- contrato equivalente entre JSON `stdout` e OTLP;
- ausência do aviso de depreciação do handler;
- configuração repetida sem duplicação;
- isolamento entre duas instâncias da aplicação;
- shutdown idempotente com flush limitado;
- falha remota fail-open;
- preservação da redação de campos sensíveis.

## Critérios de aceitação

- A suíte de logging não emite o `DeprecationWarning` atual.
- O payload OTLP preserva o contrato canônico existente.
- Criar ou encerrar uma aplicação não remove nem fecha handlers pertencentes a
  outra aplicação no mesmo processo.
- `shutdown()` pode ser chamado mais de uma vez sem erro ou bloqueio indefinido.
- O pipeline Collector -> Loki -> Grafana é validado com sucesso em Docker.
- Não há ingestão duplicada pelo mesmo backend.
- Falha do backend remoto não afeta respostas HTTP, readiness ou `stdout`.
- Nenhuma dependência de OpenTelemetry ou fornecedor aparece nos módulos de
  domínio ou nos use cases.
- Spec, documentação operacional e livedoc refletem o resultado executado.

## Riscos e observações

- O SDK de logs do OpenTelemetry ainda evolui; a migração deve ser orientada
  pelas versões fixadas e protegida por teste de contrato.
- Mudanças no ownership de handlers do logger raiz podem interferir no Uvicorn
  e no runner de testes; validar propagação e ausência de access logs duplicados.
- Não marcar a validação Docker como concluída sem executar o smoke test e
  guardar evidência do resultado.

## Definição de pronto

A task estará concluída quando código, testes, validação Docker e documentação
estiverem alinhados, sem aviso de API depreciada e sem interferência de ciclo de
vida entre instâncias da aplicação.
