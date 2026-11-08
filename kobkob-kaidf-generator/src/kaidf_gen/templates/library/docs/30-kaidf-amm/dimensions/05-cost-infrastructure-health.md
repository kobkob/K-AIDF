# Dimension 5: Cost & Infrastructure Health

**Points:** 20 (the checks below add up to 20)

<!-- audit_matrix:summary cost-infrastructure-health -->

<!-- audit_matrix:checks cost-infrastructure-health -->

`kob audit` scores these checks; the summary and the table above are rendered from the `audit_matrix` block of the spec that generated this repository. For a manual review, score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv` and record the evidence location in `auditor_notes`.

## Static audit

`kob audit` reads `policy/budget.yaml` from the scaffold (`.kaidf/` in a `kob init` project, this repository's root when audited directly): a positive `max_tokens` and `request_timeout_seconds` for the caps, and `local_fallback: true` for the fallback. The generated file is a placeholder (`placeholder: true`) that scores 0 on both checks until it is filled in.
