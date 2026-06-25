# Task — Centralizar a tradução tipada de erros de aplicação para HTTP

Status: todo

## Restrição de overhead local

A centralização de erros deve ser uma mudança de código e contrato, sem novo
serviço, middleware pesado ou dependência externa para o caminho local. Testes
de contrato devem rodar na suíte rápida sempre que possível, usando o cliente de
teste da aplicação e fixtures leves.

## Problema

Routers repetem blocos `try/except` para as mesmas exceções. O `code` público é
derivado da mensagem humana por regex, então uma mudança editorial pode quebrar
clientes e testes mesmo quando a semântica não mudou. O endpoint de booking já
tem complexidade relevante apenas pela tradução de erros.

## Escopo

- Definir exceções de aplicação com código estável e metadata segura.
- Registrar handlers por família/tipo no adapter HTTP.
- Manter status, code, message e details explícitos; não inferir code de texto
  para erros conhecidos.
- Preservar handlers de validação Pydantic e de HTTP genérico.
- Remover `try/except` repetitivo dos routers após testes de contrato.
- Não mover regra de negócio ou decisão de autorização para os handlers.

## Plano

1. Inventariar todas as exceções e o contrato HTTP atual.
2. Criar uma tabela/mapeamento tipado na camada API, organizada por módulo.
3. Migrar um router e comparar snapshots de contrato.
4. Migrar os demais e remover `_error_code_from_message` para erros conhecidos.
5. Garantir logging central de 5xx com correlation id, sem duplicar eventos de
   rejeição já emitidos pelos use cases.

## Testes

- Cada exceção conhecida possui status e code estáveis.
- Alterar a mensagem não altera o code.
- Erro inesperado não vaza stack trace/detalhes no payload.
- OpenAPI e testes de integração preservam o envelope do ADR 0014.

## Critérios de aceitação

- Routers contêm somente validação/transporte/chamada do use case.
- Codes públicos não são derivados de strings humanas.
- Não existe registry compartilhado com políticas de domínio; o mapeamento é
  exclusivamente responsabilidade do adapter HTTP.
- ADR 0014 e documentação de erros ficam sincronizados.
