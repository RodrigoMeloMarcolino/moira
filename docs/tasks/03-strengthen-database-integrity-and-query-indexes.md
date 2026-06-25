# Task — Reforçar integridade relacional, estados e índices de consulta

Status: todo

## Restrição de overhead local

Migrations, constraints e índices devem preservar o setup local enxuto. A API e
os testes rápidos não devem exigir banco populado, análise `EXPLAIN` pesada ou
serviços externos. Benchmarks, datasets representativos e validações com
PostgreSQL real devem ser comandos separados, opt-in e documentados.

## Problema

Parte importante das regras está apenas no código. `appointments.status` aceita
qualquer string; `providers.user_id` não expressa se a relação é realmente
um-para-um; várias foreign keys usadas em listagens não possuem índice explícito
(`offerings.provider_id`, `appointments.provider_id`, entre outras). PostgreSQL
não cria índices automaticamente para foreign keys.

Campos como `cancel_token_hash` e `reschedule_token_hash` existem sem fluxo que
os use, o que aumenta superfície conceitual. Também faltam decisões explícitas
de `ON DELETE` e uma auditoria entre metadata SQLAlchemy e migrations.

## Escopo

- Inventariar invariantes, cardinalidades e consultas reais antes de criar
  constraints/índices.
- Adicionar constraint ou tipo controlado para status de appointment, com
  política de transição no domínio.
- Confirmar e impor (ou rejeitar formalmente) unicidade de provider por user.
- Adicionar índices guiados por `EXPLAIN` para listagens e lookups frequentes.
- Definir `ON DELETE` para relações centrais, preferindo restrição segura quando
  não existir caso de uso de exclusão.
- Decidir se colunas de cancelamento/remarcação permanecem reservadas e
  documentadas ou se devem ser removidas até a feature existir.
- Garantir limites no contrato para `Idempotency-Key` e demais strings que hoje
  podem estourar restrições somente no commit.

## Plano de migração

1. Medir duplicidades/dados inválidos antes de adicionar constraints.
2. Criar migrations aditivas e, quando aplicável, índices `CONCURRENTLY` em
   produção; documentar a estratégia compatível com Alembic/autocommit.
3. Fazer backfill/limpeza em etapa separada de `NOT NULL` ou unicidade arriscada.
4. Manter downgrade realista ou registrar claramente limitações de rollback.
5. Comparar `Base.metadata` com o schema migrado em teste automatizado.

## Testes

- Inserts inválidos falham na constraint esperada.
- Queries administrativas e públicas usam os índices planejados em dataset
  representativo.
- Upgrade desde banco vazio e desde a migration anterior.
- Downgrade quando suportado.
- Relações não deixam órfãos nem apagam histórico acidentalmente.

## Critérios de aceitação

- Cada nova constraint corresponde a uma regra documentada.
- Não há índice criado apenas por suposição; plano de consulta fundamenta a
  escolha.
- Models e migrations ficam alinhados.
- Impacto e rollback são registrados no livedoc e em ADR se cardinalidade ou
  lifecycle mudar.
