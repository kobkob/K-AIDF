# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

### Added

- starter generated best-practice variant package under `docs/00-overview/best-practices/` as initial example material
- doctrine contract guidance that starter variant identity remains path-derived only
- doctrine contract guidance that starter variants remain part of the default generated baseline
- additive maturity-model doctrine pack design with pack-specific metadata fields and an example spec
- first-class optional maturity-model pack templates and generation script

## [0.1.2] - 2026-03-19

### Fixed

- removed deprecated schema loading in `src/kaidf_gen/schema.py`
- aligned the bundled JSON Schema with draft-07 compatibility to avoid validator metaschema warnings in current environments
- made `scripts/dev.sh` recreate stale virtual environments and use `python -m pip` instead of a brittle `pip` shim
- removed avoidable install and network dependence from `scripts/dev.sh` by running tests and CLI commands directly from `src/`
- prevented duplicate markdown front matter emission by rejecting stacked metadata blocks and normalizing the bundled prompt template

### Added

- baseline generator tests for output generation, force behavior, template loading, and unsafe-path handling
- additional coverage for loader/schema failures, template key normalization, and CLI success/error paths
- an initial repository contract document and machine-readable contract example for downstream agent and MCP integration
- contract refinement to expose prompt documents by default and define explicit front matter as a version 2 plan
- a concrete version 2 front matter schema and metadata-driven MCP behavior plan
- generator support for deterministic front matter emission via repo defaults, section defaults, and per-file metadata
- README-backed operational scripts for fast checks and version 2 example generation
- canonical doctrine package layout defined under `docs/00-overview/` with one stable file per doctrine area
- default generation now emits the canonical doctrine package files under `docs/00-overview/`
- canonical doctrine package files in the default spec now emit version 2 front matter by default
- canonical doctrine package files are now defined as rigid-ranking anchors for MCP doctrine queries

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
