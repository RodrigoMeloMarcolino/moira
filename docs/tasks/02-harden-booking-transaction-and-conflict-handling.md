# Task — Endurecer a transação e a classificação de conflitos do booking

Status: done on 2026-06-26

## Checkpoint de implementacao - 2026-06-26

Modo: assisted implementation com subagent Worker A e integracao final.

Implementado:

- `UnitOfWorkConflict` passou a carregar `reason`, `category` e
  `constraint_name`, classificados no adapter SQLAlchemy para
  `uq_customers_phone`, `uq_appointment_slots_provider_slot_start` e
  `uq_appointments_provider_idempotency_key`.
- `BookPublicAppointmentUseCase` foi separado em etapas internas de contexto,
  replay idempotente, preparo de slots/disponibilidade e persistencia atomica,
  mantendo o use case como entrada do fluxo.
- Replay/mismatch de idempotencia acontece antes de disponibilidade e antes de
  criar customer, preservando retry seguro.
- Conflito concorrente em `uq_customers_phone` faz rollback e retry limitado,
  permitindo duas reservas com mesmo telefone em slots diferentes.
- Conflito em slot vira `AppointmentBookingConflict`; conflito de idempotencia
  faz replay ou mismatch deterministico; conflito desconhecido vira
  `AppointmentPersistenceConflict` e nao e rotulado como slot indisponivel.
- A resposta e materializada com `refresh` depois do commit; invalidacao de
  cache ocorre depois e e fail-open, sem alterar sucesso ja confirmado.
- `Idempotency-Key` continua opcional, mas quando presente e validado no header
  com 1 a 128 caracteres e somente `A-Z`, `a-z`, `0-9`, `.`, `_`, `:`, `-`.

Validacao executada:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy app tests/unit`
- `uv run pytest -m "not integration" -q`
- `uv run python scripts/run_integration_tests.py`

Resultado integrado: 146 testes nao-integracao passaram, 43 testes de
integracao passaram. Permanece apenas warning local do pytest cache por
permissao de `.pytest_cache` no ambiente Windows.

Livedoc: Google Docs externo nao foi atualizado por falta de autorizacao
explicita; este checkpoint local deve ser sincronizado na task 09.

## Restrição de overhead local

As mudanças transacionais e de concorrência não devem tornar o desenvolvimento
local dependente de infraestrutura pesada por padrão. Testes unitários devem
continuar usando fakes ou fixtures leves; testes com PostgreSQL real,
concorrência ampliada ou cache remoto devem ficar em suítes opt-in e bem
documentadas.

## Problema

`BookPublicAppointmentUseCase.execute` concentra idempotência, validações,
customer, appointment, slots, commit, cache e recuperação de concorrência. Todo
`UnitOfWorkConflict` é tratado no final como conflito de slot ou idempotência,
mesmo quando a constraint causadora pode ser a unicidade global do telefone do
customer ou outra integridade. Isso pode devolver erro enganoso e perder a
oportunidade de reaproveitar o customer criado por uma request concorrente.

O fluxo também executa efeitos pós-commit antes de `refresh(appointment)`. Uma
falha inesperada após o commit pode fazer a API responder erro embora o
agendamento já exista, incentivando retry sem chave idempotente.

## Escopo

- Separar o fluxo em colaboradores internos do módulo appointments para:
  validação/replay idempotente, preparação do booking e persistência atômica.
- Preservar `BookPublicAppointmentUseCase` como entrada e orquestrador; não criar
  wrapper no router nem serviço compartilhado entre domínios.
- Classificar conflitos pela constraint/causa conhecida no adapter de
  persistência, sem depender de mensagens frágeis quando houver alternativa.
- Tratar corrida de criação de customer por telefone com retry/reload limitado.
- Definir a fronteira do commit e produzir a resposta apenas a partir de estado
  estável; efeitos de cache devem ser fail-open e não alterar o sucesso já
  confirmado no PostgreSQL.
- Tornar obrigatório ou recomendar fortemente `Idempotency-Key` no contrato de
  clientes, definindo tamanho e formato antes de chegar ao banco.

## Plano

1. Criar testes de concorrência que reproduzam colisão de slot, de customer e
   de idempotency key separadamente.
2. Enriquecer `UnitOfWorkConflict` com uma categoria estável ou mapear erros no
   repository/UoW responsável.
3. Extrair métodos/objetos privados coesos dentro do módulo appointments,
   mantendo dependências estreitas.
4. Reordenar commit, materialização da resposta, logging e invalidação de cache.
5. Documentar a garantia do endpoint quando o banco confirma e um efeito
   secundário falha.

## Testes

- Duas requests simultâneas para o mesmo slot: uma vence, outra recebe 409.
- Duas requests simultâneas com o mesmo telefone e slots diferentes reutilizam
  um customer e ambas podem concluir.
- Mesma chave/mesmo payload faz replay; mesma chave/payload diferente dá 409.
- Falha de cache após commit não transforma sucesso persistido em erro HTTP.
- Erro de integridade desconhecido não é rotulado silenciosamente como slot
  indisponível e gera log sem dados sensíveis.

## Critérios de aceitação

- Cada conflito conhecido tem tradução determinística e teste de integração.
- Não existe caminho em que um pós-commit opcional determine o status do
  booking já persistido.
- O use case fica menor e legível, mas continua dono da orquestração.
- Nenhuma chave idempotente, telefone ou payload aparece em logs.
