# KAIDF Agent

Terminal-first mentor and architect agent for K-AIDF-compatible projects.

## Scope

This first version is a CLI and interactive shell connected to a project-local `.kaidf/` repository, not a web UI.

It does three things:
- initializes and maintains `.kaidf/` in the current project
- loads doctrine and pack metadata from the local K-AIDF repository
- exposes doctrine-pack metadata through commands and scripts
- provides a terminal shell backed by a real AI controller when configured

## Commands

- `agent-aidf init [--force]`
- `agent-aidf status`
- `agent-aidf context [prompt]`
- `agent-aidf mentor`
- `agent-aidf packs`
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

## Next Layer

The next version should deepen the mentor workflow on top of `.kaidf/`, not replace the current project/runtime model.
