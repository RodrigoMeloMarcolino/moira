# CI e regras de merge

Este repositorio usa GitHub Actions para expor tres checks de merge:

- `lint`: roda `uv run ruff check .`, `uv run ruff format --check .` e `uv run mypy app`.
- `unit-tests`: roda `uv run pytest -m "not integration"`.
- `integration-tests`: sobe PostgreSQL, aplica migrations e roda `uv run pytest -m integration`.

Para bloquear merges na `main`, configure a protecao da branch no GitHub:

1. Ative `Require a pull request before merging`.
2. Configure `Required approvals` como `1`.
3. Ative `Dismiss stale pull request approvals when new commits are pushed` ou `Require approval of the most recent reviewable push`.
4. Ative `Require status checks to pass before merging`.
5. Marque como obrigatorios os checks `lint`, `unit-tests` e `integration-tests`.

O approve deve ser exigido pela protecao nativa de branch do GitHub, nao por
um workflow separado. Assim o PR pode ficar pronto para review com CI verde, e
o merge continua bloqueado ate haver pelo menos um approve valido.
