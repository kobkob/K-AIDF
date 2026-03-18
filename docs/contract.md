# K-AIDF Repository Contract

## Purpose

This document defines the generated repository contract that downstream tools must rely on.

It is the coordination point between:

- `kobkob-kaidf-generator`, which creates the repository structure
- `agent-aidf`, which operates on the generated repository
- `mcp-aidf`, which indexes and fetches repository content

The goal is to make repository shape and document semantics explicit instead of implicit.

## Contract Version

- `contract_version: 1`
- status: draft, but intended to be stable enough for early integration work

## Scope

This contract covers:

- repository layout
- document classes
- path and naming conventions
- stable document identity rules
- indexing rules for MCP consumers
- editability rules for agent consumers

This contract does not yet define:

- cross-document workflow state machines
- approval/sign-off schemas
- rich front matter requirements

## Repository Root

A generated K-AIDF repository is expected to contain:

- `README.md`
- `LICENSE`
- `CODEOWNERS`
- optional `SECURITY.md`
- `docs/`

The generator may add more files over time, but consumers should treat the root files above as the baseline contract.

## Required Directories

At minimum, generated repositories should support:

- `docs/00-overview/`
- `docs/01-intent-constraints/`

Additional numbered `docs/NN-*` phases are allowed and expected as the methodology expands.

## Required Files

Current baseline examples include:

- `docs/00-overview/kaidf.md`
- `docs/00-overview/glossary.md`
- `docs/00-overview/principles.md`
- `docs/00-overview/decision-rights.md`
- `docs/01-intent-constraints/README.md`
- `docs/01-intent-constraints/exit-criteria.md`
- `docs/01-intent-constraints/templates/ICB.md`
- `docs/01-intent-constraints/templates/constraint-matrix.csv`
- `docs/01-intent-constraints/prompts/framing.prompt.md`

Consumers must tolerate additional files in the same directories.

## Path And Naming Rules

- repository-relative paths are the canonical location reference
- phase directories use `docs/NN-name/` with a two-digit numeric prefix
- prompts belong under `prompts/`
- reusable fill-in assets belong under `templates/`
- overview and methodology reference material belongs directly under the relevant phase directory

## Document Classes

The contract distinguishes these classes:

- `core-doc`
  Description: methodology or project documents intended for direct reading
  Examples: `README.md`, `kaidf.md`, `principles.md`

- `template-doc`
  Description: reusable templates meant to be copied or filled in
  Examples: `templates/ICB.md`, `templates/constraint-matrix.csv`

- `prompt-doc`
  Description: prompts intended for agent or human-guided execution
  Examples: `prompts/framing.prompt.md`

- `governance-doc`
  Description: repository governance artifacts
  Examples: `LICENSE`, `CODEOWNERS`, `SECURITY.md`

## Stable ID Rules

Until explicit front matter IDs are introduced, the stable ID for a document is its repository-relative path.

Examples:

- `README.md`
- `docs/00-overview/kaidf.md`
- `docs/01-intent-constraints/templates/ICB.md`

Implications:

- `mcp-aidf` should use repository-relative paths as fetch identifiers
- `agent-aidf` should refer to documents by repository-relative path in orchestration logic
- renaming paths is a contract-affecting change

## Metadata Rules

There is no required front matter in contract version 1.

Consumers must derive meaning from:

- repository-relative path
- file extension
- directory role

Contract version 2 should introduce explicit front matter for indexable markdown documents.

Planned version 2 metadata fields:

- `id`
- `title`
- `document_class`
- `phase`
- `visibility`
- `status`

Version 1 consumers must not assume front matter exists. Version 2 consumers should prefer explicit metadata over path inference where available.

## Indexing Rules For MCP

`mcp-aidf` should treat these as indexable by default:

- `README.md`
- `docs/**/*.md`
- `docs/**/*.csv`

In contract version 1, prompt documents are exposed by default. `mcp-aidf` should therefore treat prompt files as normal indexable repository content unless a deployment-specific policy overrides that default.

`mcp-aidf` should not assume every file is public or user-facing. In version 1:

- `templates/` content is indexable
- `prompts/` content is indexable
- governance files are indexable if the deployment chooses to expose them

For contract version 2, visibility should move from deployment-only policy into explicit document metadata where appropriate.

If a deployment needs stricter visibility rules, that policy should be layered on top of this contract rather than inferred from missing metadata.

## Editing Rules For Agents

`agent-aidf` should treat:

- `templates/` files as canonical reusable assets, not case-specific output artifacts
- `prompts/` files as orchestrator inputs that should be edited deliberately
- phase documents and root documents as normal editable content

Agents should avoid:

- renaming contract paths without an explicit migration decision
- inventing hidden metadata conventions not defined by the contract
- treating generated template library files as if they were runtime state stores

## Machine-Readable Example

See `specs/contract.example.yaml` for a compact machine-readable example of this contract.

## Compatibility Rules

- adding new files is usually backward-compatible
- adding new optional directories is backward-compatible
- changing stable IDs or required paths is contract-breaking
- making optional metadata mandatory is contract-breaking
- moving from implicit visibility to explicit visibility metadata is a contract version change

## Immediate Integration Guidance

For early integration work:

- `kobkob-kaidf-generator` owns the canonical path structure
- `agent-aidf` should operate on repository-relative paths and document classes
- `mcp-aidf` should use repository-relative paths as fetch IDs and index `docs/` plus selected root files, including prompt documents by default
