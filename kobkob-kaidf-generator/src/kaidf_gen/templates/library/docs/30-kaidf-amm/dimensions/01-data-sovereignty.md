# Dimension 1: Data Sovereignty & Perimeter

**Points:** 20 (the checks below add up to 20)

Personal data stays out of versioned content, no cloud credentials are committed, and the default execution path runs locally.

| Check | Criterion | Points | Evidence required |
| --- | --- | --- | --- |
| `pii-isolation` | Personal data is kept out of versioned content | 8 | Scan of committed docs and data files for personal identifiers; findings listed with file paths. |
| `no-cloud-keys-in-git` | No cloud API keys or credentials are committed | 6 | Secret scan of the full history of the default branch; any hit fails the check. |
| `local-execution` | The default execution path runs entirely locally | 6 | Configuration of the default model provider and endpoints; no outbound calls on the default path. |

Score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv`. Record the evidence location in `auditor_notes`.
