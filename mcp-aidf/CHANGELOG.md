# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

## [0.6.2] - 2026-11-13

### Fixed

- the public URL is no longer hardcoded to `https://mcp-aidf.kobkob.org`. The `WWW-Authenticate` challenge, the `_meta` of the 401 JSON body and the `/.well-known/oauth-protected-resource` metadata (`resource`, `resource_documentation`) now use the `MCP_PUBLIC_URL` environment variable, read per request. Unset, they use `http://localhost:7777`. The request `Host` header is deliberately not used, since clients control it (#28)
- spec-compliant handshake over the MCP Streamable HTTP transport. A JSON-RPC notification (a message with no `id`, such as `notifications/initialized` or `notifications/cancelled`) is acknowledged with HTTP `202` and an empty body; it was answered with a `-32601` error and HTTP `400`, which JSON-RPC 2.0 forbids and which made the official MCP SDK clients fail right after `initialize`. A JSON-RPC response sent by the client (`result` or `error`, no `method`) gets the same `202`, as the transport requires. `ping` returns an empty result. `initialize` negotiates `2024-11-05`, `2025-03-26` and `2025-06-18`: a supported requested revision is echoed and any other one gets the newest, `2025-06-18` (only `2024-11-05` was offered, while the README claimed `2025-03-26`). After the handshake, a request whose `MCP-Protocol-Version` header names an unsupported revision gets a `-32600` error with HTTP `400` that lists the supported ones; a request without the header is served. Unchanged: bearer authentication runs first (an unauthenticated notification still gets `401`), a request with an `id` and an unknown method still gets `-32601` with HTTP `400`, `GET /mcp` is `405`, JSON-RPC batch requests are still refused with `-32600`, and the server stays stateless (no `Mcp-Session-Id`)

### Added

- the container image bundles the `agent-aidf` audit engine (#71). A builder stage builds its wheel and the runtime stage installs it, so `get_maturity_scorecard` and `evaluate_repository_maturity` answer `200` instead of `503`. The image also installs `git` (`--no-install-recommends`), which the engine runs as `git ls-files` on a repository with a `.git` directory, and trusts `/workspace` with `safe.directory`, because the volume is usually cloned by another user and git refuses that as "dubious ownership"
- `HEALTHCHECK` in the image: `GET /.well-known/oauth-protected-resource` must answer `200` on `PORT`, checked with Python's `urllib`, so the image needs no `curl`
- `mcp-aidf/scripts/check-image.sh`: builds the image from the repository root, runs it with a repository on `/workspace`, waits for the health check and calls both maturity tools (the CI `image` job runs it)
- `mcp-aidf/tests/test_dockerfile.py`: pins the image contract (the engine wheel, `git` and its `safe.directory`, the health check, and the files copied into the image)
- `mcp-aidf/tests/test_maturity_tools.py`: with `KAIDF_REQUIRE_ENGINE` set, a missing `agent-aidf` fails the run instead of skipping its tests (CI sets it)
- root `.dockerignore`: keeps `.git`, caches, virtualenvs, `models/` and `olmo-env/` out of the build context, which is now the repository root
- `PORT` environment variable in the container image: gunicorn binds `0.0.0.0:${PORT:-7777}`. The image sets `PORT=7777`, so `docker-compose.yml` keeps publishing `7777:7777`; a hosting platform can set another port, and the EasyPanel template at `deploy/easypanel/easypanel.json` sets `8000`. `python app.py` and `DEFAULT_PUBLIC_URL` still use 7777 (#137)
- `tests/test_easypanel_template.py`: checks `deploy/easypanel/easypanel.json` against this component, so the template cannot drift from the server: the build path holds the Dockerfile and every file it copies, the domain port equals `PORT` and the start command reads `PORT`, every variable is one `app.py` or the start command reads, `MCP_BEARER_TOKEN` ships empty, `MCP_PUBLIC_URL` is the bare origin, and the volume is mounted at `AIDF_REPO_ROOT`. The guide `docs/06-deploy/easypanel.md` must list each variable with the value the template sets (#137)
- README: an EasyPanel subsection under Deployment and the `PORT` entry under Configuration (#137)
- `MCP_PUBLIC_URL` environment variable, the public base URL of the server (a trailing `/` is ignored). Documented in `README.md` and `.env.example` (#28)
- `evaluate_repository_maturity` reports `scaffold_path`: where the audit engine looked for the scaffold-owned artifacts (`<repo_root>/.kaidf` in a `kob init` project, `repo_root` itself for a generated repository audited directly). Every remediation path in the backlog depends on that layout. It is `null` with an engine that does not report it (related: #16)
- an integration test drives the official `mcp` Python SDK client (`streamable_http_client` and `ClientSession`) over HTTP against the Flask app, served by werkzeug on a loopback port: `initialize`, `tools/list` and a `search` call, plus the `401` an unauthenticated client gets. `mcp>=2,<3` is a `dev` extra, installed by `scripts/bootstrap.sh` and by CI

### Changed

- the Dockerfile builds from the repository root: `docker build -f mcp-aidf/Dockerfile .`. `mcp-aidf/docker-compose.yml` and the root `docker-compose.local.yml` use that context, and `deploy/easypanel/easypanel.json` sets `source.path` to `/` and `build.file` to `mcp-aidf/Dockerfile`. The template test and the guide follow
- the `503` for the maturity tools is only for a deployment without `agent-aidf` (for example a local run that did not install it). The container image has the engine, so the tools work there
- `scripts/bootstrap.sh` installs `agent-aidf` (editable) next to the server's requirements, so the local test run covers the maturity tools
- `mcp-aidf CI` installs `agent-aidf`, requires the engine in the test run, watches `agent-aidf/**`, and adds an `image` job that runs `scripts/check-image.sh`
- the workspace `docs/` sections covered by `tests/test_workspace_docs.py` include `06-deploy` (#137)

### Removed

- the unused `MATURITY_LEVEL_PRIORITY` constant in `app.py` (#28)
- the nested `.github/` directory (`workflows/release.yml` and `PULL_REQUEST_TEMPLATE.md`). GitHub Actions only reads the `.github/` at the repository root, so that workflow never ran. Releases are made from the root `.github/workflows/release.yml`, one tag for all components; see the root `RELEASING.md`

## [0.6.1] - 2026-11-06

### Changed

- version aligned with the workspace release `v0.6.1`: `pyproject.toml` and `SERVER_VERSION` in `app.py` (reported in `serverInfo`) say `0.6.1`. No functional changes; the root `CHANGELOG.md` lists the release as a whole

## [0.6.0] - 2026-10-30

### Added

- tenant scoping: documents can declare a `namespace`, and `MCP_TOKEN_SCOPES` maps extra bearer tokens to the namespaces they may read. A scoped token gets the same visibility rules as before, plus its namespace list; a document with no namespace is shared with every tenant only when it is public; internal and private documents with no namespace are visible only to the primary token. Another tenant's document returns the same error as a missing one. Invalid configuration stops the server at startup
- document visibility is enforced on `search` and `fetch`: `private` documents are never returned, `internal` documents only to authenticated requests, and `public` documents to everyone. Unknown visibility values are hidden (fail closed). A `fetch` of a hidden document returns the same error as a missing one (#14)

- two MCP tools for KAIDF-AMM maturity, built on the audit engine in `agent-aidf`:
  - `get_maturity_scorecard` returns the matrix: dimensions, point weights, severities, and the criteria and remediation for each check
  - `evaluate_repository_maturity` scores a repository under `AIDF_REPO_ROOT` and returns the global and per-dimension score, the violations ordered by severity, the gap counts per severity, and an ordered mitigation backlog. `format: "prompt"` returns a Portuguese prompt for a local model (OLMo 2, Qwen 2.5 Coder) that asks for a diagnosis and a prioritised backlog
- `path` is resolved against `AIDF_REPO_ROOT` (default: the root, not the server's working directory). Paths outside the root are refused, symlinks included, and the refusal does not reveal whether the path exists
- `evaluate_repository_maturity` requires the primary token. Scoped tokens get `403`, because the report lists file paths
- without the `agent-aidf` package the two tools return `503` with a clear message. `search` and `fetch` are unaffected. `Dockerfile` copies `maturity.py`, but the image does not install `agent-aidf`, so the evaluation tools are unavailable in the container until it is added

### Changed

- the server reports version `0.6.0` in `serverInfo` (it reported `0.5.5`). `pyproject.toml` now declares the project and its `dev` extra (`pytest>=8.0`)
- `scripts/bootstrap.sh` installs the `dev` extra, so `make test-mcp` runs on a clean checkout without a missing `pytest`

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
