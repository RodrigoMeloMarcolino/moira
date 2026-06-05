# CI e regras de merge

Este repositorio usa GitHub Actions para expor quatro checks de merge:

- `lint`: roda `uv run ruff check .`, `uv run ruff format --check .` e `uv run mypy app`.
- `unit-tests`: roda `uv run pytest -m "not integration"`.
- `integration-tests`: sobe PostgreSQL, aplica migrations e roda `uv run pytest -m integration`.
- `pull-request-approval`: exige pelo menos um approve de um contribuidor no commit atual do PR, exceto para autores explicitamente isentos.

Para bloquear merges na `main`, configure a protecao da branch no GitHub:

1. Ative `Require a pull request before merging`.
2. Nao configure `Required approvals` nativo como `1`, porque essa regra nao permite excecao por autor do PR.
3. Ative `Require status checks to pass before merging`.
4. Marque como obrigatorios os checks `lint`, `unit-tests`, `integration-tests` e `pull-request-approval`.

Antes de receber approve, o unico check esperado a falhar deve ser
`pull-request-approval`, exceto quando o autor do PR estiver na lista de
isencao. Os checks `lint`, `unit-tests` e `integration-tests` devem passar
normalmente.

O workflow `pull-request-approval` considera aprovadores com associacao
`OWNER`, `MEMBER`, `COLLABORATOR` ou `CONTRIBUTOR`, ignora bots, ignora o autor
do PR e aceita somente review feita contra o SHA atual do PR.

Autores isentos atualmente:

- `RodrigoMeloMarcolino`
