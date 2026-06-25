# Task — Endurecer a transação e a classificação de conflitos do booking

Status: todo

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
