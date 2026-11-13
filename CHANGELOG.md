# Changelog

All notable changes to this workspace repository will be documented in this file.

The format is based on Keep a Changelog and the workspace follows SemVer while in `0.y.z` development.

## [Unreleased]

### Fixed

- Changelog sections for the tags v0.4.2, v0.5.5 and v0.5.6, which were missing between 0.6.0 and 0.1.3; the repeated LocalAI and inference-providers bullets of 0.6.0 are removed. `agent-aidf/webui/package.json` (still 0.1.0) joins the version sources: `scripts/bump-version.sh` sets it and `scripts/check-version.sh` checks it (#113)
- `docker-compose.local.yml`: the Ollama service publishes its port on loopback only (`127.0.0.1:11434`), since Ollama has no authentication and Docker's port publishing bypasses ufw, and the image is pinned by digest instead of `latest` (#112)
- `agent-aidf` `kob audit` scores the layouts `kob init` and the generator actually produce: the scaffold is `<root>/.kaidf/` when it exists, else the audited root itself, and scaffold-owned artifacts (`README.md` and `docs/`, `mentor-workflow.json`, `policy/*.yaml`, `specs/*.yaml`, `docs/20-ethical-model/*.json`, `data/manifests/*.yaml`) are looked up there first and then at the root, while the credential scan and CI checks stay on the root. Before, a fresh `kob init` project could not reach 100 and a standalone generated repository could not earn 43 points. Details and remediations name the path that was checked, and the report and JSON output state the scaffold path. In a repository audited without `.kaidf/` the `mentor-state` remediation no longer asks to run `kob mentor`, which only runs inside a project (related: #16)
- `kobkob-kaidf-generator`: `kaidf_gen.__version__` is read from the package metadata instead of a hard-coded `0.1.0`; the `dev` extra declares `packaging` for the test that checks it (#81)
- `mcp-aidf`: spec-compliant handshake over the MCP Streamable HTTP transport. JSON-RPC notifications such as `notifications/initialized`, and JSON-RPC responses sent by the client, are acknowledged with HTTP `202` and an empty body instead of a `-32601` error, `ping` returns an empty result, `initialize` negotiates `2024-11-05`, `2025-03-26` and `2025-06-18` (the newest on an unknown request), and an unsupported `MCP-Protocol-Version` header is refused with HTTP `400`. The official MCP SDK clients, which failed right after `initialize`, now complete the handshake; an integration test drives the official `mcp` Python SDK client against the server (see `mcp-aidf`'s own changelog)
- CLA check (`.github/workflows/cla-check.yml`): `signatures/cla.json` is the object the CLA Assistant reads (`{"signedContributors": []}`) instead of an empty list, which made the action crash on every pull request; the `pull_request_target` activity type is `synchronize` (the previous `synchronized` does not exist, so new pushes never re-ran the check); an `issue_comment` trigger lets contributors sign with the standard comment; the action is `contributor-assistant/github-action` pinned by SHA (v2.6.1) running with explicit `GITHUB_TOKEN` permissions instead of the unset `KOBKOB_CLA_PAT` secret; `eltonaquino` joins the allowlist

### Added

- `mcp-aidf` container image bundles the `agent-aidf` audit engine and `git` (#71), so `evaluate_repository_maturity` and `get_maturity_scorecard` answer `200` in the container. The image is built from the repository root (`docker build -f mcp-aidf/Dockerfile .`), with a `HEALTHCHECK` on the protected-resource metadata and a `.dockerignore` for the root context. `mcp-aidf/scripts/check-image.sh` builds it and checks the tools, and the `mcp-aidf CI` workflow runs it in an `image` job
- `deploy/easypanel/easypanel.json` (#137): an EasyPanel schema for `mcp-aidf`, imported with the panel's "Create From Schema". It creates one App service built from this repository (build path `/mcp-aidf`, `Dockerfile`, branch `main`), a domain on the service's generated host that targets container port `8000`, a `workspace` volume mounted at `/workspace`, and the environment `PORT=8000`, `MCP_PUBLIC_URL=https://$(PRIMARY_DOMAIN)`, `AIDF_REPO_ROOT=/workspace` and an empty `MCP_BEARER_TOKEN` to fill in before the first deploy. `deploy/easypanel/README.md` describes the file
- `docs/06-deploy/` (#137): a deployment section with the EasyPanel guide (`easypanel.md`): importing the template, the two `/workspace` layouts and how to fill the volume, verification with `curl`, connecting Claude Code, Claude Desktop (through `mcp-remote`), Cursor and Roo Code with the bearer token, current limitations and troubleshooting
- `agent-aidf` per-command help (#92): every built-in command's `-h` shows a description and worked examples, and the new `kob help` lists the commands (one line each) while `kob help <command>` prints the same page as `kob <command> -h`, including nested commands such as `kob help ext list`. `kob audit` documents `--severity`, `--fail-under`, `--fail-on-critical` and `--json` with their exit codes, `kob ext` documents the `-x` install flag, and `kob appliance` documents `init` and `template`. An unknown command name fails with exit code `2` and suggests the closest match. `help` is a reserved command name that extensions cannot claim
- `agent-aidf` `kob ext list` (#88): read-only inventory of the built-in and user extensions with their version, author, origin, load state (loaded, failed, disabled or shadowed), CLI arguments, top-level handlers, subcommands and prompt interceptors. User extensions show install integrity: the installer now writes `.kob-install.json` (archive SHA-256 and per-file SHA-256), and the listing reports `verified`, `MODIFIED` (with the changed files), `no-record` or `unreadable`. `--json` prints the same inventory as `schema_version: 1`
- `agent-aidf` `kob appliance init --from-notebook <file.ipynb>` (#87): reads the settings in the notebook cell tagged `kaidf-config` (a fenced YAML block: `project_name`, `model`, `audit_fail_under`) without running any cell, creates `.kaidf/` when it is missing, and records the settings with the notebook's name, title and SHA-256 in `.kaidf/appliance.yaml`. Notebooks that carry secret-looking keys are refused. `kob appliance template <file.ipynb>` writes a starter notebook for Google Colab, Kaggle and JupyterLab (install, init and audit cells)
- `agent-aidf` placeholder rule in `kob audit`: a YAML or JSON artifact whose top-level key `placeholder` is `true` scores 0 with a "fill in" remediation instead of a "create" one; `kob init` records the spec it used as `.kaidf/specs/kaidf.yaml`
- `kobkob-kaidf-generator` default scaffold ships `policy/pii-masking-rules.yaml`, `policy/hitl-config.yaml`, `policy/budget.yaml`, `docs/20-ethical-model/risk-assessment.json`, `docs/20-ethical-model/explicability-schema.json` and `data/manifests/dataset-audit.yaml` as marked placeholders with guidance, so every `kob audit` check is reachable from a generated repository; `docs/contract.md` and the `docs/30-kaidf-amm/` pages describe the layout and placeholder rules (related: #16)
- `mcp-aidf` `evaluate_repository_maturity` reports `scaffold_path`, where the engine looked for the scaffold-owned artifacts (`<repo_root>/.kaidf` in a `kob init` project, `repo_root` itself for a generated repository audited directly), since every remediation path in the backlog depends on it (related: #16)
- `agent-aidf`: `tests/test_audit_matrix_contract.py` loads the generator's `specs/kaidf.default.yaml` and asserts its `audit_matrix` block equals `audit.py` `DIMENSION_SPECS` exactly (dimension ids, names and points; check ids, titles and points, in order), skipping with a reason when the sibling checkout is missing; the `agent-aidf` CI workflow now also runs on changes to that spec
- `.github/workflows/release.yml`: one release workflow at the repository root, run on `v*` tags. `verify-version` checks the tag against the version in the three `pyproject.toml` files and `SERVER_VERSION` in `mcp-aidf/app.py`, and requires a `## [<version>]` heading in the four changelogs; the three component CI workflows then run through `workflow_call`; `build` makes the `agent-aidf` and `kobkob-kaidf-generator` sdists and wheels and a versioned `mcp-aidf` tarball; `release` publishes them in a GitHub Release with generated notes, as a prerelease for tags that contain a `-` (for example `-rcN`). Every action is pinned by commit SHA. PyPI publishing is left out until a trusted publisher exists
- `scripts/bump-version.sh <version>` sets the four version sites and reports which changelogs still need a `## [<version>]` section; `scripts/check-version.sh <version>` is the check the workflow runs, also available as `make check-version VERSION=x.y.z` (and `make bump-version VERSION=x.y.z`)
- `.github/PULL_REQUEST_TEMPLATE.md` at the root, consolidating the three nested templates

### Changed

- `mcp-aidf` container image: the listen port comes from the `PORT` environment variable, default `7777` as before, so `mcp-aidf/docker-compose.yml` is unaffected (#137; see `mcp-aidf`'s own changelog)
- `mcp-aidf CI` also runs when `deploy/**` or `docs/**` change: `tests/test_easypanel_template.py` checks the EasyPanel template against the Dockerfile and `app.py`, and `tests/test_workspace_docs.py` indexes the workspace `docs/` tree, now including `06-deploy` (#137)
- `docs/` reorganised into numbered sections (#93): `01-basics/` (quickstart, installation, concepts), `02-architecture/` (the five KAIDF-AMM dimensions, the extension runtime, security), `03-commands/` (a reference page per `kob` command), `04-interfaces/` (WebUI and TUI) and `05-models/` (inference providers, `AIDF_MODEL` precedence), with an index at `docs/README.md`. `docs/00-overview/inference-providers.md` moved to `docs/05-models/inference-providers.md`
- `mcp-aidf` indexes the workspace `docs/` sections: a document under `docs/<section>/` takes the section as its `phase`, and a file directly under `docs/` (such as the index) is in phase `root`. The canonical doctrine paths under `docs/00-overview/` are unchanged, because `contracts/index-contract` and generated repositories depend on them (#93)
- `kobkob-kaidf-generator`: the `audit_matrix` block of `specs/kaidf.default.yaml` mirrors the `kob audit` engine exactly: the same five dimensions and the engine's 15 checks with their ids, titles and points, each with an `evidence` line describing what the engine verifies. The previous 16-check declarative matrix shared the KAIDF-AMM v1.0 name with the engine but was never scored by any tool; its dropped checks (regulatory mappings, pre-commit hooks, security gates, filled phase deliverables, request timeouts) are listed as planned for v1.1 in the generated `docs/30-kaidf-amm/README.md`
- `kobkob-kaidf-generator`: `docs/30-kaidf-amm/audit-matrix.csv` and the summaries and check tables of the dimension pages are rendered from the `audit_matrix` block (`content: "audit_matrix:csv"`, `<!-- audit_matrix:summary <dimension-id> -->` and `<!-- audit_matrix:checks <dimension-id> -->` markers) instead of being static templates, so they cannot drift from it. The generated README, dimension pages and report template say that v1.0 scores the presence and parseability of the listed artifacts, not their substance
- `RELEASING.md` describes the monorepo flow: one `vX.Y.Z` tag releases the three components, with the bump, changelog, commit and tag steps and what the workflow verifies and builds. The component `RELEASING.md` files point to it, and `CONTRIBUTING.md` no longer describes the components as separately committed and tagged repositories
- `kobkob-kaidf-generator`, `mcp-aidf`: added the `0.6.1` changelog section that the `v0.6.1` bump had left out (both ship `0.6.1` with no functional changes)

### Removed

- the nested `agent-aidf/.github/`, `kobkob-kaidf-generator/.github/` and `mcp-aidf/.github/` directories. GitHub Actions only reads the root `.github/workflows/`, so their `release.yml` never ran: tags `v0.5.5`, `v0.5.6`, `v0.6.0-rc1`, `v0.6.0` and `v0.6.1` produced no build, no GitHub Release and no tag-time verification

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

### Security

- `mcp-aidf` (#29): the Docker image now runs as an unprivileged `appuser` and serves the app with `gunicorn` instead of the Flask development server; `requirements.txt` pins every runtime dependency (Flask `3.1.3`, Werkzeug, PyYAML, gunicorn, and transitive packages) instead of `Flask==3.0.0` plus an unpinned `PyYAML`; the hardcoded `SECRET_KEY` placeholders are gone (`docker-compose.yml` now requires `SECRET_KEY` from the environment, `.env.example` and `scripts/env-common.sh` no longer default to `change-me`, and `scripts/load-mcp-env.sh` no longer prints the secret); without `SECRET_KEY`, direct runs of `app.py` use a random per-process secret instead of `dev-key-change-in-prod` (see `mcp-aidf`'s own changelog)
- `agent-aidf` (#30): the web UI's `POST /api/mentor` and `POST /api/exit` require a per-process token (`X-KAIDF-Token`, 401 when missing, 403 when wrong), and every route rejects non-loopback `Host` and cross-origin `Origin` headers with 403 (see `agent-aidf`'s own changelog)
- `kobkob-kaidf-generator` (#22): `load_template_by_key` rejects keys that resolve outside the packaged template library (e.g. `../../etc/passwd`) with `UnsafePathError` (see `kobkob-kaidf-generator`'s own changelog)

## [0.5.6] - 2026-10-20

### Added

- `agent-aidf` KAIDF-AMM v1.0 audit: the five-dimension audit matrix spec (#50), the audit engine that scores a repository against it (#51), and the `kob audit` command with its REPL integration (#52)

## [0.5.5] - 2026-10-16

### Security

- `agent-aidf` (#30): the web UI routes require the per-process token and reject foreign `Origin` and `Host` headers
- `agent-aidf` (#22): template loading rejects paths that resolve outside the packaged template library (path traversal)
- `mcp-aidf` (#27): internal error details are no longer returned to clients, the protocol version is validated, and `signatures/cla.json` is initialized

### Fixed

- `kobkob-kaidf-generator` (#23, #24): malformed YAML is handled cleanly and duplicate spec paths are rejected
- `kobkob-kaidf-generator` (#13): front matter v2 across every generated document template
- `agent-aidf` (#32): CRLF line endings and UTF-8 Portuguese titles in front matter
- `kob gen` (#39): relative `--out` and `--spec` paths resolve against the caller's working directory
- `agent-aidf` (#31): `is_affirmative` is stricter and `--port` is range-checked
- `mcp-aidf` (#15, #26): indexing is shared with `agent-aidf` and cached
- workflows (#44, #45): root GitHub workflows consolidated, the CLA check fixed for `main`, and lint enforced as a blocking CI step

## [0.4.2] - 2026-07-23

### Added

- `agent-aidf` interactive Textual TUI, dual-mode with the one-shot CLI, with a redesigned layout and i18n scaffolding
- `agent-aidf` web UI (React, shadcn and Flask) with `/exit`
- `kob` CLI with `status`, `shell`, `serve`, `compile` and `gen` commands, and local Ollama/OLMo inference scaffolding

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
