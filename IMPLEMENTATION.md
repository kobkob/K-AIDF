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
- JSON-RPC 2.0 over HTTP POST
- Protocol version negotiation (echoes client's requested version)
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
- 🔄 Uses a single configured local K-AIDF repository root as the first content model

## Next Steps for Enhancement
1. Support sector-specific best-practice variants under a stable canonical doctrine package
2. Make variant ranking explicit for domain-specific queries while preserving canonical doctrine precedence
3. Add proper logging and monitoring
4. Support more than one repository root if needed
