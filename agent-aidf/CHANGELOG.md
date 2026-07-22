# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

### Added

- redesigned the `kob` TUI layout: a single bordered header with the K-AIDF logo (from the root `README.md`), the active model, and the current directory on the left, the command legend on the right, embedded as the header's border title; a canvas with a live `Current Status - K-AIDF Phase {current}/{total}` line; and a footer status bar — all values (version, model, directory, phase) are read from the running system instead of hardcoded
- `agent_aidf.i18n` — a `gettext`-based `_()` helper used by every `kob` TUI/CLI string; English is the source language and the default (no catalog required), with a `src/agent_aidf/locale/agent_aidf.pot` template for adding other languages via standard `.po`/`.mo` catalogs

### Changed

- `kob` (`agent_aidf.cli.main`) is now dual-mode: `kob` with no arguments launches an interactive [Textual](https://textual.textualize.io/) TUI (`/init`, `/status`, `/mentor [answer]`, `/shell`, `/compile`, `/gen`, `/ui`, `/serve` typed into the prompt); `kob <command> ...` with arguments still runs that command one-shot, via a new `argparse` dispatcher in `cli/main.py`, so the existing `Makefile` targets (`agent-shell`, `agent-status`, `agent-mentor*`, `agent-ui`, `generate-default/maturity/ethical`) keep working unchanged
- swapped the `click>=8.1` runtime dependency for `textual>=0.58`
- the TUI's displayed model name now reflects the controller `build_controller()` actually resolves (`OPENAI_MODEL` when `OPENAI_API_KEY` is set, otherwise `AIDF_MODEL` or the `OLMo local` default) instead of a hardcoded label

## [0.4.0] - 2026-07-19

### Added

- `kob status`, bundling the existing project/runtime status report
- `kob shell`, bundling the existing interactive terminal shell
- `kob serve [--port]` placeholder alias of `kob ui`
- `kob compile [spec] --out <dir> [--force]` / `kob gen [spec] --out <dir> [--force]`, exposing `kaidf_gen.cli generate` the same way `kob init` already shells out to the generator

### Changed

- root `Makefile`: `agent-shell`, `agent-status`, `agent-mentor`, `agent-mentor-status`, and `agent-mentor-reset` now invoke `kob` instead of `agent_aidf.legacy_cli`; added `agent-ui`
- root `Makefile`: `generate-default`, `generate-maturity`, and `generate-ethical` now invoke `kob gen` instead of the generator's own scripts directly
- `agent-context`, `agent-packs`, `agent-apps`, and the `agent-app-*` targets remain on the legacy CLI, since `kob ui`/`serve` do not yet implement real app lifecycle control

## [0.3.0] - 2026-07-19

### Added

- `kob` click-based root command group (`agent_aidf.cli.main`) as the new unified entrypoint
- `kob init [--force]`, bundling the existing `.kaidf/` generator-backed initialization
- `kob mentor [answer] [--status] [--reset]`, bundling the existing persisted mentor workflow
- `kob ui [--port]` placeholder command, to later launch the local web server daemon for the mentor UI
- `click` runtime dependency

### Changed

- renamed the legacy argparse CLI module from `agent_aidf.cli` to `agent_aidf.legacy_cli` to free the `agent_aidf.cli` package name for the new `kob` entrypoint; `Makefile` targets, `tests/test_cli.py`, and `scripts/{dev,shell,list-docs}.sh` updated accordingly
- `[project.scripts]` now installs `kob` instead of `agent-aidf`

## [0.2.0] - 2026-03-27

### Added

- project-local `.kaidf/` runtime support for K-AIDF-compatible creator projects
- `init`, `status`, `context`, and `mentor` commands
- generator-backed `.kaidf/` initialization from the default `kobkob-kaidf-generator` spec
- project-runtime tests covering local `.kaidf/` resolution and initialization
- instant app scaffolding with persistent apps under `.kaidf/apps/<app-id>` and ephemeral temp apps
- `apps`, `app-create`, and `app-open` commands for instant app lifecycle inspection
- persisted mentor workflow state with resumable quiz-style continuation via `mentor [answer]`
- mentor workflow can now create or reuse a persistent instant app and append mentor notes when answers imply a concrete prototype
- mentor workflow now refreshes the active app scaffold files and writes a structured mentor brief for implementation state
- mentor workflow can now spawn a second persistent instant app when answers explicitly shift modality or request separation
- simple runtime lifecycle commands now exist for web instant apps: run, runtime, and stop
- mentor can now auto-start the active web instant app and report the live localhost URL in its action summary
- mentor now restarts active web apps after scaffold changes and stops superseded running web apps when switching targets

### Changed

- repository resolution now prefers `.kaidf/` in the current project over generic repo-only defaults
- default AI controller instructions now frame the agent as a mentor and architect for creators
- project status and controller context now include persistent instant app inventory
- `mentor` now advances a persisted workflow instead of launching the generic shell
- mentor state now tracks the active instant app chosen by the workflow

## [0.1.1] - 2026-03-20

### Added

- Python CLI package for terminal-first repository interaction
- repository metadata loader for doctrine packs, maturity fields, and ethical-model fields
- interactive shell with `packs`, `docs`, `find`, and `open`
- operational scripts for shell and metadata consumption
- CLI tests for basic repository navigation flows
- OpenAI Responses API controller integration with stub fallback and conversation continuity support
- scored controller-context selection over pack metadata and canonical document hints

## [0.1.0] - 2026-03-17

### Added

- initial project definition for the K-AIDF agent
- repository initialization as a nested Git repository on `main`
- standard repository metadata: `.gitignore`, `CODEOWNERS`, `CONTRIBUTING.md`, and MIT license
- development baseline: `.editorconfig`, GitHub CI, PR template, and release workflow
- release hygiene: `RELEASING.md`, changelog maintenance, and tag-based GitHub releases
- quality gates: markdown linting and baseline file validation in CI
