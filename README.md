# MCP-AIDF Server

A Model Context Protocol (MCP) server with OAuth 2.1 authentication for ChatGPT integration.

## Overview

This server implements the MCP specification with OAuth authentication, providing search and fetch capabilities for AIDF content. It's designed to work with ChatGPT connectors and follows OpenAI's MCP requirements.

## Architecture

- **Flask** web server running on port 7777
- **Docker** containerized deployment
- **Nginx** reverse proxy (port 80 → 7777)
- **Cloudflare** SSL termination (443 → 80)

## Endpoints

### MCP Protocol
- `POST /mcp` - Main MCP JSON-RPC endpoint
  - Methods: `initialize`, `tools/list`, `tools/call`
  - Tools: `search`, `fetch`

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

## Security

- OAuth 2.1 with PKCE for secure authentication
- Resource parameter binding for token scope
- WWW-Authenticate headers for proper challenge flow
- HTTPS enforced via Cloudflare
