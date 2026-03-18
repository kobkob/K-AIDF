# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

### Fixed

- removed deprecated schema loading in `src/kaidf_gen/schema.py`
- aligned the bundled JSON Schema with draft-07 compatibility to avoid validator metaschema warnings in current environments
- made `scripts/dev.sh` recreate stale virtual environments and use `python -m pip` instead of a brittle `pip` shim
- removed avoidable install and network dependence from `scripts/dev.sh` by running tests and CLI commands directly from `src/`

### Added

- baseline generator tests for output generation, force behavior, template loading, and unsafe-path handling
- additional coverage for loader/schema failures, template key normalization, and CLI success/error paths
- an initial repository contract document and machine-readable contract example for downstream agent and MCP integration

## [0.1.1] - 2026-03-17

### Added

- standard repository metadata: `CODEOWNERS`, `CONTRIBUTING.md`, and MIT license text
- development baseline: GitHub CI, PR template, and release workflow
- release hygiene: `RELEASING.md`, changelog maintenance, and tag-based GitHub releases
- quality gates: markdown linting plus `ruff` lint and format checks in CI

## [0.1.0] - 2026-03-17

### Added

- initial CLI generator for K-AIDF repository scaffolding
- YAML spec validation with JSON Schema
- packaged template library and example spec
