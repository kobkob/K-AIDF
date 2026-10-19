# Dimension 5: Cost & Infrastructure Health

**Points:** 20 (the checks below add up to 20)

Consumption is bounded: hard token caps, request timeouts, and a documented local fallback when the remote model is unavailable.

| Check | Criterion | Points | Evidence required |
| --- | --- | --- | --- |
| `token-hard-caps` | Hard caps on tokens per request are configured | 8 | Configured maximum output and context sizes for each provider, enforced in code. |
| `request-timeouts` | Network calls to models have timeouts | 6 | Timeout values for every outbound model request, set in code or configuration. |
| `local-fallback` | A local fallback is documented and tested | 6 | Documented fallback to the local model and a test that exercises the switch. |

Score each check as `pass`, `partial` or `fail` in `../audit-matrix.csv`. Record the evidence location in `auditor_notes`.
