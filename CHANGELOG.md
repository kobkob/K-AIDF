# Changelog

All notable changes to this workspace repository will be documented in this file.

The format is based on Keep a Changelog and the workspace follows SemVer while in `0.y.z` development.

## [Unreleased]

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
