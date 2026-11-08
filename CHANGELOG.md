# Changelog

All notable changes to this workspace repository will be documented in this file.

The format is based on Keep a Changelog and the workspace follows SemVer while in `0.y.z` development.

## [Unreleased]

### Fixed

- `mcp-aidf`: spec-compliant handshake over the MCP Streamable HTTP transport. JSON-RPC notifications such as `notifications/initialized`, and JSON-RPC responses sent by the client, are acknowledged with HTTP `202` and an empty body instead of a `-32601` error, `ping` returns an empty result, `initialize` negotiates `2024-11-05`, `2025-03-26` and `2025-06-18` (the newest on an unknown request), and an unsupported `MCP-Protocol-Version` header is refused with HTTP `400`. The official MCP SDK clients, which failed right after `initialize`, now complete the handshake; an integration test drives the official `mcp` Python SDK client against the server (see `mcp-aidf`'s own changelog)
- CLA check (`.github/workflows/cla-check.yml`): `signatures/cla.json` is the object the CLA Assistant reads (`{"signedContributors": []}`) instead of an empty list, which made the action crash on every pull request; the `pull_request_target` activity type is `synchronize` (the previous `synchronized` does not exist, so new pushes never re-ran the check); an `issue_comment` trigger lets contributors sign with the standard comment; the action is `contributor-assistant/github-action` pinned by SHA (v2.6.1) running with explicit `GITHUB_TOKEN` permissions instead of the unset `KOBKOB_CLA_PAT` secret; `eltonaquino` joins the allowlist

### Added

- `agent-aidf`: `tests/test_audit_matrix_contract.py` loads the generator's `specs/kaidf.default.yaml` and asserts its `audit_matrix` block equals `audit.py` `DIMENSION_SPECS` exactly (dimension ids, names and points; check ids, titles and points, in order), skipping with a reason when the sibling checkout is missing; the `agent-aidf` CI workflow now also runs on changes to that spec

### Changed

- `kobkob-kaidf-generator`: the `audit_matrix` block of `specs/kaidf.default.yaml` mirrors the `kob audit` engine exactly: the same five dimensions and the engine's 15 checks with their ids, titles and points, each with an `evidence` line describing what the engine verifies. The previous 16-check declarative matrix shared the KAIDF-AMM v1.0 name with the engine but was never scored by any tool; its dropped checks (regulatory mappings, pre-commit hooks, security gates, filled phase deliverables, request timeouts) are listed as planned for v1.1 in the generated `docs/30-kaidf-amm/README.md`
- `kobkob-kaidf-generator`: `docs/30-kaidf-amm/audit-matrix.csv` and the summaries and check tables of the dimension pages are rendered from the `audit_matrix` block (`content: "audit_matrix:csv"`, `<!-- audit_matrix:summary <dimension-id> -->` and `<!-- audit_matrix:checks <dimension-id> -->` markers) instead of being static templates, so they cannot drift from it. The generated README, dimension pages and report template say that v1.0 scores the presence and parseability of the listed artifacts, not their substance

## [0.6.1] - 2026-11-06

Security hardening release. Consolidates PRs #85 and #86, which close #67, #68, #78 and #79.

### Security

- `agent-aidf` `kob -x` (#68, PR #86): a remote (`https://`) extension installs only after the operator approves a summary (name, author, version, source, SHA-256) with `[y/N]`, or with `--yes`. Without a terminal, a remote install fails unless `--yes` is given. `--sha256 <hash>` pins the archive digest for remote and local sources and is checked before extraction
- `agent-aidf` extensions can no longer preempt built-in commands (#78, PR #85): built-in subcommands are never offered to extension handlers, top-level extension handlers run only when no subcommand is given, and an extension subcommand that reuses a built-in or already-claimed name is refused with a warning
- `agent-aidf` `kob audit` credential scan (#79, PR #85) recognizes OpenAI project keys, GitHub tokens (`ghp_`, `github_pat_`), Slack tokens (`xox[bap]-`) and Stripe live keys. Files over 1 MB are named in the check detail as not scanned

### Fixed

- `agent-aidf` `Words` extension (#67, PR #85) answers only when the whole prompt is a presentation question or greeting, with an optional short greeting before and closing word after. A phrase inside a request, such as `traduza 'how are you'`, now reaches the model

## [0.6.0] - 2026-10-30

General availability. This release consolidates the 0.6.0 milestones:

### Highlights

- **KAIDF-AMM Engine:** a deterministic governance audit engine with a dedicated taxonomy of dimensions, checks and severities, backed by a comprehensive unit test suite (`agent-aidf`, `kobkob-kaidf-generator`)
- **MCP Maturity Tools:** `get_maturity_scorecard` and `evaluate_repository_maturity` for audit and automated generation of a mitigation backlog (`mcp-aidf`)
- **Dynamic Extensions Runtime:** a dynamic module system under `ext/` supporting the core `Ext` and `Words` modules (`agent-aidf`)
- **Model Flexibility:** dynamic support for local and remote models through `--model` and standardized environment variables (`agent-aidf`)
- **Enterprise LocalAI Stack:** the `docker-compose.localai.yml` manifest, the `make workspace-localai` automation and B2B inference documentation

### Added

- `agent-aidf` `kob audit`: a read-only KAIDF-AMM v1.0 scorecard for a repository (five dimensions, per-check severities, `--severity`, `--json`, `--fail-under`, `--fail-on-critical`), also available as `audit [path]` in the shell. The generator ships the `kaidf-audit` skill manifest it checks (see `agent-aidf` and `kobkob-kaidf-generator` changelogs)
- `mcp-aidf` maturity tools: `get_maturity_scorecard` and `evaluate_repository_maturity`, built on the `agent-aidf` audit engine, with path confinement under `AIDF_REPO_ROOT`, primary-token-only evaluation, and a `503` when `agent-aidf` is not installed (see `mcp-aidf`'s own changelog)
- `agent-aidf` runtime extension system: kob scans the built-in `ext/` directory and `$KOB_EXTENSIONS_DIR` at boot, extensions can add flags, subcommands and handlers, `kob -x <source>` installs a `.tgz` from a local path or `https://` URL, and the core `Words` extension answers presentation questions
- `agent-aidf` `kob --model <name>` picks the model for a single run across `mentor`, `shell`, `ui` and `serve`; the web UI header shows the kob logo
- `kobkob-kaidf-generator` bootstrap falls back to cloud environments (Kaggle/Colab) when the default path is unavailable
- `docker-compose.localai.yml` and `make workspace-localai` / `make workspace-localai-down`: a LocalAI stack with an OpenAI-compatible API on port 8080. The first boot downloads the AIO models and backends; the `/readyz` healthcheck allows 20 minutes of `start_period` for that. Backends persist in the named volume `localai-backends`, so a recreated container does not download them again. Warm boots still take about 7 minutes because the AIO image re-imports its preloaded models on every start (see `docs/00-overview/inference-providers.md`)
- `docs/00-overview/inference-providers.md`: provider architecture (Ollama vs. LocalAI vs. OpenAI/Groq), the `kob` environment variables that select and point the provider, and the on-premises deployment steps. `./models/` is ignored by Git
- `kobkob-kaidf-generator` `0.1.5`: the 5 K-AIDF Basic delivery phases now have their own default-spec directories (`docs/01_intent_constraints/` … `docs/05_verification_transfer/`), and `kob init` ships the maturity-model and ethical-model packs by default (see `kobkob-kaidf-generator`'s own changelog)
- `agent-aidf` `0.5.1`: the mentor workflow now always targets `.kaidf/mentor-workflow.json` across the CLI, TUI, shell, legacy CLI, and web UI, and `agent-aidf` is fully deprecated as a shell command name in favor of `kob` (see `agent-aidf`'s own changelog)
- `agent-aidf` `0.5.2`: kob now states a stable identity and grounds KAIDF answers in the manifesto, `/shell`/default chat use an open unrestricted prompt (mentor remains the only path that mutates files), and both the TUI and web UI show a live status indicator (verb + elapsed time + token count) instead of a static "Thinking..." label (see `agent-aidf`'s own changelog)
- `agent-aidf` `0.5.3`: the chat/mentor request timeout is now configurable via `AIDF_CHAT_TIMEOUT_SECONDS` (default raised from 120s to 300s for slower machines), and both the TUI (`/copy`, `/copy-all`) and web UI ("Copy last", "Copy all") can now copy replies out to the system clipboard (see `agent-aidf`'s own changelog)
- `agent-aidf` `0.5.4`: mentor's question order now follows the real 5 K-AIDF Basic phases with completion gated on actual filled-in artifacts plus explicit acceptance (not raw step count); kob can propose confirmed `write_file`/`run_shell` actions during mentor, with a new `kob --yolo` mode to skip that confirmation (always with a bold warning banner); `/shell`, `/compile`, `/gen` are CLI-only now; the `/copy` clipboard bug is fixed; and kob's identity no longer misattributes the underlying model to Kobkob LLC (see `agent-aidf`'s own changelog)
- root workspace automation via `Makefile`, shared env scripts, and `.env.example`
- `make workspace-up` now installs and starts a local OLMo-over-Ollama Docker stack sized to the host: `scripts/detect-ollama-model.sh` picks a model tag from detected RAM/disk/GPU (falling back between `olmo2:7b-1124-instruct-q4_K_M` and `olmo2:13b-1124-instruct-q4_K_M`, or erroring clearly if the machine can't run either), `scripts/workspace-up.sh` starts `docker-compose.local.yml` (now with a healthcheck and `restart: unless-stopped`, plus an optional `docker-compose.gpu.yml` NVIDIA overlay), pulls the model, and persists `AIDF_MODEL`/`OLLAMA_HOST`/`KAIDF_LOCAL_INFERENCE` into the workspace `.env`; `make workspace-down`/`workspace-logs` and a new `make agent-tui` round it out
- `.env.example` documents `AIDF_CHAT_PROVIDER`, `OLLAMA_HOST`, `AIDF_MODEL`, and `AIDF_OLLAMA_MODEL` for the new local-inference path (see `agent-aidf`'s own changelog for the `kob`-side wiring)
- `docker-compose.localai.yml` adds a LocalAI stack (OpenAI-compatible API on port 8080, models mounted from `./models`, CPU image by default with documented NVIDIA GPU activation, and a `/readyz` healthcheck); `make workspace-localai` starts it and waits until the API is ready, and `make workspace-localai-down` stops it
- `docs/00-overview/inference-providers.md` documents the plug-and-play inference architecture (Ollama vs. LocalAI vs. OpenAI/Groq cloud), the `kob` environment variables that select and point the provider, and the on-premises deployment steps; `./models/` is ignored by Git

### Security

- `mcp-aidf` (#29): the Docker image now runs as an unprivileged `appuser` and serves the app with `gunicorn` instead of the Flask development server; `requirements.txt` pins every runtime dependency (Flask `3.1.3`, Werkzeug, PyYAML, gunicorn, and transitive packages) instead of `Flask==3.0.0` plus an unpinned `PyYAML`; the hardcoded `SECRET_KEY` placeholders are gone (`docker-compose.yml` now requires `SECRET_KEY` from the environment, `.env.example` and `scripts/env-common.sh` no longer default to `change-me`, and `scripts/load-mcp-env.sh` no longer prints the secret); without `SECRET_KEY`, direct runs of `app.py` use a random per-process secret instead of `dev-key-change-in-prod` (see `mcp-aidf`'s own changelog)
- `agent-aidf` (#30): the web UI's `POST /api/mentor` and `POST /api/exit` require a per-process token (`X-KAIDF-Token`, 401 when missing, 403 when wrong), and every route rejects non-loopback `Host` and cross-origin `Origin` headers with 403 (see `agent-aidf`'s own changelog)
- `kobkob-kaidf-generator` (#22): `load_template_by_key` rejects keys that resolve outside the packaged template library (e.g. `../../etc/passwd`) with `UnsafePathError` (see `kobkob-kaidf-generator`'s own changelog)

## [0.1.3] - 2026-03-20

### Added

- workspace context tracking for ethical-model pack planning, packaging, and MCP integration

## [0.1.2] - 2026-03-20

### Added

- workspace context tracking for starter doctrine variants, additive doctrine packs, and maturity-model pack integration

## [0.1.1] - 2026-03-19

### Added

- workspace context updates tracking generator hardening, contract work, operational scripts, and downstream next steps

## [0.1.0] - 2026-03-17

### Added

- root workspace documentation and MIT license
- root repository standards: `.gitignore`, `.editorconfig`, `CODEOWNERS`, and `CONTRIBUTING.md`
- workspace context tracking in `CONTEXT.md`
- documented project structure for the nested `kobkob-kaidf-generator`, `agent-aidf`, and `mcp-aidf` repositories
- remote and release guidance for the workspace and child repositories
