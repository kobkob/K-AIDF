# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

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
