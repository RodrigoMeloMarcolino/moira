# Task — Alinhar configuração de runtime com comportamento real e seguro

Status: todo

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
