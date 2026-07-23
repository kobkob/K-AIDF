# K-AIDF

K-AIDF (Knowledge and Artificial Intelligence Development Framework) is a governance framework for the ethical, responsible, and human-centered use of AI, paired with the tooling that implements it. This repository — **kaidf core** — is the single source tree for that tooling. See `MANIFESTO.md` for the framework's founding principles.

K-AIDF uses itself as its own creation tool: the generator scaffolds a K-AIDF repository, the agent (`kob`) guides a creator through it, and the MCP server exposes it to AI clients.
### The Terminal UI
<img width="1470" height="768" alt="TUI_0 4 2" src="https://github.com/user-attachments/assets/196cd777-fd48-48b8-ac28-4dadb7d011b8" />

### The Web UI
<img width="1633" height="901" alt="webUI_0 4 2" src="https://github.com/user-attachments/assets/1677073a-d0ed-4299-8f82-b733780c3b96" />

### Simplified Architecture Diagram
<img width="1701" height="924" alt="achitecture_0 4 2" src="https://github.com/user-attachments/assets/598eb2fa-967a-4836-bae5-405ec44e9681" />

## Repository Layout

This used to be a workspace of three separate nested Git repositories. They have since been merged into this single repository (with `git subtree`, preserving history) and their standalone GitHub repos archived. All further work happens here, in one commit/PR history.

```text
K-AIDF/
├── agent-aidf/                 # the kob CLI and mentor agent
├── kobkob-kaidf-generator/      # scaffold generator (kaidf-gen)
├── mcp-aidf/                    # MCP server for AI-client integration
├── Makefile                     # root automation for all three
├── scripts/                     # shared env-loading scripts
├── docker-compose.local.yml     # local Ollama + MCP stack
├── MANIFESTO.md
└── README.md
```

Beyond these three components, you can add personal extensions or full projects as additional subdirectories, or fork this repo as a starting point for your own application — improvements to the core can be upstreamed back as child-project contributions.

## Components

| Component | Role | Status |
|---|---|---|
| `kobkob-kaidf-generator` | Generates a K-AIDF repository scaffold from a declarative YAML spec — canonical doctrine, optional maturity-model and ethical-model packs, v2 front matter metadata | Working; `kaidf-gen validate`/`generate` CLI, own test suite |
| `agent-aidf` | Hosts the `kob` CLI and mentor agent that operate on a project-local `.kaidf/` repository | Working; CLI is mid-migration from a legacy argparse interface to the new `kob` click CLI (see below) |
| `mcp-aidf` | Exposes generated K-AIDF content over MCP (`search`/`fetch`) with OAuth 2.1, for ChatGPT and other MCP clients | Working; Flask server, Docker deployment, doctrine-aware ranking |

Recommended mental model — a pipeline:

1. `kobkob-kaidf-generator` defines and generates the canonical K-AIDF file/folder structure.
2. `agent-aidf` (`kob`) consumes that structure to guide a creator's workflow.
3. `mcp-aidf` publishes selected content and search/fetch to external AI clients.

## The `kob` CLI

`kob` (`agent_aidf.cli.main`) is the unified entrypoint for `agent-aidf`, replacing the old standalone `agent-aidf` command. It is mid-migration: some commands are fully implemented, others are placeholders or still only reachable through the legacy CLI.

| Command | Status |
|---|---|
| `kob init [--force]` | real — generates `.kaidf/` via the generator |
| `kob status` | real — project/runtime status report |
| `kob mentor [answer] [--status] [--reset]` | real — persisted, quiz-style mentor workflow |
| `kob shell` | real — interactive terminal shell |
| `kob compile [spec] --out <dir> [--force]` / `kob gen ...` | real — runs the generator's `generate` engine directly |
| `kob ui [--port]` / `kob serve [--port]` | placeholder — will launch the local mentor web daemon |

Commands not yet ported to `kob` still run through the legacy CLI:

```bash
python -m agent_aidf.legacy_cli {context,packs,contracts,contract-create,contract-open,apps,app-create,app-open,app-run,app-runtime,app-stop,docs,find,open,chat}
```

Context resolution order for both CLIs: `--repo` override → `.kaidf/` in `--project`/cwd → `AIDF_REPO_ROOT` → the project root as a fallback.

## Local Development

