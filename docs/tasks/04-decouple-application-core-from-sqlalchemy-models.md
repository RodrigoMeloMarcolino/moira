# Task — Desacoplar o core de aplicação dos models SQLAlchemy

Status: todo

## Restrição de overhead local

O desacoplamento deve reduzir, não aumentar, o custo de rodar localmente. Use
cases devem permanecer testáveis com fakes simples, sem sessão SQLAlchemy ou
banco obrigatório. Novas abstrações só são aceitáveis se mantiverem o boot local
e a suíte rápida previsíveis.

## Problema

Ports e use cases de users, providers, offerings, availability, customers e
appointments importam diretamente classes em `infrastructure.models`. Assim,
as interfaces que deveriam ser definidas pelo consumidor já dependem do adapter
de persistência. Isso contraria o sentido de dependência do ADR 0010 e torna os
testes unitários dependentes de objetos ORM, instrumentação e estado de sessão.

## Decisão proposta

Adotar entidades/records de domínio ou application DTOs somente onde a
separação traz valor real. Repositories SQLAlchemy mapeiam explicitamente entre
persistência e core. Não criar uma hierarquia DDD cerimonial nem duplicar todo
campo sem necessidade.

## Escopo

- Definir tipos neutros para os agregados retornados pelos ports.
- Remover imports de `infrastructure` de `application` e `domain`.
- Fazer ports pertencerem ao módulo consumidor e usar nomes consistentes.
- Mapear ORM ↔ core nos repositories; schemas Pydantic continuam na borda HTTP
  ou viram command DTOs neutros quando usados diretamente pelos use cases.
- Retornar output DTOs explícitos quando o router não precisa da entidade
  inteira.
- Preservar transação, identidade e performance; evitar lazy loading oculto.

## Estratégia incremental

1. Escolher um módulo pequeno, preferencialmente users ou customers, e provar o
   padrão com testes.
2. Migrar providers e auth, incluindo um `AuthenticatedProvider`/principal
   neutro para que `CurrentProviderDep` não exponha ORM.
3. Migrar offerings e availability.
4. Migrar appointments por último, após as correções transacionais e temporais.
5. Adicionar regra automatizada de imports antes de concluir.

## Testes

- Use cases instanciados com fakes simples, sem SQLAlchemy.
- Testes de repository garantem mapping bidirecional e campos obrigatórios.
- Contratos HTTP permanecem idênticos.
- Teste de arquitetura falha se application/domain importar infrastructure,
  FastAPI ou SQLAlchemy.

## Critérios de aceitação

- Zero imports de infrastructure em application/domain.
- Ports não referenciam models ORM.
- Routers não declaram models ORM como retorno.
- A quantidade de abstrações novas é justificada por fronteira, não por mera
  simetria de pastas.
- ADR 0010 é atualizado se o padrão de mapping passar a ser uma obrigação do
  projeto.
