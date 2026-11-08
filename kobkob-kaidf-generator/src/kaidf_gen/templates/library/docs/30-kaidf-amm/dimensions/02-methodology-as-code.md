# Dimension 2: Methodology-as-Code

**Points:** 20 (the checks below add up to 20)

<!-- audit_matrix:summary methodology-as-code -->

<!-- audit_matrix:checks methodology-as-code -->

`kob audit` scores these checks; the summary and the table above are rendered from the `audit_matrix` block of the spec that generated this repository. For a manual review, score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv` and record the evidence location in `auditor_notes`.

## Static audit

`kob audit` checks `README.md` and `docs/`, `mentor-workflow.json`, `specs/*.yaml`, the Front Matter v2 block on every Markdown document in the scaffold and `data/manifests/skills.yaml`, resolved against the scaffold (`.kaidf/` in a `kob init` project, this repository's root when audited directly) and then the root. `kob init` records the spec it used as `specs/kaidf.yaml` in the scaffold; `kob mentor` writes `mentor-workflow.json`.
