# Dimension 1: Data Sovereignty & Perimeter

**Points:** 20 (the checks below add up to 20)

<!-- audit_matrix:summary data-sovereignty -->

<!-- audit_matrix:checks data-sovereignty -->

`kob audit` scores these checks; the summary and the table above are rendered from the `audit_matrix` block of the spec that generated this repository. For a manual review, score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv` and record the evidence location in `auditor_notes`.

## Static audit

`kob audit` scans the tracked files at the root of the audited project for credentials and `.env` files, and reads `policy/pii-masking-rules.yaml` from the scaffold (`.kaidf/` in a `kob init` project, this repository's root when audited directly). The generated rules file is a placeholder (`placeholder: true`) and scores 0 until it is filled in.
