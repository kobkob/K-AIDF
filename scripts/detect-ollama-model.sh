#!/usr/bin/env bash
# Picks an Ollama model tag sized to the host's RAM/disk/GPU so a creator
# doesn't get handed a model too heavy to run at a usable speed.
#
# Real tags on Ollama's library (verified against registry.ollama.ai): the
# "olmo" v1 family isn't published there at all — only "olmo2", starting at
# 7B. There's no smaller OLMo to fall back to, so a genuinely underpowered
# machine gets a clear error instead of a silently-broken pull.
#
# Prints exactly one line to stdout: the chosen model tag.
# Everything else (reasoning, detected values) goes to stderr, so callers can
# safely do MODEL="$(scripts/detect-ollama-model.sh)".
set -euo pipefail

STANDARD_MODEL="olmo2:7b-1124-instruct-q4_K_M"
HEAVY_MODEL="olmo2:13b-1124-instruct-q4_K_M"

STANDARD_RAM_MB=8000
STANDARD_GPU_VRAM_MB=4000
STANDARD_DISK_MB=5000

HEAVY_RAM_MB=32000
HEAVY_GPU_VRAM_MB=12000
HEAVY_DISK_MB=10000

log() { echo "$@" >&2; }

if [[ -n "${AIDF_OLLAMA_MODEL:-}" ]]; then
  log "AIDF_OLLAMA_MODEL is set: using '${AIDF_OLLAMA_MODEL}' (skipping hardware detection)."
  echo "${AIDF_OLLAMA_MODEL}"
  exit 0
fi

detect_ram_mb() {
  if [[ -r /proc/meminfo ]]; then
    awk '/^MemTotal:/ { printf "%d", $2 / 1024 }' /proc/meminfo
  elif command -v sysctl >/dev/null 2>&1; then
    local bytes
    bytes="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
    echo $(( bytes / 1024 / 1024 ))
  else
    echo 0
  fi
}

detect_disk_free_mb() {
  df -Pm / 2>/dev/null | awk 'NR==2 { print $4 }' || echo 0
}

detect_gpu_vram_mb() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null \
      | sort -rn | head -n1 || echo 0
  else
    echo 0
  fi
}

RAM_MB="$(detect_ram_mb)"
DISK_FREE_MB="$(detect_disk_free_mb)"
GPU_VRAM_MB="$(detect_gpu_vram_mb)"

RAM_MB="${RAM_MB:-0}"
DISK_FREE_MB="${DISK_FREE_MB:-0}"
GPU_VRAM_MB="${GPU_VRAM_MB:-0}"

log "Detected hardware: RAM=${RAM_MB}MB, free disk (/)=${DISK_FREE_MB}MB, GPU VRAM=${GPU_VRAM_MB}MB"
log "(Free disk is measured on / and is approximate — Docker Desktop/WSL2 may store its virtual disk elsewhere.)"

qualifies_for_heavy=0
if [[ "${RAM_MB}" -ge "${HEAVY_RAM_MB}" || "${GPU_VRAM_MB}" -ge "${HEAVY_GPU_VRAM_MB}" ]]; then
  qualifies_for_heavy=1
fi

qualifies_for_standard=0
if [[ "${RAM_MB}" -ge "${STANDARD_RAM_MB}" || "${GPU_VRAM_MB}" -ge "${STANDARD_GPU_VRAM_MB}" ]]; then
  qualifies_for_standard=1
fi

if [[ "${qualifies_for_heavy}" -eq 1 && "${DISK_FREE_MB}" -ge "${HEAVY_DISK_MB}" ]]; then
  log "RAM/GPU meet the >=${HEAVY_RAM_MB}MB RAM or >=${HEAVY_GPU_VRAM_MB}MB VRAM threshold and there is enough free disk: choosing the larger ${HEAVY_MODEL}."
  echo "${HEAVY_MODEL}"
  exit 0
fi

if [[ "${qualifies_for_heavy}" -eq 1 ]]; then
  log "RAM/GPU qualify for ${HEAVY_MODEL}, but free disk is below ${HEAVY_DISK_MB}MB: falling back to the smaller ${STANDARD_MODEL}."
fi

if [[ "${qualifies_for_standard}" -eq 1 && "${DISK_FREE_MB}" -ge "${STANDARD_DISK_MB}" ]]; then
  log "Choosing the standard ${STANDARD_MODEL} (needs roughly >=${STANDARD_RAM_MB}MB RAM or a >=${STANDARD_GPU_VRAM_MB}MB-VRAM GPU, and ${STANDARD_DISK_MB}MB free disk)."
  echo "${STANDARD_MODEL}"
  exit 0
fi

log "ERROR: this machine doesn't meet the minimum for any published OLMo model."
log "OLMo's smallest model on Ollama's library is 7B (~4.5GB) and needs roughly ${STANDARD_RAM_MB}MB RAM (or a ${STANDARD_GPU_VRAM_MB}MB+ VRAM GPU) and ${STANDARD_DISK_MB}MB free disk to run at a usable speed."
log "Detected: RAM=${RAM_MB}MB, GPU VRAM=${GPU_VRAM_MB}MB, free disk=${DISK_FREE_MB}MB."
log "Free up resources and re-run, set AIDF_OLLAMA_MODEL to an existing local tag to skip pulling, or use a cloud provider instead (set OPENAI_API_KEY)."
exit 1
