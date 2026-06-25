# Task — Consolidar e conduzir o backlog da revisão geral

Status: done

## Restrição de overhead local

As tasks derivadas deste backlog devem preservar uma experiência local leve:
rodar a aplicação, linters e testes rápidos não pode passar a depender de
serviços externos, Docker, observabilidade distribuída, Redis obrigatório ou
integrações remotas. Quando uma validação pesada for necessária, ela deve ser
opt-in, documentada e isolada de `uv run pytest -m "not integration"`, `uv run
ruff check .`, `uv run mypy app tests/unit` e do boot local padrão da API.

## Objetivo

Registrar o diagnóstico técnico de 2026-06-24 e transformar os achados em uma
sequência executável de refatorações, sem misturar correções funcionais,
mudanças arquiteturais e melhorias operacionais em uma única entrega.

## Estado verificado

- O livedoc aponta como checkpoint mais recente a correção do CI da PR #16 e
  registra 101 testes unitários/não-integração e 41 de integração.
- `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy app tests/unit` e `uv run pytest -m "not integration" -q`
  passam no estado local; permanece o warning conhecido do handler OTLP.
- Os routers estão majoritariamente finos e os módulos estão organizados por
  domínio, coerentemente com o ADR 0010.
- A aplicação depende diretamente de models SQLAlchemy em seus ports e use
  cases; portanto, a separação hexagonal declarada é parcial.
- `app/api/deps.py` concentra 509 linhas de composição de todos os módulos.
- O scheduling usa datetimes locais sem aplicar efetivamente
  `providers.timezone`; regras sobrepostas podem devolver slots duplicados.
- CORS e timezone padrão existem na configuração, mas CORS não é instalado e o
  timezone do provider não governa o cálculo de agenda.
- Há configuração e colunas preparatórias ainda sem comportamento associado;
  isso deve ser explicitado ou removido, evitando interfaces de intenção falsa.

## Ordem de implementação

1. `01-fix-scheduling-timezone-and-slot-semantics.md`
2. `02-harden-booking-transaction-and-conflict-handling.md`
3. `03-strengthen-database-integrity-and-query-indexes.md`
4. `04-decouple-application-core-from-sqlalchemy-models.md`
5. `05-split-request-container-by-module.md`
6. `06-centralize-http-error-translation.md`
7. `07-align-runtime-configuration-with-actual-behavior.md`
8. `08-add-architecture-and-regression-quality-gates.md`
9. `logging-hardening.md`
10. `09-sync-general-review-to-livedoc.md`

Cada task deve ser implementada em mudança pequena e revisável. Tasks 4 e 5
podem ser migradas módulo a módulo, mas cada incremento precisa manter testes e
contratos HTTP verdes.

## Resultado

O backlog foi criado em ordem de dependência e risco. Nenhuma alteração de
runtime foi feita durante esta revisão. A escrita do checkpoint no livedoc foi
bloqueada pelo controle de segurança do conector por falta de autorização
explícita para enviar a análise do repositório ao documento externo; a
sincronização ficou registrada como follow-up, sem tentativa de contorno.
