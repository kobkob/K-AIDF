# Dimension 4: Deterministic Guardrails

**Points:** 20 (the checks below add up to 20)

<!-- audit_matrix:summary deterministic-guardrails -->

<!-- audit_matrix:checks deterministic-guardrails -->

`kob audit` scores these checks; the summary and the table above are rendered from the `audit_matrix` block of the spec that generated this repository. For a manual review, score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv` and record the evidence location in `auditor_notes`.

## Static audit

`kob audit` reads `.github/workflows/` at the root of the audited project, not in the scaffold: at least one workflow file must exist, and no step may set `continue-on-error: true`.
