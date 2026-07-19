# K-AIDF Workspace

K-AIDF uses itself as the creation tool.
This directory is a single repository that groups three related K-AIDF projects as tracked subdirectories, forming the basic minimum environment for a working framework. We name it "**kaidf core**".

## Purpose

The intent is to keep the K-AIDF ecosystem split by responsibility:

- `kobkob-kaidf-generator`: generates K-AIDF repository scaffolds from declarative YAML specs
- `mcp-aidf`: exposes K-AIDF content through an MCP server for ChatGPT and other MCP clients
- `agent-aidf`: hosts the interactive agent surfaces that operate on top of a K-AIDF repository structure

This root directory is both the coordination layer and the single source tree. Each component was previously its own repository; their histories have been merged in as subdirectories via `git subtree`, and their standalone GitHub repositories are archived. All further changes to any component are made and versioned here.

Beyond these three basic repositories extending the framework, we can include personal extensions or main projects in this same directory, creating a child project. You can have your fork of this repo to create your own application from this point. Following best-practices the improvements you make to this core could be updated to child projects.

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

## Integration Contract

The authoritative integration contract lives in `kobkob-kaidf-generator/docs/contract.md` (draft v1, with v2 front matter guidance). Each component owns a distinct slice:

| Concern | Owner | Downstream rule |
|---------|-------|-----------------|
| Repository layout, paths, templates | `kobkob-kaidf-generator` | Specs + template library are the only source of structure |
| Document classes, stable IDs, front matter | Contract in generator docs | Generator emits; agent and MCP consume |
| Doctrine categories, pack metadata | Contract (derived layer) | Agent and MCP infer/rank; generator emits pack fields in specs |
| Mentor workflow, instant apps, contracts | `agent-aidf` | Runtime state under `.kaidf/` only — not part of the repo contract |
| MCP search/fetch, OAuth, visibility policy | `mcp-aidf` | Indexes generated repos via `AIDF_REPO_ROOT`; no separate content model |

**Verified alignment (agent-aidf + mcp-aidf):**

- Same indexable surface: `README.md`, `MANIFESTO.md`, `docs/**/*.md`, `docs/**/*.csv`
- Same canonical doctrine paths under `docs/00-overview/`
- Same v2 front matter fields: `id`, `title`, `document_class`, `phase`, `visibility`, `status`
- Same additive pack fields: `pack`, `maturity_level`, `assessment_type`, `ethical_domain`, `control_type`, `risk_type`
- Fetch ID: front matter `id` preferred, repository-relative path as fallback

**Known gaps to address in future contract work:**

- Indexing logic is duplicated across `agent-aidf/src/agent_aidf/repo.py` and `mcp-aidf/app.py` (no shared library yet)
- MCP does not yet enforce v2 visibility rules (exclude `private` documents by default)
- Cross-document workflow state (mentor, apps, contracts) is intentionally outside the generated-repo contract

## Workspace Conventions

- each subdirectory is a tracked path within this single repository, not a separate Git repository
- this root directory is the primary source tree for all three components, as well as workspace automation and documentation
- cross-project changes are coordinated directly in this repository, in the same commit or PR when they touch shared contracts

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

The `agent-*` Make targets now assume the default generated K-AIDF repository should exist at the configured workspace path. If it is missing, the workspace will generate it automatically before running the agent command.

## Current State

The three components now have clear baseline roles and working local flows:

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

- install the agent-aidf cli for global system use and as a web service with UIX
- deepen `agent-aidf` from scaffold-refresh behavior into richer mentor-driven app generation
- implement a rating system to define and evaluate the project adoption of the kaidf contracts
- decide how much of the creator project outside `.kaidf/` should be inspected during mentor workflows
- continue tightening the generator-to-agent-to-MCP contract around IDs, metadata, and runtime expectations
- define the next additive doctrine pack after the current maturity-model and ethical-model packs
