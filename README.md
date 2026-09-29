# Kobkob Installation Guide

## Quick Start
Install Kobkob with a single command:
```bash
curl -sSL https://raw.githubusercontent.com/kobkob/K-AIDF/main/scripts/install.sh | bash
```

## CLI Usage
Default commands route to OLMo:
```bash
./scripts/cli-entrypoint.sh "Your query here"
```

## Document Signing
1. Ensure `manifest.json` exists in the root directory.
2. Start the MCP server:
```bash
./mcp-server/sign --manifest=manifest.json
```

## Polar.sh Integration
After payment, Kobkob auto-installs via Polar.sh webhook.

## Troubleshooting
- Ensure Docker is running.
- Verify `manifest.json` is valid JSON.