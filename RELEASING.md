# Releasing

## Versioning Model

This workspace repository tracks the coordination layer only. It should be versioned independently from the child repositories.

- workspace repo: document and tag coordination milestones
- `kobkob-kaidf-generator`: version is authoritative in `pyproject.toml`
- `agent-aidf`: version should be tracked by changelog and tags until code-level versioning is introduced
- `mcp-aidf`: version is currently exposed in `app.py` and should stay aligned with changelog and tags

## Pre-Push Checklist

1. Confirm the workspace root is committed.
2. Confirm each child repository is committed.
3. Confirm changelogs reflect the completed work.
4. Confirm `CONTEXT.md` states the next recommended step.
5. Confirm intended remote URLs are configured for every repository.

## Tagging Guidance

- do not tag a release version unless the changelog and version source match the commit being tagged
- for the current state, the safest next public tags are:
  - workspace root: `v0.1.0` after remote configuration
  - `agent-aidf`: `v0.1.0`
  - `mcp-aidf`: `v0.1.0`
  - `kobkob-kaidf-generator`: tag only after deciding whether the current unreleased work should become `v0.1.1` or `v0.2.0`

## Next Release Decision

Before the first public push of `kobkob-kaidf-generator`, decide whether the repository standardization and CI/release work should be:

- `v0.1.1` if treated as a backward-compatible packaging and process improvement
- `v0.2.0` if treated as a meaningful project maturity milestone

