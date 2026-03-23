# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

### Added

- project-local `.kaidf/` runtime support for K-AIDF-compatible creator projects
- `init`, `status`, `context`, and `mentor` commands
- generator-backed `.kaidf/` initialization from the default `kobkob-kaidf-generator` spec
- project-runtime tests covering local `.kaidf/` resolution and initialization

### Changed

- repository resolution now prefers `.kaidf/` in the current project over generic repo-only defaults
- default AI controller instructions now frame the agent as a mentor and architect for creators

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
