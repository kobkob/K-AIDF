# MCP-AIDF Server

A Model Context Protocol (MCP) server with bearer-token authentication (`MCP_BEARER_TOKEN`).

## Overview

This server implements the MCP specification with bearer-token authentication, providing search and fetch capabilities for AIDF content. Every request to `/mcp` and `/` must carry `Authorization: Bearer <MCP_BEARER_TOKEN>`.

The current implementation uses the simplest useful content model:

- one configured local K-AIDF repository root
- contract-based file selection
- path IDs by default
- optional front matter metadata when present
- doctrine-aware classification layered on top of generic document classes

## Architecture

- **Flask** web server running on port 7777
- **Single local repository root** configured by `AIDF_REPO_ROOT`
- **Docker** containerized deployment
- **Nginx** reverse proxy (port 80 → 7777)
- **Cloudflare** SSL termination (443 → 80)

## Endpoints

### MCP Protocol

- `POST /mcp` - Main MCP JSON-RPC endpoint
  - Methods: `initialize`, `tools/list`, `tools/call`
  - Tools: `search`, `fetch`

### Indexed Content Model

- Root file: `README.md`
- Documents under `docs/**/*.md`
- CSV templates under `docs/**/*.csv`
- Prompt documents are exposed by default when they live under `docs/**/prompts/`

The server uses repository-relative paths as fetch IDs by default and prefers metadata IDs when front matter exists.

Doctrine-aware categories currently inferred by the server:

- `manifesto`
- `principles`
- `best-practices`
- `governance`
- `maturity`
- `implementation`
- `training`
- `general`

Canonical doctrine files under `docs/00-overview/` receive rigid ranking priority for doctrine-oriented queries.

### Bearer Token Authentication

- `MCP_BEARER_TOKEN` is the only accepted credential. The comparison is constant-time.
- A missing or wrong token returns HTTP 401 with a `WWW-Authenticate` challenge. A wrong token adds `error="invalid_token"` (RFC 6750).
- `GET /.well-known/oauth-protected-resource` - Protected resource metadata (RFC 9728). It names this server as the resource and does not advertise an authorization server, because none is implemented.

The earlier OAuth 2.1 endpoints (`/oauth/authorize`, `/oauth/token`, `/oauth/register` and `/.well-known/oauth-authorization-server`) were stubs that issued a fixed token and redirected to any URL. They have been removed.

## Usage

### ChatGPT Integration

1. In ChatGPT → Settings → Connectors → Create
2. Enter URL: `https://mcp-aidf.kobkob.org/mcp`
3. Configure the connector with the bearer token from `MCP_BEARER_TOKEN`, if its settings allow a static token. This server no longer offers an OAuth linking flow.
4. Use search and fetch tools in conversations

### API Example

```bash
# Initialize MCP session
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' \
  https://mcp-aidf.kobkob.org/mcp

# List available tools
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  https://mcp-aidf.kobkob.org/mcp
```

## Deployment

```bash
# Provide a generated K-AIDF repository on the host first
export AIDF_REPO_HOST_PATH=/absolute/path/to/kobkob-kaidf

# Build and run
docker compose up --build -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

## Configuration

Environment variables in `docker-compose.yml`:

- `SECRET_KEY` - Flask session secret. Required by `docker-compose.yml` (no default; `docker compose` fails if it is unset or empty). Set it in `.env` (see `.env.example`).
- `MCP_BEARER_TOKEN` - the bearer token every client must present. Required by `docker-compose.yml` (no default). Use a long random value, for example `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Outside Docker, if it is unset, the server starts with a random token for that process only and logs it at startup; that token changes on every restart and is not shared between gunicorn workers.
- `AIDF_REPO_ROOT` - absolute path to the generated K-AIDF repository to index

Docker Compose also expects:

- `AIDF_REPO_HOST_PATH` - host path mounted read-only into the container at `/data/kaidf-repo`

## Compliance

- **MCP Specification**: 2025-03-26
- **Authentication**: static bearer token (RFC 6750) and protected resource metadata (RFC 9728). No OAuth 2.1 authorization server
- **JSON-RPC 2.0**: Request/response protocol
- **OpenAI Requirements**: Search/fetch tools, proper error handling

## Files

- `app.py` - Main Flask application
- `Dockerfile` - Container configuration  
- `docker-compose.yml` - Service orchestration
- `requirements.txt` - Python dependencies
- `README.md` - This documentation

## Behavior

`search`:

- performs a simple local index scan over the configured repository root
- searches path, title, ID, phase, class, and document body
- returns metadata, doctrine category, canonical doctrine status, doctrine priority, optional starter `variant_domain`, optional pack fields (`pack`, `maturity_level`, `assessment_type`, `ethical_domain`, `control_type`, `risk_type`), detailed ranking components, and a short snippet

`fetch`:

- resolves a document by metadata `id` when front matter exists
- falls back to repository-relative path lookup
- returns metadata, doctrine classification, and full document content

## Canonical Doctrine And Variants

The canonical doctrine package is expected under `docs/00-overview/`.

Canonical files:

- `manifesto.md`
- `principles.md`
- `best-practices.md`
- `governance.md`
- `maturity.md`
- `implementation.md`

Recommended starter variant model:

- keep `docs/00-overview/best-practices.md` as the generic canonical file
- add sector-specific variants under `docs/00-overview/best-practices/`
- use one file per domain, for example:
  - `docs/00-overview/best-practices/seo.md`
  - `docs/00-overview/best-practices/content.md`
  - `docs/00-overview/best-practices/research.md`

This keeps the canonical doctrine stable while allowing domain-specific operational guidance to expand later. These starter variants are examples, not fixed doctrine requirements, and they remain part of the default generated baseline while future doctrine packs are added separately.

Ranking rule:

- canonical `best-practices.md` stays first for generic best-practice queries
- matching starter variants should rank first for clearly domain-specific queries such as `seo` or `research`
- starter variant identity is path-derived from known repository locations, not a separate authored metadata field

## Maturity-Model Pack

The first-class optional maturity-model pack lives under `docs/10-maturity-model/`.

When front matter is present, the server exposes:

- `pack`
- `maturity_level`
- `assessment_type`

Ranking rule:

- canonical `docs/00-overview/maturity.md` stays first for generic `maturity` queries
- level queries such as `managed` or `experimental` should rank the matching level document first
- assessment queries such as `checklist` should rank the matching assessment document first

## Ethical-Model Pack

The first-class optional ethical-model pack lives under `docs/20-ethical-model/`.

When front matter is present, the server exposes:

- `pack`
- `ethical_domain`
- `control_type`
- `risk_type`

Ranking rule:

- generic `ethical-model` queries should rank the pack `README.md` first
- domain queries such as `transparency` should rank the matching principle or control document first
- control-oriented queries such as `privacy` should rank the matching control document first
- risk queries such as `bias-and-harm` should rank the matching risk document first

## Security

- Bearer token checked with a constant-time comparison on `/mcp` and `/`
- WWW-Authenticate headers for proper challenge flow (RFC 6750)
- HTTPS enforced via Cloudflare
