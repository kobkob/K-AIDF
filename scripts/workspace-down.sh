#!/usr/bin/env bash
# Stops the local Ollama/OLMo Docker stack. Leaves .env untouched — the
# container being down just means the next chat attempt gets a clear
# "could not reach Ollama" message instead of a real reply.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/env-common.sh"

cd "${KAIDF_WORKSPACE_ROOT}"

docker compose -f docker-compose.local.yml down
