# Task — Dividir o composition root em fábricas por módulo

Status: todo

## Restrição de overhead local

A divisão do composition root não deve introduzir framework de DI, geração de
código ou inicialização antecipada de serviços externos. As factories precisam
continuar preguiçosas o suficiente para a aplicação subir localmente com o
mínimo de configuração e para testes sobrescreverem dependências sem montar o
grafo inteiro.

## Problema

`app/api/deps.py` possui 509 linhas e conhece repositories, caches, adapters e
use cases de todos os domínios. O `RequestContainer` oferece um service locator
global crescente, enquanto várias dependências são construídas tanto em
`cached_property` quanto em funções `build_*`. Qualquer novo módulo tende a
alterar o mesmo arquivo e ampliar o grafo de dependências.

## Escopo

- Manter apenas dependências transversais de request em um núcleo pequeno:
  sessão, UoW, cache genérico e principal autenticado.
- Criar fábricas/composição por módulo (`auth`, `providers`, `offerings`,
  `availability`, `appointments`) próximas à borda API do módulo.
- Injetar cada dependência somente nos use cases que a consomem.
- Eliminar construção duplicada e acesso indireto via service locator.
- Manter política de cache nos módulos donos; shared fornece apenas primitives.
- Evitar um framework/container de DI novo: `Depends`, funções e dataclasses
  pequenas são suficientes.

## Plano

1. Mapear o grafo atual e identificar objetos request-scoped versus stateless.
2. Extrair auth/principal primeiro, sem retornar model ORM.
3. Extrair fábricas de providers e offerings.
4. Extrair availability e appointments, preservando os colaboradores internos.
5. Reduzir `api/deps.py` a composição transversal e aliases realmente comuns.
6. Validar criação de múltiplas apps e overrides de dependência em testes.

## Testes

- Cada factory possui teste de wiring mínimo.
- Overrides de FastAPI substituem ports sem precisar montar o container inteiro.
- Uma request compartilha a mesma sessão/UoW onde necessário.
- Módulos não recebem cache, token codec ou repository que não utilizam.
- Teste de imports impede factory de um domínio importar use cases de outro sem
  uma dependência de aplicação explícita.

## Critérios de aceitação

- Não há container global com catálogo de todos os serviços.
- Adicionar um use case em um módulo não exige editar composição de módulos não
  relacionados.
- Casos de uso permanecem a entrada da aplicação; nenhum reader/helper de borda
  os substitui.
- A composição fica mais curta e navegável sem nova dependência externa.
