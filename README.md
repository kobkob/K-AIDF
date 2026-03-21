# MCP-AIDF Server

A Model Context Protocol (MCP) server with OAuth 2.1 authentication for ChatGPT integration.

## Overview

This server implements the MCP specification with OAuth authentication, providing search and fetch capabilities for AIDF content. It is designed to work with ChatGPT connectors and follows OpenAI's MCP requirements.

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

### OAuth 2.1 Authentication
- `GET /.well-known/oauth-authorization-server` - OAuth server metadata
- `GET /.well-known/oauth-protected-resource` - Protected resource metadata
- `GET /oauth/authorize` - Authorization endpoint
- `POST /oauth/token` - Token exchange endpoint
- `POST /oauth/register` - Dynamic client registration

## Usage

### ChatGPT Integration
1. In ChatGPT → Settings → Connectors → Create
2. Enter URL: `https://mcp-aidf.kobkob.org/mcp`
3. Follow OAuth linking flow
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
- `SECRET_KEY` - Flask session secret
- `AIDF_REPO_ROOT` - absolute path to the generated K-AIDF repository to index

Docker Compose also expects:
- `AIDF_REPO_HOST_PATH` - host path mounted read-only into the container at `/data/kaidf-repo`

## Compliance

- **MCP Specification**: 2025-03-26
- **OAuth 2.1**: RFC 6749 with PKCE
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
- returns metadata, doctrine category, canonical doctrine status, doctrine priority, optional starter `variant_domain`, detailed ranking components, and a short snippet

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

This keeps the canonical doctrine stable while allowing domain-specific operational guidance to expand later. These starter variants are examples, not fixed doctrine requirements.

Ranking rule:
- canonical `best-practices.md` stays first for generic best-practice queries
- matching starter variants should rank first for clearly domain-specific queries such as `seo` or `research`

## Security

- OAuth 2.1 with PKCE for secure authentication
- Resource parameter binding for token scope
- WWW-Authenticate headers for proper challenge flow
- HTTPS enforced via Cloudflare
