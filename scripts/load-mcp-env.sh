#!/usr/bin/env bash
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Use: source scripts/load-mcp-env.sh" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/env-common.sh"

echo "mcp-aidf environment loaded"
echo "KAIDF_WORKSPACE_ROOT=${KAIDF_WORKSPACE_ROOT}"
echo "AIDF_REPO_ROOT=${AIDF_REPO_ROOT}"
echo "AIDF_REPO_HOST_PATH=${AIDF_REPO_HOST_PATH}"
echo "SECRET_KEY=${SECRET_KEY}"
