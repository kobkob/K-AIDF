# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

### Added

- tenant scoping: documents can declare a `namespace`, and `MCP_TOKEN_SCOPES` maps extra bearer tokens to the namespaces they may read. A scoped token gets the same visibility rules as before, plus its namespace list; a document with no namespace is shared with every tenant only when it is public; internal and private documents with no namespace are visible only to the primary token. Another tenant's document returns the same error as a missing one. Invalid configuration stops the server at startup
- document visibility is enforced on `search` and `fetch`: `private` documents are never returned, `internal` documents only to authenticated requests, and `public` documents to everyone. Unknown visibility values are hidden (fail closed). A `fetch` of a hidden document returns the same error as a missing one (#14)

- two MCP tools for KAIDF-AMM maturity, built on the audit engine in `agent-aidf`:
  - `get_maturity_scorecard` returns the matrix: dimensions, point weights, severities, and the criteria and remediation for each check
  - `evaluate_repository_maturity` scores a repository under `AIDF_REPO_ROOT` and returns the global and per-dimension score, the violations ordered by severity, the gap counts per severity, and an ordered mitigation backlog. `format: "prompt"` returns a Portuguese prompt for a local model (OLMo 2, Qwen 2.5 Coder) that asks for a diagnosis and a prioritised backlog
- `path` is resolved against `AIDF_REPO_ROOT` (default: the root, not the server's working directory). Paths outside the root are refused, symlinks included, and the refusal does not reveal whether the path exists
- `evaluate_repository_maturity` requires the primary token. Scoped tokens get `403`, because the report lists file paths
- without the `agent-aidf` package the two tools return `503` with a clear message. `search` and `fetch` are unaffected. `Dockerfile` copies `maturity.py`, but the image does not install `agent-aidf`, so the evaluation tools are unavailable in the container until it is added

### Security

- `/mcp` and `/` accept only `Authorization: Bearer <MCP_BEARER_TOKEN>`, compared in constant time. Before, any non-empty `Authorization` header was accepted (#11)
- `MCP_BEARER_TOKEN` is required by `docker-compose.yml` and documented in `.env.example`. Without it, the server starts with a random token for that process only, logs it at startup, and does not share it between gunicorn workers (#11)

### Removed

- the OAuth 2.1 stub endpoints `/oauth/authorize`, `/oauth/token`, `/oauth/register` and `/.well-known/oauth-authorization-server`. `/oauth/token` issued the fixed token `mcp_token`, and `/oauth/authorize` redirected to any `redirect_uri` with a fixed code (open redirect) (#11)
- the `authorization_servers` field from `/.well-known/oauth-protected-resource`, because no authorization server is implemented (#11)

## [0.5.5] - 2026-10-16

### Added

- pytest test suite is now automatically run in CI/CD pipeline (`.github/workflows/ci.yml`)

### Security

- Dockerfile runs as a non-root `appuser` and serves the app with `gunicorn` (`app:app`, port 7777) instead of the Flask development server (`python app.py`)
- `requirements.txt` pins all runtime dependencies, including transitive ones: `Flask==3.1.3` (was `3.0.0`), `Werkzeug==3.1.9`, `PyYAML==6.0.3` (was `>=6.0.1`), `gunicorn==26.2.0`
- removed the `SECRET_KEY` placeholders: `docker-compose.yml` requires `SECRET_KEY` from the environment (`${SECRET_KEY:?...}`, no default), and `app.py` no longer falls back to the hardcoded `dev-key-change-in-prod`, using a random per-process secret when unset
- internal errors no longer leak to clients: `/mcp` wraps every request, logs the traceback on the server, and returns a JSON-RPC `-32603` "Internal error." (HTTP 500) with no stack trace, path or exception text; a non-JSON body returns `-32700` and a non-object body returns `-32600`, both as JSON (#27)
- `tools/call` `search` rejects a non-integer `limit` with `-32602` instead of an internal error that quoted the Python exception message (#27)

### Fixed

- front matter parsing accepts CRLF line endings, so documents saved with Windows line endings keep their metadata instead of silently losing it (#32)
- `initialize` validates the requested `protocolVersion` against the supported revisions (`2024-11-05`): a supported version is echoed back, while an unknown, missing or non-string one is answered with the newest supported version instead of being echoed blindly (#27)

### Changed

- the document index is cached in memory: each request checks a signature of the indexable files (path, mtime, size) and reuses the parsed documents while nothing changed, instead of re-reading and re-parsing the whole repository. On a 65-document repository a request dropped from about 27 ms to about 2 ms; edits, additions and removals are picked up on the next request (#26)
- the indexing contract is shared with `agent-aidf` through `contracts/index-contract/` (fixture corpus and `expected.json`), and both packages' tests check against it (#15)

## [0.1.2] - 2026-03-20

## [0.1.1] - 2026-03-20

### Added

- single-repository local indexing model driven by `AIDF_REPO_ROOT`
- real `search` and `fetch` behavior over contract-defined K-AIDF files
- optional front matter awareness for metadata IDs, titles, visibility, and document classes
- doctrine-aware categories and ranking metadata derived from manifesto/governance/best-practice content
- rigid ranking and detailed score metadata for canonical doctrine package files
- explicit tests for doctrine ranking and canonical doctrine fetch behavior
- explicit starter-variant ranking and `variant_domain` metadata for domain-specific best-practice queries
- explicit starter-variant identity remains path-derived from canonical repository paths
- documentation that starter variants remain part of the default generated baseline
- explicit maturity-model pack metadata and ranking for level- and assessment-specific queries
- explicit ethical-model pack metadata and ranking for ethical-domain, control, and risk queries

## [0.1.0] - 2026-03-17

### Added

- initial MCP server prototype with OAuth endpoints and stubbed tools
- repository initialization as a nested Git repository on `main`
- standard repository metadata: `.gitignore`, `CODEOWNERS`, `CONTRIBUTING.md`, and MIT license
- development baseline: `.editorconfig`, GitHub CI, PR template, and release workflow
- release hygiene: `RELEASING.md`, changelog maintenance, and tag-based GitHub releases
- quality gates: markdown linting plus `ruff` lint and format checks in CI
