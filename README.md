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
  Purpose: common entrypoints for tests, canonical generator scripts, agent mentor/runtime commands, and MCP Docker control

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
make install-agent
make test-all
make generate-default
make agent-status
make agent-mentor
make agent-mentor ANSWER="We need a transparent localhost review app."
make agent-apps
make agent-app-run APP=mentor-web-app
make agent-shell
make mcp-up
```

If needed, copy `.env.example` to `.env` and fill in local values such as `OPENAI_API_KEY`, `KAIDF_GENERATED_REPO`, and `SECRET_KEY`.

## Current State

The three nested repositories now have clear baseline roles and working local flows:

- `kobkob-kaidf-generator`
  Status: generates the canonical K-AIDF repository structure from declarative specs, including canonical doctrine packages, optional maturity-model and ethical-model packs, and version-2-style metadata/front matter support

- `agent-aidf`
  Status: now operates directly on project-local `.kaidf/` repositories with a persisted mentor workflow, quiz-style continuation, instant app management under `.kaidf/apps/`, and web-app runtime lifecycle commands

- `mcp-aidf`
  Status: is a functional MCP server over generated K-AIDF repositories with doctrine-aware search/fetch behavior and metadata-aware ranking

In practice, the generator defines the structure, the agent uses that structure for creator workflows, and the MCP server exposes selected repository content to external AI clients.

## Current Highlights

- `kobkob-kaidf-generator` now provides the strongest downstream contract surface, including canonical doctrine layout, metadata emission, and packaged doctrine-pack examples
- `agent-aidf` is now beyond a simple shell: it persists mentor state, guides a framework-led workflow across CLI invocations, creates or reuses instant apps, rewrites app scaffolds from workflow intent, and can start/restart/stop active localhost web apps
- `mcp-aidf` now consumes the generated contract model instead of relying on a loose content interpretation only

## Typical Local Flow

One practical end-to-end flow in this workspace is:

1. Use `kobkob-kaidf-generator` to generate or refresh a K-AIDF-compatible repository scaffold.
2. Use `agent-aidf` inside a creator project to initialize `.kaidf/`, run the persisted mentor workflow, and evolve instant apps under `.kaidf/apps/`.
3. Use `mcp-aidf` to expose the generated repository content to MCP clients for doctrine-aware search and fetch.

## Suggested Next Steps

- deepen `agent-aidf` from scaffold-refresh behavior into richer mentor-driven app generation
- decide how much of the creator project outside `.kaidf/` should be inspected during mentor workflows
- continue tightening the generator-to-agent-to-MCP contract around IDs, metadata, and runtime expectations
- define the next additive doctrine pack after the current maturity-model and ethical-model packs
