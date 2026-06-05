# CI e regras de merge

Este repositorio usa GitHub Actions para expor quatro checks de merge:

- `lint`: roda `uv run ruff check .`, `uv run ruff format --check .` e `uv run mypy app`.
- `unit-tests`: roda `uv run pytest -m "not integration"`.
- `integration-tests`: sobe PostgreSQL, aplica migrations e roda `uv run pytest -m integration`.
- `pull-request-approval`: exige pelo menos um approve de um contribuidor no commit atual do PR.

Para bloquear merges na `main`, configure a protecao da branch no GitHub:

1. Ative `Require a pull request before merging`.
2. Configure `Required approvals` como `1`.
3. Ative `Dismiss stale pull request approvals when new commits are pushed` ou `Require approval of the most recent reviewable push`.
4. Ative `Require status checks to pass before merging`.
5. Marque como obrigatorios os checks `lint`, `unit-tests`, `integration-tests` e `pull-request-approval`.

Antes de receber approve, o unico check esperado a falhar deve ser
`pull-request-approval`. Os checks `lint`, `unit-tests` e `integration-tests`
devem passar normalmente.

O workflow `pull-request-approval` considera aprovadores com associacao
`OWNER`, `MEMBER`, `COLLABORATOR` ou `CONTRIBUTOR`, ignora bots, ignora o autor
do PR e aceita somente review feita contra o SHA atual do PR.
