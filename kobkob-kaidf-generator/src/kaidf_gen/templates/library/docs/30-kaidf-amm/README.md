# KAIDF-AMM: 5-Dimension Audit Matrix

The KAIDF-AMM matrix scores a K-AIDF repository out of 100 points, split across five dimensions of 20 points each. `kob audit` (the `agent-aidf` audit engine) is what scores a repository against it.

| # | Dimension | Points |
| --- | --- | --- |
| 1 | Data Sovereignty & Perimeter | 20 |
| 2 | Methodology-as-Code | 20 |
| 3 | Regulatory Compliance | 20 |
| 4 | Deterministic Guardrails | 20 |
| 5 | Cost & Infrastructure Health | 20 |

## What this matrix is, and is not

- It mirrors the `kob audit` engine: the dimension ids, names and points and the check ids, titles and points in this folder are the ones in `agent-aidf`'s `audit.py` (`DIMENSION_SPECS`). A cross-component test keeps the two identical.
- In v1.0 the engine scores the presence and parseability of the listed artifacts, not their substance: a parseable `pii-masking-rules.yaml` earns its points whatever rules it contains. The evidence column of each check says exactly what is verified.
- It does not certify compliance. The Regulatory Compliance dimension checks that governance artifacts exist; it is not legal advice.
- A score is only meaningful when every point is backed by the evidence listed for its check.

## How to run an audit

1. Run `kob audit` at the repository root (`kob audit --json` for machine-readable output). Each check reports its points, its finding and a remediation.
2. Use the dimension pages in `dimensions/` for what each check verifies.
3. For a manual review, fill `audit-matrix.csv`: set `status` to `pass`, `partial` or `fail` for each check and record the evidence in `auditor_notes`.
4. Write the result with `templates/audit-report.md`.

## Planned for v1.1

The declarative matrix described these checks before it was aligned with the engine, but no tool ever scored them. They are planned as engine checks for v1.1, so the intent is not lost:

- regulatory mappings (LGPD/GDPR, NIST AI RMF, EU AI Act) from obligations to controls and evidence files
- pre-commit hooks that run formatting and secret checks
- security gates in CI (dependency pinning, secret scanning) that block on findings
- phase deliverables under `docs/0N_*/` filled in rather than left as scaffold
- timeouts enforced on every outbound model request (v1.0 only checks the configured value in `.kaidf/policy/budget.yaml`)

The matrix version is `1.0`. Its machine-readable definition is the `audit_matrix` block of the spec that generated this repository; `audit-matrix.csv` and the summaries and check tables in `dimensions/` are rendered from that block.
