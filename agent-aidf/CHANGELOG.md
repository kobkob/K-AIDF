# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

### Fixed

- `kob init` on a project that already has `.kaidf/` prints a short error and a hint to use `kob init --force`, and exits with code 1, instead of a Python traceback. The condition is a new `ProjectAlreadyInitializedError`, a `ValueError` subclass, so existing callers are unaffected (#57)

- `kob gen` and `kob init` work where `ensurepip` is missing, such as Kaggle and Colab. If the generator's bootstrap fails, or its `.venv` cannot import PyYAML and jsonschema, kob uses the Python that is running it when that Python has those modules, and prints a notice; otherwise it stops with a message that says what to install. The generator now runs with its source on `PYTHONPATH` in both `init` and `gen`, so no installed package is needed

### Added

- `kob --version` and `kob -v` print the installed version as `kob X.Y.Z` and exit with code 0, instead of an argument error (#58)
- `kob audit` output is rich: a tier-coloured score panel titled `KAIDF-AMM v1.0 - Audit Scorecard`, a table of dimensions with points, status (Pass, Partial, Fail) and a progress bar, and a `Remediações` panel that lists each failed check with its finding and the recommended action. `--json` is unchanged, and each check's JSON now includes its `remediation` (#56)
- the static audit checks `data/manifests/skills.yaml` in Methodology-as-Code: the file must declare a version and a non-empty list of skills, each with a unique id, a command and a permissions mapping
- every `kob audit` check has a severity (`critical`, `high`, `medium` or `low`) that says what a failure exposes. Credential and personal-data checks are critical; budget, human review and CI gate checks are high; governance artifacts are medium; structure and documentation are low. The severity is in the JSON output of each check and in the findings panel
- `kob audit --severity <level>` shows only findings at that severity or above (`--severity high` shows high and critical). `--json` always lists every check
- `kob audit --fail-under <0-100>` exits with code 1 when the score is below the value, and `kob audit --fail-on-critical` exits with code 1 when any critical finding is present. Both messages go to stderr. Without these flags `kob audit` still exits with code 0, as before

- model calls retry transient failures with exponential backoff: three attempts in total, waiting 1s and then 2s. Transient failures are HTTP 408, 429, 500, 502, 503 and 504, timeouts, and connection failures. Other HTTP errors (for example 400 or 401) are not retried. Applies to OpenAI and local Ollama
- when every attempt fails, chat returns a structured reply that starts with `[kob] Model unavailable:` and says nothing was recorded. The mentor keeps the question pending and records no interaction, so the user can answer again. Phase guidance written for contracts is skipped

### Changed

- Methodology-as-Code now has five checks of 4 points each, instead of four of 5 points, so the dimension still totals 20
- `ruff check` and `ruff format --check` are clean across `src/` and `tests/`. The cleanup covers `controller.py`, `mentor.py`, `tools.py` and their tests. The same PR also carries pending changes to those modules, which this entry does not describe (#59)
- timeouts and connection failures to the model are reported with the `[kob] Model unavailable:` reply after the retries, instead of the earlier one-line messages (`OpenAI API request timed out...`, `Could not reach local Ollama...`)

## [0.5.6] - 2026-10-20

### Added

- `kob audit [PATH] [--json]`: runs the KAIDF-AMM audit on a repository (default: the current directory). It prints the score, the tier, a breakdown by dimension, and each check that did not earn its points, with the finding. `--json` prints the full result for pipelines. A missing path exits with code 2, and a completed audit exits with code 0 whatever the score
- `audit [path]` in the interactive shell, scoring the project (or the given path) and printing the same report
- `agent_aidf.audit`: a read-only static scorecard for a K-AIDF repository (`run_audit(repo_path)`), with the five KAIDF-AMM dimensions of 20 points each, scored out of 100 and classified as Platinum (90+), Gold (75-89), Silver (60-74) or Non-Compliant / Unrated (below 60). It checks tracked files for credentials and `.env` files, the `.kaidf/` scaffold, `mentor-workflow.json`, YAML specs, Front Matter v2 coverage, the regulatory artifacts, CI workflows and blocking gates, and the budget policy in `.kaidf/policy/budget.yaml`. Each check reports the detail it found (#audit)

## [0.5.5] - 2026-10-16

### Security

- web UI `POST /api/mentor` and `POST /api/exit` now require a per-process token (`X-KAIDF-Token`, embedded in the served page as a meta tag and compared with `hmac.compare_digest`): missing token returns 401, wrong token returns 403
- web UI rejects requests whose `Host` is not `127.0.0.1`/`localhost` on the server's port (DNS-rebinding guard) and cross-origin `Origin` headers, on every route, with 403

### Changed

- removed obsolete `src/agent_aidf/cli/main.py.old` (legacy Click-based CLI with Portuguese strings), which was superseded by the current Textual+argparse architecture

### Fixed

- `is_affirmative` accepts only confirmations: `yes`, `y`, `sim`, `s`, `true`, `1` (optionally followed by a comma and more text). Completion and vague words (`done`, `pronto`, `finish`, `ok`, `accept`, `go ahead`, `correct`) no longer approve a file write or a phase acceptance, so they fall through to normal mentor chat (#31)
- `--port` is validated as a TCP port (1 to 65535) for `kob ui`/`kob serve`, the legacy `app-run` command, and the REPL `app-run` command. A bad value is a usage error (exit code 2) on the command line and a message inside the REPL, instead of a crash; the REPL no longer exits on an unknown instant app either (#31)
- an invalid `AIDF_UI_PORT` is reported on stderr and ignored in favor of the default port, instead of breaking every `kob` command (#31)
- `repo.py` document classification now matches `mcp-aidf` for the shared index contract (`contracts/index-contract/`): Portuguese doctrine keywords (`princípios`, `governança`, `maturidade`, `treinamento`, `implementação`, `certificação`) are recognized, and blank or non-string metadata values (`pack`, `maturity_level`, ...) are treated as absent instead of being kept raw (#15)
- `kob gen`/`kob compile` now resolve relative `--out` and `spec` paths against the directory you ran the command from (#39). Previously the generator subprocess ran with `cwd` set to the generator repository, so `kob gen --out ./out` wrote into the generator checkout instead of your project
- front matter parsing (`repo.py`) accepts CRLF line endings, so documents saved with Windows line endings keep their metadata (title, phase, pack, ...) instead of silently losing it (#32)

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
- `agent_aidf.__version__` now reads dynamically from package metadata (using `importlib.metadata.version()`) instead of maintaining a separate hardcoded constant, eliminating version drift where `__version__` could disagree with `pyproject.toml`

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
- deprecated `agent-aidf` as a shell command name, now that only `kob` is installed as a console script: `python -m agent_aidf.legacy_cli --help` no longer shows `usage: agent-aidf ...`, and `kob shell`'s banner/prompt now read `kob shell` / `kob>` instead of `agent-aidf shell` / `agent-aidf>`. The `agent-aidf` name is unaffected as the directory, distribution, and `agent_aidf` module name

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