```bash
make install-generator     # bootstrap the generator venv
make install-agent         # bootstrap the agent-aidf venv (installs kob)
make install-mcp           # bootstrap the mcp-aidf venv
make test-all              # run all three test suites
```

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` (used by `kob mentor`/`kob shell`'s AI controller; falls back to a stub if unset), `KAIDF_GENERATED_REPO`, and `SECRET_KEY` (mcp-aidf).

Common workflow targets (all resolve/generate the default repository automatically if missing):

```bash
make generate-default              # kob gen the default spec into kobkob-kaidf-generator/out
make generate-maturity              # kob gen the maturity-model pack example
make generate-ethical                # kob gen the ethical-model pack example
make agent-status                   # kob status
make agent-mentor ANSWER="..."       # kob mentor
make agent-mentor-status             # kob mentor --status
make agent-shell                     # kob shell
make agent-ui                        # kob ui (placeholder)
make agent-packs                     # legacy CLI: doctrine packs
make agent-apps                      # legacy CLI: list instant apps
make agent-app-run APP=<id> [PORT=...]  # legacy CLI: start a web instant app
make mcp-up / mcp-down / mcp-logs    # Docker Compose control for mcp-aidf
```

Run `make help` for the full, current target list.

## Local Inference Stack

`docker-compose.local.yml` stands up a local-inference alternative to the OpenAI-backed controller: an Ollama container serving an OLMo model, plus the `mcp-aidf` server pointed at it (`workspace-up`/`workspace-down`). On the agent side, `agent_aidf.llm_provider.LLMProvider` defines the provider interface and `agent_aidf.providers.olmo_local.OLMoLocalProvider` is an in-progress driver for it — **not yet wired into the mentor controller**, which still runs on the OpenAI Responses API (with a stub fallback when no API key is set).

## Integration Contract

The authoritative integration contract lives in `kobkob-kaidf-generator/docs/contract.md` (draft v1, v2 front matter guidance). Each component owns a distinct slice:

| Concern | Owner | Downstream rule |
|---|---|---|
| Repository layout, paths, templates | `kobkob-kaidf-generator` | Specs + template library are the only source of structure |
| Document classes, stable IDs, front matter | Contract in generator docs | Generator emits; agent and MCP consume |
| Doctrine categories, pack metadata | Contract (derived layer) | Agent and MCP infer/rank; generator emits pack fields in specs |
| Mentor workflow, instant apps, contracts | `agent-aidf` | Runtime state under `.kaidf/` only — not part of the repo contract |
| MCP search/fetch, OAuth, visibility policy | `mcp-aidf` | Indexes generated repos via `AIDF_REPO_ROOT`; no separate content model |

Verified alignment (agent-aidf + mcp-aidf): same indexable surface (`README.md`, `MANIFESTO.md`, `docs/**/*.md`, `docs/**/*.csv`), same canonical doctrine paths under `docs/00-overview/`, same v2 front matter fields (`id`, `title`, `document_class`, `phase`, `visibility`, `status`) and pack fields (`pack`, `maturity_level`, `assessment_type`, `ethical_domain`, `control_type`, `risk_type`), same fetch-ID rule (front matter `id` preferred, path as fallback).

Known gaps: indexing logic is duplicated across `agent-aidf/src/agent_aidf/repo.py` and `mcp-aidf/app.py` (no shared library yet); MCP does not yet enforce v2 visibility rules (exclude `private` by default); mentor/apps/contracts workflow state is intentionally outside the generated-repo contract.

## Boundaries

- `kobkob-kaidf-generator` owns spec parsing, schema validation, template packaging, and scaffold generation.
- `agent-aidf` owns orchestration UX, prompt flows, local project interaction, and user-facing workflows.
- `mcp-aidf` owns MCP protocol handling, OAuth, indexing, search, fetch, and connector-facing integration.

Avoid duplicating K-AIDF document semantics across components — the generator is the source of truth for structure; the agent and MCP server consume generated repositories.

## Next Steps

- implement `kob ui`/`kob serve` for real (launch the local mentor web daemon)
- wire `agent_aidf.providers.olmo_local.OLMoLocalProvider` into the mentor controller as a local-inference alternative to OpenAI
- finish migrating the remaining legacy CLI commands (`context`, `packs`, `apps`, `contracts`, `app-*`, `docs`, `find`, `open`, `chat`) onto `kob`
- close the known integration-contract gaps above (shared indexing library, MCP visibility enforcement)
- define the next additive doctrine pack after the current maturity-model and ethical-model packs
