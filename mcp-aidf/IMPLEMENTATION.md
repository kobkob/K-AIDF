# MCP Server Implementation Notes

## What This Server Does

This is a **Model Context Protocol (MCP) server** that integrates with ChatGPT via OAuth 2.1 authentication. It provides two main tools:

1. **search** - Search AIDF content by query
2. **fetch** - Fetch documents by ID

## Key Implementation Details

### OAuth Flow

- Implements full OAuth 2.1 with PKCE
- Supports dynamic client registration (DCR)
- Handles `resource` parameter binding as required by OpenAI
- Returns proper `token_endpoint_auth_method` in registration

### MCP Protocol

- JSON-RPC 2.0 over HTTP POST: the MCP Streamable HTTP transport in its stateless form (no `Mcp-Session-Id`, no server-to-client SSE stream; `GET /mcp` answers `405`)
- Protocol version negotiation: `2024-11-05`, `2025-03-26` and `2025-06-18` are supported. `initialize` echoes a supported requested revision and answers the newest one otherwise. After the handshake, an unsupported `MCP-Protocol-Version` header is refused with HTTP `400` (`-32600`); a missing header is served
- Notifications (no `id`, for example `notifications/initialized`) and JSON-RPC responses sent by the client are acknowledged with HTTP `202` and an empty body, never with a JSON-RPC reply; `ping` returns an empty result. JSON-RPC batch requests are not accepted
- Proper error handling with `_meta["mcp/www_authenticate"]` for OAuth triggers
- WWW-Authenticate headers on 401 responses

### ChatGPT Connector Requirements

- Must expose `search` and `fetch` tools (OpenAI requirement)
- Tools return content as `[{"type": "text", "text": "..."}]` format
- Handles both form-encoded and JSON token requests
- Includes `issuer` field in OAuth metadata

## Current Status

- ✅ Successfully creates ChatGPT connectors
- ✅ OAuth linking flow works
- ✅ Basic local repository-backed search/fetch implementation
- ✅ Doctrine-aware classification over generic indexed documents
- ✅ Rigid ranking for canonical doctrine files under `docs/00-overview/`
- ✅ Automated tests for repository indexing, doctrine ranking, canonical fetch, and MCP search responses
- ✅ Spec-compliant handshake verified against the official `mcp` Python SDK client (`initialize`, `tools/list`, `tools/call`)
- ✅ Explicit starter-variant ranking for domain-specific best-practice queries
- ✅ Explicit maturity-pack classification and ranking for level and assessment queries
- ✅ Explicit ethical-pack classification and ranking for ethical domain, control, and risk queries
- 🔄 Uses a single configured local K-AIDF repository root as the first content model

## Next Steps for Enhancement

1. Add proper logging and monitoring
2. Support more than one repository root if needed
