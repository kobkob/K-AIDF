# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows SemVer while in `0.y.z` development.

## [Unreleased]

### Added

- single-repository local indexing model driven by `AIDF_REPO_ROOT`
- real `search` and `fetch` behavior over contract-defined K-AIDF files
- optional front matter awareness for metadata IDs, titles, visibility, and document classes
- doctrine-aware categories and ranking metadata derived from manifesto/governance/best-practice content
- rigid ranking and detailed score metadata for canonical doctrine package files
- explicit tests for doctrine ranking and canonical doctrine fetch behavior
- explicit starter-variant ranking and `variant_domain` metadata for domain-specific best-practice queries

## [0.1.0] - 2026-03-17

### Added

- initial MCP server prototype with OAuth endpoints and stubbed tools
- repository initialization as a nested Git repository on `main`
- standard repository metadata: `.gitignore`, `CODEOWNERS`, `CONTRIBUTING.md`, and MIT license
- development baseline: `.editorconfig`, GitHub CI, PR template, and release workflow
- release hygiene: `RELEASING.md`, changelog maintenance, and tag-based GitHub releases
- quality gates: markdown linting plus `ruff` lint and format checks in CI
