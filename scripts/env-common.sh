#!/usr/bin/env bash
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "This script is meant to be sourced, not executed directly." >&2
  exit 1
fi

KAIDF_WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export KAIDF_WORKSPACE_ROOT
export KAIDF_GENERATOR_DIR="${KAIDF_WORKSPACE_ROOT}/kobkob-kaidf-generator"
export KAIDF_AGENT_DIR="${KAIDF_WORKSPACE_ROOT}/agent-aidf"
export KAIDF_MCP_DIR="${KAIDF_WORKSPACE_ROOT}/mcp-aidf"

if [[ -f "${KAIDF_WORKSPACE_ROOT}/.env" ]]; then
  # shellcheck disable=SC1091
  source "${KAIDF_WORKSPACE_ROOT}/.env"
fi

if [[ -z "${KAIDF_GENERATED_REPO:-}" ]]; then
  KAIDF_GENERATED_REPO="${KAIDF_GENERATOR_DIR}/out/kobkob-kaidf"
fi
export KAIDF_GENERATED_REPO
export AIDF_REPO_ROOT="${AIDF_REPO_ROOT:-${KAIDF_GENERATED_REPO}}"
export AIDF_REPO_HOST_PATH="${AIDF_REPO_HOST_PATH:-${AIDF_REPO_ROOT}}"
export OPENAI_MODEL="${OPENAI_MODEL:-gpt-5}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
export SECRET_KEY="${SECRET_KEY:-change-me}"
