# K-AIDF Workspace

This directory is a workspace that groups three related K-AIDF projects as nested Git repositories.

## Purpose

The intent is to keep the K-AIDF ecosystem split by responsibility:

- `kobkob-kaidf-generator`: generates K-AIDF repository scaffolds from declarative YAML specs
- `mcp-aidf`: exposes K-AIDF content through an MCP server for ChatGPT and other MCP clients
- `agent-aidf`: hosts the interactive agent surfaces that operate on top of a K-AIDF repository structure

This root directory is the coordination layer. It documents how the projects fit together, but the implementation history and release lifecycle of each component should remain inside its own nested repository.

## Repository Layout

```text
K-AIDF/
├── agent-aidf/
├── kobkob-kaidf-generator/
├── mcp-aidf/
├── LICENSE
└── README.md
```

## Recommended System Model

The cleanest way to think about the workspace is as a pipeline:

1. `kobkob-kaidf-generator` defines and generates the canonical K-AIDF file and folder structure.
2. `agent-aidf` consumes that structure to guide user workflows in CLI and web interfaces.
3. `mcp-aidf` publishes selected K-AIDF content and search/fetch capabilities to external AI clients through MCP.

That separation keeps concerns clear:

- generation logic stays isolated from runtime agent behavior
- external protocol and auth concerns stay isolated from the core methodology tooling
- each project can version, test, and deploy independently

## Boundaries

Use these boundaries to avoid architectural drift:

- `kobkob-kaidf-generator` should own spec parsing, schema validation, template packaging, and scaffold generation
- `agent-aidf` should own orchestration UX, prompt flows, local project interaction, and user-facing workflows
- `mcp-aidf` should own MCP protocol handling, OAuth, indexing, search, fetch, and connector-facing integration

Avoid duplicating K-AIDF document semantics across all three projects. The generator should remain the source of truth for structure, while the agent and MCP server should consume generated repositories or shared exported artifacts.

## Integration Direction

A practical integration direction for the three repositories is:

- define a stable generated document layout in `kobkob-kaidf-generator`
- make `agent-aidf` read and operate against that layout directly
- make `mcp-aidf` index or fetch from generated K-AIDF repositories rather than inventing a separate content model

If shared contracts become necessary, keep them small and explicit:

- folder and file naming conventions
- front matter or metadata conventions
- document identifiers for MCP `fetch`
- indexing rules for MCP `search`

## Workspace Conventions

- each subdirectory is intended to be its own Git repository
- this root directory serves as workspace documentation, not as the primary source tree for any one component
- cross-project changes should be coordinated by updating the relevant child repositories, not by collapsing the projects into one codebase

## Workspace Automation

The root workspace now includes:

- `Makefile`
  Purpose: common entrypoints for tests, canonical generator scripts, agent shell launch, and MCP Docker control

- `scripts/env-common.sh`
  Purpose: shared workspace environment defaults

- `scripts/load-agent-env.sh`
  Purpose: load the environment needed to run `agent-aidf`

- `scripts/load-mcp-env.sh`
  Purpose: load the environment needed to run `mcp-aidf`

- `.env.example`
  Purpose: example values for workspace-level environment configuration

Typical commands:

```bash
make test-all
make generate-default
make agent-shell
make mcp-up
```

If needed, copy `.env.example` to `.env` and fill in local values such as `OPENAI_API_KEY`, `KAIDF_GENERATED_REPO`, and `SECRET_KEY`.

## Current State

- `kobkob-kaidf-generator` is the most complete component today
- `mcp-aidf` is a functional MCP server over generated K-AIDF repositories
- `agent-aidf` now has a terminal-first shell with a real AI controller path and metadata-aware commands

## Suggested Next Steps

- initialize `agent-aidf` and `mcp-aidf` as nested repositories if they are not already
- define a small shared contract for generated document IDs and metadata
- decide whether `mcp-aidf` reads directly from generated repositories or from a separate indexed store
- implement `agent-aidf` against the generated K-AIDF structure rather than duplicating repository semantics
