# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

### Fixed

- removed deprecated schema loading in `src/kaidf_gen/schema.py`
- aligned the bundled JSON Schema with draft-07 compatibility to avoid validator metaschema warnings in current environments

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
