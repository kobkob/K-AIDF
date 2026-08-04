# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

## [0.5.4] - 2026-08-04

### Added

- kob can now propose and apply real actions during the mentor workflow, via a new prompt-engineered action protocol (`agent_aidf.tools`, since local Ollama has no native tool-calling): `write_file` drafts or updates a project file, `run_shell` runs a one-shot shell command from the project root (captured output, timeout). Both are sandboxed to the project root and, by default, always paused for explicit user confirmation before anything happens - the user sees the exact proposed content/command first
- `kob --yolo`: disables the write_file/run_shell confirmation pause for the session (both CLI and TUI, and `kob --yolo ui`), applying proposed actions immediately instead. A bold warning is shown immediately in every interface - a persistent red banner in the TUI, a `rich`-rendered warning before CLI output, and a red banner in the web UI (new `yolo` field on `/api/status`). Deliberately does NOT bypass phase-acceptance confirmation, which is a methodology quality gate, not a tool-safety guardrail
- the mentor workflow's question order is now driven by the real 5 K-AIDF Basic phases (`contracts.basic_phase_definitions()`) instead of 8 unrelated doctrine categories, and a phase only reaches "done" once its artifact files under `docs/0N_.../` are actually filled in (not the generator's blank scaffold) AND the user explicitly accepts it - never from raw question/step count. `maturity.phase_progress`/`phase_snapshot` and `ProjectStatus.mentor_accepted_phases` reflect this
- kob now states a clear identity ("kob, version X, built by Kobkob LLC") and explicitly disclaims that the underlying model (e.g. OLMo) is a separate, independently-developed model, not a Kobkob LLC product - fixing a prior ambiguity that could read as attributing the model itself to Kobkob LLC
- every real chat/mentor reply now carries a short, deterministic reminder to review, verify, and decide whether to accept it - appended in code (not left to the model to remember)

### Changed

- `/shell`, `/compile`, and `/gen` are no longer TUI slash-commands (the web UI never had them). `kob shell`, `kob compile`, and `kob gen` remain fully intact as CLI subcommands; the agent's own access to that capability now goes through the confirmed `run_shell` action instead
- generic chat/`/shell` no longer draws on the K-AIDF manifesto or gets told to interpret KAIDF doctrine - that's back to being the mentor workflow's job alone, reversing an overreach from 0.5.2

### Fixed

- `/copy` and `/copy-all` in the TUI now actually reach the system clipboard: they try `pyperclip` first (xclip/xsel/wl-copy/pbcopy/Win32, reliable for local sessions) and always also fire the OSC52 terminal escape sequence as a second attempt (works over SSH). A failed `pyperclip` attempt is reported honestly instead of silently doing nothing

## [0.5.3] - 2026-07-31

### Added

- `AIDF_CHAT_TIMEOUT_SECONDS` env var to control how long kob waits for a chat/mentor reply before giving up (documented in `.env.example`); invalid or non-positive values fall back to the default. The default itself is also raised from 120s to 300s, since CPU-only/slower local machines were routinely hitting "did not respond within 120s" on otherwise-healthy requests
- `/copy` and `/copy-all` commands in the TUI, copying the last reply or the full canvas transcript to the system clipboard via Textual's OSC52-based `copy_to_clipboard()` - works over SSH and needs no clipboard tool installed locally
- "Copy last" / "Copy all" buttons on the web UI's Mentor card, using the browser clipboard API

## [0.5.2] - 2026-07-31

### Added

- kob now has a stated identity: every chat/mentor exchange (TUI, `kob shell`, the web UI) opens its system prompt with "You are kob, version {version}, running the {model} model. You are an ethical and humanized agent made by Kobkob LLC.", composed dynamically from the installed package version and the active controller's model so it can't go stale
- when asked about KAIDF, kob now grounds its answer in the actual K-AIDF manifesto document instead of speaking generically: the manifesto's full body (previously truncated to a 3-line/280-char teaser like any other document) is now injected into context whenever a query matches "kaidf", with a scoring boost so it reliably surfaces
- a live, responsive status indicator replaces the old static "Thinking..." text in both the TUI and the web UI: a randomly-picked verb (Deliberating, Marinating, Incubating, Unscrambling, Weaving, Calibrating, Churning, Concocting, Noodling, Faffing) ticks with elapsed seconds while a chat/mentor call is in flight, then resolves to "Replied in {elapsed}s ({tokens} tokens)" once the reply lands. Token counts come from Ollama's `eval_count`/`prompt_eval_count` and OpenAI's `usage`, surfaced via a new `ChatController.last_usage` side-channel and threaded through `MentorTurn.token_usage` and the web UI's `/api/mentor` response

### Changed

- `/shell`'s embedded `chat` command and the TUI's default free-text chat now use an explicitly open, unrestricted system prompt (shared by every `ChatController`, mentor included) instead of the old narrow "act as a pragmatic architect" instructions. kob still cannot read/write files or run shell commands on its own in this mode — the prompt tells it to redirect any such request to the mentor workflow, which remains the only path that actually mutates files. `/shell`'s other REPL commands (`packs`, `apps`, `contracts`, `docs`, `app-run`, `app-create`, etc.) are unchanged

### Fixed

