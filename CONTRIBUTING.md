# Contributing

## Scope

This repository is the coordination layer for the K-AIDF workspace.

- keep cross-repository structure and documentation here
- do not duplicate component implementation history here; the root `CHANGELOG.md` names the component in backticks and the details live in the component's own `CHANGELOG.md`
- make component code changes in the corresponding component directory (`agent-aidf/`, `kobkob-kaidf-generator/`, `mcp-aidf/`); they are part of this repository, not separate repositories

## Branch Policy

- default branch: `main`
- keep feature work in short-lived branches
- merge changes through reviewed pull requests when practical

## Before Push

- confirm the workspace documentation matches the current state of the components
- add a `## [Unreleased]` entry to the component `CHANGELOG.md` you touched and to the root `CHANGELOG.md`
- update `CONTEXT.md` when the recommended next step changes

## Releasing

- components are not tagged or released on their own: one `vX.Y.Z` tag at the repository root releases `agent-aidf`, `kobkob-kaidf-generator` and `mcp-aidf` together, see `RELEASING.md`
