# KAIDF Agent

Terminal-first agent shell for generated K-AIDF repositories.

## Scope

This first version is a CLI and interactive shell connected to repository metadata, not a web UI.

It does three things:
- loads a local generated K-AIDF repository
- exposes doctrine-pack metadata through commands and scripts
- provides a terminal shell backed by a real AI controller when configured

## Commands

- `agent-aidf packs`
- `agent-aidf docs [--pack ...] [--phase ...] [--ethical-domain ...] [--maturity-level ...]`
- `agent-aidf find <query>`
- `agent-aidf open <id-or-path>`
- `agent-aidf chat <prompt>`
- `agent-aidf shell`

The CLI reads the repository from `--repo`, `AIDF_REPO_ROOT`, or the current directory.

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

## Next Layer

The next version should add the AI chat controller boundary on top of this metadata shell rather than replacing it.