- the TUI's `/mentor` command used to run the LLM call synchronously on the main thread, freezing the entire UI for the duration of the request; it now runs in a background worker with the same live status indicator as chat, matching how `/mentor` already behaved in the web UI

## [0.5.1] - 2026-07-30

### Fixed

- the mentor workflow now always reads and writes `.kaidf/mentor-workflow.json` — never the project root. New `project.resolve_mentor_repo_root()` requires `.kaidf/` to exist and raises a clear "Run `kob init` first" error otherwise, instead of the previous silent fallback (via `resolve_runtime_repo_root()`) that let `kob mentor`, the TUI's `/mentor`, `kob shell`'s `mentor`/`mentor-status`/`mentor-reset`, `python -m agent_aidf.legacy_cli mentor`, and the web UI's `POST /api/mentor` write mentor state outside `.kaidf/` before `kob init` had run
- the web UI surfaces this as a `400` JSON `{"error": ...}` response, and `postMentor()` in `webui/src/App.tsx` now shows that message instead of a bare `POST /api/mentor -> 400`

### Removed

- the stray root-level `mentor-workflow.json` runtime artifact that had been committed by mistake (see 27d3b13); `.gitignore` now excludes `/mentor-workflow.json` and `/.kaidf/` so local runtime state can't be committed again

### Changed

- `kob init` now generates the maturity-model and ethical-model packs by default (`kobkob-kaidf-generator`'s `kaidf.default.yaml` bundles them), so every fresh `.kaidf/` project ships with `docs/10-maturity-model/` and `docs/20-ethical-model/` without a separate `generate` call
- deprecated `agent-aidf` as a shell command name, now that only `kob` is installed as a console script: `python -m agent_aidf.legacy_cli --help` no longer shows `usage: agent-aidf ...`, and `kob shell`'s banner/prompt now read `kob shell` / `kob> ` instead of `agent-aidf shell` / `agent-aidf> `. The `agent-aidf` name is unaffected as the directory, distribution, and `agent_aidf` module name

## [0.5.0] - 2026-07-27

### Added

- `agent_aidf.controller.OllamaChatController` — a local-inference `ChatController` backed by a locally running Ollama/OLMo instance, reusing the same repo-context builder as `OpenAIResponsesController`. Connection failures return a friendly message instead of raising, so `/mentor`, `kob shell`'s `chat` command, and the TUI degrade gracefully instead of crashing when Ollama isn't running
- `build_controller()` is local-first by default: it now returns `OllamaChatController` unless `AIDF_CHAT_PROVIDER=openai` is explicitly set (`none` still forces the no-AI stub). Merely having `OPENAI_API_KEY` set in the environment no longer switches the backend — that previously caused an ambient/leftover key to silently divert `kob` to the cloud
- in the `kob` TUI, any input that isn't a recognized `/command` is no longer rejected as "Unknown command" — it's sent to the active chat controller as a prompt, and the reply streams into the canvas asynchronously (same worker-thread pattern already used for the web UI), so free text now round-trips through the local OLMo model by default
- new `agent-aidf/tests/conftest.py` with an autouse fixture forcing `AIDF_CHAT_PROVIDER=none` by default, keeping the test suite deterministic and network-free
- `DEFAULT_LOCAL_MODEL` in the TUI is now `"OLMo 3.1 local"`, shown until `make workspace-up` (see the root `Makefile`) has picked and pulled a real model tag into `AIDF_MODEL`, at which point the header reflects that exact tag

### Changed

- `active_model_label()` no longer special-cases `OpenAIResponsesController` via `isinstance`; it now also recognizes `OllamaChatController` explicitly so the local path can fall back to the friendly `OLMo 3.1 local` label instead of a raw technical tag when unconfigured

### Removed

- `agent_aidf.llm_provider.LLMProvider` and `agent_aidf.providers.olmo_local.OLMoLocalProvider` — dead code that was never wired into `build_controller()`, used a different interface shape than `ChatController`, and imported `requests`, which was never a declared dependency (would have raised `ModuleNotFoundError` if it had ever been instantiated). Superseded by `OllamaChatController` above

## [0.4.2] - 2026-07-22

### Added

- `kob ui` / `kob serve` (and `/ui`, `/serve` in the TUI) now launch a real local web UI instead of a placeholder: a React + Tailwind + shadcn-style frontend (`agent-aidf/webui/`, built output committed at `src/agent_aidf/webui_dist/`) backed by a new Flask server (`agent_aidf.webui`) exposing `GET /api/status`, `POST /api/mentor`, and `POST /api/exit`. It shows the 5 K-AIDF Basic delivery phases with live done/current/pending state and a mentor chat panel
- `agent_aidf.maturity` — shared `phase_progress()`/`phase_snapshot()` mapping mentor progress onto the 5 phases from `contracts.basic_phase_definitions()`, used by both the TUI and the web UI
- `/exit` command in the TUI: stops the web UI if one is running (via `werkzeug.serving.make_server(...).shutdown()`), then quits `kob`. The web UI has the same `/exit` typed into its own command input, which stops its own server and shows a "Session ended" screen
- `flask>=3.0` runtime dependency (matches the version already used by `mcp-aidf`)

### Changed

- in the TUI, command output and web UI request/mentor activity now share one scrolling log in the canvas (previously each command replaced the canvas contents outright)

## [0.4.1] - 2026-07-22

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
