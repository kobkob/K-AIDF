# KAIDF-AMM: 5-Dimension Audit Matrix

The KAIDF-AMM matrix scores a K-AIDF repository out of 100 points, split across five dimensions of 20 points each.

| # | Dimension | Points |
| --- | --- | --- |
| 1 | Data Sovereignty & Perimeter | 20 |
| 2 | Methodology-as-Code | 20 |
| 3 | Regulatory Compliance | 20 |
| 4 | Deterministic Guardrails | 20 |
| 5 | Cost & Infrastructure Health | 20 |

## What this matrix is, and is not

- It defines the checks, their points, and the evidence each one needs.
- It does not certify compliance. Regulatory mapping (dimension 3) documents how obligations are addressed; it is not legal advice.
- A score is only meaningful when every point is backed by the evidence listed for its check.

## How to run an audit

1. Fill `audit-matrix.csv`: set `status` to `pass`, `partial` or `fail` for each check and record the evidence in `auditor_notes`.
2. Use the dimension pages in `dimensions/` for the detailed check criteria.
3. Write the result with `templates/audit-report.md`.

The matrix version is `1.0`. Its machine-readable definition is the `audit_matrix` block of the spec that generated this repository.
