# Changelog

All notable changes to this workspace repository will be documented in this file.

The format is based on Keep a Changelog and the workspace follows SemVer while in `0.y.z` development.

## [Unreleased]

### Added

- `kobkob-kaidf-generator` `0.1.5`: the 5 K-AIDF Basic delivery phases now have their own default-spec directories (`docs/01_intent_constraints/` … `docs/05_verification_transfer/`), and `kob init` ships the maturity-model and ethical-model packs by default (see `kobkob-kaidf-generator`'s own changelog)
- `agent-aidf` `0.5.1`: the mentor workflow now always targets `.kaidf/mentor-workflow.json` across the CLI, TUI, shell, legacy CLI, and web UI, and `agent-aidf` is fully deprecated as a shell command name in favor of `kob` (see `agent-aidf`'s own changelog)
- `agent-aidf` `0.5.2`: kob now states a stable identity and grounds KAIDF answers in the manifesto, `/shell`/default chat use an open unrestricted prompt (mentor remains the only path that mutates files), and both the TUI and web UI show a live status indicator (verb + elapsed time + token count) instead of a static "Thinking..." label (see `agent-aidf`'s own changelog)
- root workspace automation via `Makefile`, shared env scripts, and `.env.example`
- `make workspace-up` now installs and starts a local OLMo-over-Ollama Docker stack sized to the host: `scripts/detect-ollama-model.sh` picks a model tag from detected RAM/disk/GPU (falling back between `olmo2:7b-1124-instruct-q4_K_M` and `olmo2:13b-1124-instruct-q4_K_M`, or erroring clearly if the machine can't run either), `scripts/workspace-up.sh` starts `docker-compose.local.yml` (now with a healthcheck and `restart: unless-stopped`, plus an optional `docker-compose.gpu.yml` NVIDIA overlay), pulls the model, and persists `AIDF_MODEL`/`OLLAMA_HOST`/`KAIDF_LOCAL_INFERENCE` into the workspace `.env`; `make workspace-down`/`workspace-logs` and a new `make agent-tui` round it out
- `.env.example` documents `AIDF_CHAT_PROVIDER`, `OLLAMA_HOST`, `AIDF_MODEL`, and `AIDF_OLLAMA_MODEL` for the new local-inference path (see `agent-aidf`'s own changelog for the `kob`-side wiring)

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
