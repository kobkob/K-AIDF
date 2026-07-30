# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

## [0.1.5] - 2026-07-30

### Changed

- the 5 K-AIDF Basic delivery phase directories in `specs/kaidf.default.yaml` are now `docs/01_intent_constraints/` … `docs/05_verification_transfer/` (underscore-separated, matching `agent-aidf`'s `contracts.py::_BASIC_PHASES` names and order), replacing the single hyphenated `docs/01-intent-constraints/` — a contract-affecting path rename, since `docs/01-intent-constraints/` no longer exists in the default spec output
- `specs/kaidf.default.yaml` now bundles the maturity-model and ethical-model additive pack sections by default, so a plain `generate`/`kob init` run produces `docs/10-maturity-model/` and `docs/20-ethical-model/` without a separate spec or `generate` call; the packs remain independently generatable via their own example specs
- `docs/contract.md` and the example specs (`specs/contract.example.yaml`, `specs/kaidf.metadata-v2.example.yaml`) updated for the new phase directory naming, required files, and default-pack inclusion

### Added

- `docs/02_discovery_mapping/`, `docs/03_design_simulation/`, `docs/04_execution_instrumentation/`, and `docs/05_verification_transfer/` template/prompt/exit-criteria scaffolding, mirroring phase 1's existing minimal-skeleton style
- `docs/01_intent_constraints/data-provenance.md` template

## [0.1.4] - 2026-03-20

### Added

- ethical-model doctrine pack plan in the contract and machine-readable contract example
- ethical-model example spec with pack-specific ethics, control, and risk metadata fields
- first-class optional ethical-model pack templates and generation script

## [0.1.3] - 2026-03-20

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
