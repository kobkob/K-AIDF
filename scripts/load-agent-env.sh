#!/usr/bin/env bash
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Use: source scripts/load-agent-env.sh" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/env-common.sh"

echo "agent-aidf environment loaded"
echo "KAIDF_WORKSPACE_ROOT=${KAIDF_WORKSPACE_ROOT}"
echo "AIDF_REPO_ROOT=${AIDF_REPO_ROOT}"
echo "OPENAI_MODEL=${OPENAI_MODEL}"
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY=set"
else
  echo "OPENAI_API_KEY=unset"
fi
