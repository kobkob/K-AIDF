#!/usr/bin/env bash
# Installs and starts the local Ollama/OLMo Docker stack (docker-compose.local.yml),
# picks a model tag sized to the host's hardware, pulls it, and persists the
# resulting config into the workspace .env so `kob` picks up local inference.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/env-common.sh"

cd "${KAIDF_WORKSPACE_ROOT}"

COMPOSE_FILES=(-f docker-compose.local.yml)
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "Detected an NVIDIA GPU — enabling Docker GPU passthrough (requires the NVIDIA Container Toolkit on this host)."
  COMPOSE_FILES+=(-f docker-compose.gpu.yml)
fi

echo "Picking an Ollama model for this machine..."
MODEL="$(bash scripts/detect-ollama-model.sh)"
echo "Selected model: ${MODEL}"

echo "Starting local infrastructure (Community + OLMo)..."
docker compose "${COMPOSE_FILES[@]}" up -d

echo "Waiting for the Ollama server to become ready..."
READY=0
for _ in $(seq 1 30); do
  if docker exec aidf-ollama ollama list >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done
if [[ "${READY}" -ne 1 ]]; then
  echo "Ollama did not become ready in time. Check 'make workspace-logs' for details." >&2
  exit 1
fi

echo "Pulling ${MODEL} (this can take a while on first run)..."
docker exec aidf-ollama ollama pull "${MODEL}"

ENV_FILE="${KAIDF_WORKSPACE_ROOT}/.env"
touch "${ENV_FILE}"

set_env_var() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
  fi
}

set_env_var "KAIDF_LOCAL_INFERENCE" "true"
set_env_var "OLLAMA_HOST" "http://localhost:11434"
set_env_var "AIDF_MODEL" "${MODEL}"

echo ""
echo "Local OLMo/Ollama stack is ready."
echo "  Model:        ${MODEL}"
echo "  Ollama host:  http://localhost:11434"
echo "  Config saved: ${ENV_FILE}"
echo ""
echo "Run 'make agent-tui' (or 'kob') to start chatting with the local model."
