# Dimension 4: Deterministic Guardrails

**Points:** 20 (the checks below add up to 20)

Checks run automatically and block merges: CI gates, pre-commit hooks and security gates that do not depend on a person remembering to run them.

| Check | Criterion | Points | Evidence required |
| --- | --- | --- | --- |
| `ci-blocking-gates` | CI gates for tests and lint block merges | 7 | Workflow files in .github/workflows/ with lint and test steps not marked continue-on-error. |
| `pre-commit-hooks` | Pre-commit hooks run formatting and secret checks | 5 | Hook configuration in the repository and proof that it is installed in the developer setup. |
| `security-gates` | Security gates run in CI and block on findings | 8 | Dependency pinning and secret scanning enabled in CI, with the gate set to fail the build. |

Score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv`. Record the evidence location in `auditor_notes`.
