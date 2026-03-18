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
- one unrelated local modification exists in `scripts/dev.sh`

### `agent-aidf`

- initialized as a nested Git repository on `main`
- repository metadata, CI, PR template, changelog, and releasing guide are in place
- current CI checks baseline documentation and markdown quality
- still a project stub with README-level definition

### `mcp-aidf`

- initialized as a nested Git repository on `main`
- repository metadata, CI, PR template, changelog, and releasing guide are in place
- quality gates are defined with markdown linting and `ruff`
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

## Known Rough Edges

### `kobkob-kaidf-generator`

- tests emit a deprecation warning from `importlib.resources.open_text` in `src/kaidf_gen/schema.py`
- tests emit a JSON Schema metaschema warning
- local `ruff` checks were added to CI but were not run in this sandbox because `ruff` is not installed here

## Remote Status

- workspace root: `origin` configured as `https://github.com/kobkob/K-AIDF.git`
- `kobkob-kaidf-generator`: `origin` configured as `https://github.com/kobkob/kobkob-kaidf-generator.git`
- `agent-aidf`: `origin` configured as `https://github.com/kobkob/agent-aidf.git`
- `mcp-aidf`: `origin` configured as `https://github.com/kobkob/mcp-aidf.git`

## Next Recommended Step

Finalize repository versioning and remote configuration before first push, then clean up the generator rough edges:

1. decide the initial public version tags for the workspace root, `agent-aidf`, and `mcp-aidf`
2. decide the next public version tag for `kobkob-kaidf-generator`
3. replace deprecated schema loading in `src/kaidf_gen/schema.py`
4. fix or modernize the JSON Schema declaration to remove the metaschema warning
5. verify the new lint/format gates locally once `ruff` is available

## Resume Point

If work resumes later, continue with:

repository tagging decisions, then `kobkob-kaidf-generator` warning cleanup
