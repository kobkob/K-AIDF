# Dimension 3: Regulatory Compliance

**Points:** 20 (the checks below add up to 20)

<!-- audit_matrix:summary regulatory-compliance -->

<!-- audit_matrix:checks regulatory-compliance -->

`kob audit` scores these checks; the summary and the table above are rendered from the `audit_matrix` block of the spec that generated this repository. For a manual review, score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv` and record the evidence location in `auditor_notes`.

## Static audit

`kob audit` checks `docs/20-ethical-model/risk-assessment.json`, `docs/20-ethical-model/explicability-schema.json`, `policy/hitl-config.yaml` and `data/manifests/dataset-audit.yaml` in the scaffold (`.kaidf/` in a `kob init` project, this repository's root when audited directly). All four are generated as placeholders (`placeholder: true`) and score 0 until they are filled in.
