# Workspace Context

## What This Workspace Is

This directory is a coordination workspace for three nested Git repositories:

- `kobkob-kaidf-generator`
- `agent-aidf`
- `mcp-aidf`

The root directory documents how they fit together. Each child project owns its own history, CI, release flow, and lifecycle.

## Current State

### `kobkob-kaidf-generator`

- branch: `main`
- repository metadata is standardized
- CI, PR template, release workflow, changelog, and releasing guide are in place
- quality gates are defined with markdown linting and `ruff`
- tests pass locally with `PYTHONPATH=src python -m pytest -q`
- schema loading no longer uses deprecated `importlib.resources.open_text`
- bundled JSON Schema is aligned with draft-07 compatibility for current validator support
- `scripts/dev.sh` now recreates broken local virtual environments and runs the dev loop directly from `src/`
- baseline generator coverage now includes generation flow, force behavior, template lookup, and unsafe-path handling
- generator coverage now also includes loader/schema failures, template key normalization, and CLI success/error paths
- an initial generated-repository contract now exists in `kobkob-kaidf-generator/docs/contract.md`
- the contract now treats prompt documents as exposed by default for MCP indexing and plans explicit front matter for contract version 2
- the contract now includes a concrete version 2 YAML front matter shape and metadata-driven MCP behavior plan
- the generator spec now supports deterministic front matter emission through repo defaults, section defaults, and per-file metadata
- the generator now has a documented script surface in the README: `dev.sh`, `check.sh`, and `generate-v2-example.sh`
- the contract now defines a canonical doctrine package layout under `docs/00-overview/`
- the default generator spec now emits the canonical doctrine package under `docs/00-overview/`
- the canonical doctrine package is now explicitly version 2 and treated as a rigid-ranking anchor set in `mcp-aidf`
- the default generator spec now also emits an initial best-practice variant package under `docs/00-overview/best-practices/`

### `agent-aidf`

- initialized as a nested Git repository on `main`
- repository metadata, CI, PR template, changelog, and releasing guide are in place
- current CI checks baseline documentation and markdown quality
- still a project stub with README-level definition

### `mcp-aidf`

- initialized as a nested Git repository on `main`
- repository metadata, CI, PR template, changelog, and releasing guide are in place
- quality gates are defined with markdown linting and `ruff`
- now implements the simplest useful content model: one configured local K-AIDF repository root
- real `search` and `fetch` behavior now work over contract-defined files with optional front matter awareness
- now applies a doctrine-aware interpretation layer for manifesto, principles, best practices, governance, maturity, implementation, and training content
- explicit tests now cover doctrine ranking, canonical doctrine fetch behavior, and MCP search result metadata
- the canonical generic doctrine package now has a first variant path model for sector-specific best-practice documents under `docs/00-overview/best-practices/`
- local runtime validation passes with:

```bash
python -m py_compile app.py
python -c "import app"
```

## What Was Just Completed

- root workspace documentation and MIT license
- root repository standards and release guidance
- nested repository initialization for `agent-aidf` and `mcp-aidf`
- branch normalization to `main`
- `.gitignore` baselines
- per-repo `CODEOWNERS` and `CONTRIBUTING.md`
- development baseline with `.editorconfig`, CI, and PR templates
- release baseline with changelogs, releasing guides, and tag-driven release workflows
- CI quality gates with markdown linting and repo-appropriate validation
- generator warning cleanup, baseline test expansion, CLI coverage, documented operational scripts, initial version 2 metadata implementation, doctrine-aware MCP interpretation, canonical doctrine package design, default doctrine emission, and rigid doctrine ranking

## Known Rough Edges

### `kobkob-kaidf-generator`

- local `ruff` checks were added to CI but were not run in this sandbox because `ruff` is not installed here

## Remote Status

- workspace root: `origin` configured as `https://github.com/kobkob/K-AIDF.git`
- `kobkob-kaidf-generator`: `origin` configured as `https://github.com/kobkob/kobkob-kaidf-generator.git`
- `agent-aidf`: `origin` configured as `https://github.com/kobkob/agent-aidf.git`
- `mcp-aidf`: `origin` configured as `https://github.com/kobkob/mcp-aidf.git`

## Next Recommended Step

Move from baseline generator hardening into broader contract work:

1. verify the new lint/format gates locally once `ruff` is available
2. formalize how `mcp-aidf` should rank domain-specific best-practice variants for specific queries without weakening canonical doctrine precedence
3. decide whether doctrine variant categories should remain path-derived only or gain explicit metadata later

## Resume Point

If work resumes later, continue with:

local lint verification, then doctrine variant ranking and metadata refinement
