# Task — Adicionar gates de arquitetura, cobertura e regressão operacional

Status: todo

## Restrição de overhead local

Novos gates devem ser rápidos, determinísticos e baratos por padrão. A suíte
local principal não deve passar a exigir Docker, banco real, rede, navegador ou
pipeline de observabilidade. Gates pesados podem existir como etapas separadas
de CI ou comandos opt-in, com baseline documentada e sem bloquear o ciclo curto
de desenvolvimento.

## Problema

Os checks atuais passam e são uma boa baseline, mas não impedem regressões nas
fronteiras arquiteturais. `mypy` está com `strict = false`, integration depende
de runner próprio e `tests/e2e` está vazio. O warning OTLP é conhecido, mas não
há política geral para novos warnings. A divergência entre models e migrations
também não é verificada automaticamente.

## Escopo

- Criar testes de arquitetura baseados em imports, sem adicionar ferramenta
  pesada se um teste Python simples resolver.
- Proibir application/domain de importar FastAPI, SQLAlchemy ou infrastructure.
- Verificar que módulos shared não importam políticas/DTOs de múltiplos domínios.
- Adicionar cobertura com limiar inicial baseado na baseline, elevável por
  módulo; não perseguir 100% artificial.
- Tornar warnings novos falhas, com exceção temporária e localizada para o OTLP
  até `logging-hardening.md` ser concluída.
- Adicionar smoke E2E mínimo do fluxo signup → login → offering → availability
  → public booking, ou documentar por que integração já cobre o mesmo risco.
- Verificar schema Alembic versus metadata em ambiente efêmero.
- Evoluir mypy por módulos, começando no domínio/application novos ou migrados.

## Plano

1. Medir cobertura e warnings atuais e registrar a baseline.
2. Implementar gates de import e schema drift.
3. Configurar warnings e cobertura no pytest/CI.
4. Adicionar smoke de jornada sem duplicar toda a suíte de integração.
5. Habilitar opções strict gradualmente por override de módulo.

## Critérios de aceitação

- Uma violação de fronteira falha localmente e no CI com mensagem acionável.
- Coverage gate não reduz a cobertura atual e não incentiva testes sem valor.
- Migrations ausentes ou metadata divergente são detectadas.
- A jornada crítica possui ao menos um teste ponta a ponta automatizado.
- README e `docs/ci.md` apresentam os mesmos comandos executados pelo CI.
