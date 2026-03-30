# KAIDF Agent

Terminal-first mentor and architect agent for K-AIDF-compatible projects.

## Scope

This first version is a CLI and interactive shell connected to a project-local `.kaidf/` repository, not a web UI.

It does three things:
- initializes and maintains `.kaidf/` in the current project
- loads doctrine and pack metadata from the local K-AIDF repository
- exposes doctrine-pack metadata through commands and scripts
- provides a terminal shell backed by a real AI controller when configured
- manages project-local instant apps under `.kaidf/apps/<app-id>` for mentor-driven local workflows
- generates mentor-aware basic contracts under `.kaidf/contracts/<contract-id>` for K-AIDF delivery setup

## Commands

- `agent-aidf init [--force]`
- `agent-aidf status`
- `agent-aidf context [prompt]`
- `agent-aidf mentor [answer] [--status] [--reset]`
- `agent-aidf packs`
- `agent-aidf contracts`
- `agent-aidf contract-create [contract-id] [--brief ...] [--force]`
- `agent-aidf contract-open <contract-id-or-path>`
- `agent-aidf apps`
- `agent-aidf app-create <app-id> [--mode persistent|ephemeral] [--kind shell|web]`
- `agent-aidf app-open <app-id-or-path>`
- `agent-aidf app-run <app-id> [--port ...]`
- `agent-aidf app-runtime <app-id>`
- `agent-aidf app-stop <app-id>`
- `agent-aidf docs [--pack ...] [--phase ...] [--ethical-domain ...] [--maturity-level ...]`
- `agent-aidf find <query>`
- `agent-aidf open <id-or-path>`
- `agent-aidf chat <prompt>`
- `agent-aidf shell`

The CLI resolves runtime context in this order:
- `--repo` when you need an explicit override
- `.kaidf/` inside `--project` or the current directory
- `AIDF_REPO_ROOT` if no local `.kaidf/` exists
- the project root as a fallback for repository-style inspection

`agent-aidf init` creates `.kaidf/` by calling the local `kobkob-kaidf-generator` default spec.

## AI Controller

The shell and `chat` command use:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default: `gpt-5`)
- `OPENAI_BASE_URL` (default: `https://api.openai.com/v1`)
- `AIDF_CHAT_INSTRUCTIONS` for custom developer instructions

If `OPENAI_API_KEY` is not set, the agent falls back to a safe stub controller instead of failing.

## Mentor Workflow

The `mentor` command is now the main guided workflow entrypoint:

- `agent-aidf mentor`
  Purpose: show or resume the current pending mentor question

- `agent-aidf mentor "<answer>"`
  Purpose: record the answer, analyze it against `.kaidf/`, update the active instant app when relevant, and ask the next question

- `agent-aidf mentor --status`
  Purpose: inspect persisted workflow state, active app, and last action summary

- `agent-aidf mentor --reset`
  Purpose: clear the persisted mentor workflow state

Mentor state is stored in `.kaidf/mentor-workflow.json`.

## Basic Contracts

Persistent basic contracts live under `.kaidf/contracts/<contract-id>/`.

- `agent-aidf contracts`
  Purpose: list generated contracts

- `agent-aidf contract-create [contract-id] [--brief ...] [--force]`
  Purpose: create a mentor-aware contract scaffold that follows the five K-AIDF Basic phases

- `agent-aidf contract-open <contract-id-or-path>`
  Purpose: inspect a generated contract and its current mentor/app context

Each contract currently writes:

- `contract.json`
  Purpose: machine-readable contract metadata and the five Basic phases

- `contract.md`
  Purpose: readable contract summary with phase-by-phase responsibilities and exits

- `quiz.md`
  Purpose: phase-aligned mentor quiz prompts for the basic workflow

## Instant App Runtime

Persistent instant apps live under `.kaidf/apps/<app-id>/`.

For web apps, the runtime layer stores:

- `app-runtime.json`
  Purpose: persisted runtime state including status, pid, port, and log path

- `app-runtime.log`
  Purpose: background server stdout/stderr log

- `mentor-brief.json`
  Purpose: structured implementation brief generated from the latest mentor step

- `mentor-notes.md`
  Purpose: append-only mentor history for that app

The mentor currently uses these rules:

- reuse the current app when the workflow stays on the same implementation track
- spawn a new app when the answer changes modality or explicitly asks for a separate/new app
- refresh app files on relevant mentor steps
- start or restart the active web app automatically and report the live localhost URL
- stop a superseded running web app when the workflow switches to a different active app

## Scripts

- `scripts/dev.sh`
  Purpose: run tests and, when `AIDF_REPO_ROOT` is set, validate metadata loading through the `packs` command

- `scripts/check.sh`
  Purpose: run the test suite quickly

- `scripts/list-docs.sh`
  Purpose: invoke `agent-aidf docs` directly from a script surface

- `scripts/shell.sh`
  Purpose: start the interactive shell

## Current Features

- `.kaidf/` project runtime support
- persisted mentor workflow state in `.kaidf/mentor-workflow.json`
- persistent basic contracts under `.kaidf/contracts/`
- contract generation grounded in the K-AIDF Basic framework phases
- mentor-aware contract creation that can reuse current mentor state and active instant app context
- quiz-style mentor continuation that resumes from the last pending question
- project-local persistent instant apps under `.kaidf/apps/`
- ephemeral instant app scaffolds for throwaway local workflows
- mentor answers can create or reuse a persistent instant app and write mentor notes into that app
- mentor answers can also refresh the active app scaffold files so the app reflects the current workflow intent
- mentor can now keep refining the current app or spawn a new persistent app when the workflow shifts scope or modality
- web instant apps can now be started, inspected, and stopped through a simple persisted runtime state
- mentor-driven web app updates now auto-start the current app when needed and report the live localhost URL
- mentor now restarts the active web app after updates and stops superseded running web apps when the workflow switches apps
- path and front-matter aware repository indexing
- doctrine pack discovery
- metadata filters for:
  - `pack`
  - `phase`
  - `ethical_domain`
  - `maturity_level`
  - `assessment_type`
  - `risk_type`
- interactive shell with `packs`, `docs`, `find`, `open`, and `quit`
- explicit AI chat-controller boundary with a safe stub implementation for now
- OpenAI Responses API controller integration with repository-aware prompt context
- scored context selection that prefers pack/domain/level/risk matches over generic text matches
- project-aware `status` and `context` inspection commands
- mentor-oriented default controller instructions for creator workflows
- controller context now includes the current persistent instant app inventory
- mentor workflow state is visible in `status`, `context`, and the controller prompt
- mentor workflow can attach implementation actions to the active instant app when the answer points to a concrete prototype
- mentor-driven implementation updates now rewrite the active app `README.md`, structured brief, and runtime scaffold files

## Next Layer

The next version should deepen the mentor workflow on top of `.kaidf/`, not replace the current project/runtime model.
