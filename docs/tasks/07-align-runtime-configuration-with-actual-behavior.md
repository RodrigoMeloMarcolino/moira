# Task — Alinhar configuração de runtime com comportamento real e seguro

Status: done on 2026-06-26

## Checkpoint de implementacao - 2026-06-26

Modo: assisted implementation com subagent Worker C e integracao final.

Implementado:

- `CORSMiddleware` passa a ser instalado somente quando `CORS_ALLOWED_ORIGINS`
  contem origens configuradas, com methods/headers restritos ao uso atual da
  API bearer.
- `DEFAULT_TIMEZONE` passa por validacao IANA em `Settings`.
- `ProviderSignupCreate.timezone` ficou opcional; `SignupProviderUseCase`
  recebe `default_timezone` por injecao em `app/api/deps.py` e usa esse valor
  quando o payload omite timezone.
- `JWT_SECRET_KEY` default/fraco e rejeitado fora de `local` e `test`, e
  `JWT_ALGORITHM` fica limitado ao allowlist suportado pelo codec atual.
- Expiracao JWT, timeout OTLP e TTLs de cache receberam limites positivos e
  maximos.
- `redis_url` passou a `SecretStr`; `build_cache_backend` explicita
  `get_secret_value()` no limite de infraestrutura.
- `RedisCache` continua fail-open para falhas esperadas de backend Redis/socket,
  mas propaga erros de programacao como `RuntimeError`.
- README e `.env.example` foram ajustados com o comportamento de runtime.

Validacao executada:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy app tests/unit`
- `uv run pytest -m "not integration" -q`
- `uv run python scripts/run_integration_tests.py`

Resultado integrado: 146 testes nao-integracao passaram, 43 testes de
integracao passaram. Permanece apenas warning local do pytest cache por
permissao de `.pytest_cache` no ambiente Windows.

Notas de integracao:

- `app/api/deps.py` tambem recebeu a alteracao paralela da task 06 para
  `InvalidAccessToken`; o resultado integrado preserva logging de autenticacao
  e traducao centralizada.
- Nenhum ADR novo foi identificado como necessario para esta task.
- Google Docs externo nao foi atualizado por falta de autorizacao explicita;
  este checkpoint local deve ser sincronizado na task 09.

## Restrição de overhead local

As validações de configuração devem proteger ambientes não-locais sem quebrar o
fluxo local padrão. `local` e `test` devem continuar iniciando com defaults
seguros e explícitos; integrações como Redis, CORS real de frontend ou segredos
fortes devem ser configuráveis sem se tornarem obrigatórias para desenvolvimento
e testes rápidos.

## Problema

`CORS_ALLOWED_ORIGINS` é parseado mas `CORSMiddleware` não é instalado.
`DEFAULT_TIMEZONE` existe, porém o signup usa default próprio no schema e o
cálculo de agenda não consome a configuração. O JWT possui secret local padrão,
sem guardrail explícito contra uso em ambiente não-local. TTLs aceitam valores
sem limites, e `redis_url` é string comum apesar de ser dado sensível em logs e
diagnósticos.

Configuração sem efeito é particularmente perigosa: operadores acreditam ter
ativado um comportamento que não existe.

## Escopo

- Instalar CORS de forma condicional ou remover a configuração até existir um
  consumidor; definir methods, headers e credentials mínimos.
- Ter uma única fonte para timezone padrão e conectá-la ao signup, sem esconder
  a validação por provider.
- Rejeitar secret JWT default/fraco fora de `local` e `test`.
- Validar algoritmo JWT contra allowlist suportada.
- Aplicar limites positivos e máximos razoáveis aos TTLs e timeout/configurações.
- Tratar URLs/secrets como valores sensíveis e garantir redação.
- Revisar captura ampla de `Exception` no cache: manter fail-open para falhas
  esperadas do backend, sem esconder bugs de programação/cancelamento.

## Testes

- CORS ausente quando lista vazia e restrito quando configurado.
- Produção não inicia com secret default/fraco.
- Timezone default vem de uma fonte única.
- TTL zero/negativo ou excessivo falha na configuração.
- Falha Redis esperada degrada; erro de programação não é silenciosamente
  transformado em cache miss.

## Critérios de aceitação

- Toda setting declarada possui consumidor verificável ou é removida.
- Defaults inseguros não chegam a ambiente não-local.
- `.env.example`, README e compose refletem exatamente o runtime.
- Nenhuma mudança introduz dependência de configuração no domínio.
