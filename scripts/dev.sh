#!/usr/bin/env bash
set -euo pipefail

./scripts/bootstrap.sh
PYTHONPATH=src .venv/bin/python -m pytest -q

if [[ -n "${AIDF_REPO_ROOT:-}" ]]; then
  PYTHONPATH=src .venv/bin/python -m agent_aidf.cli --repo "$AIDF_REPO_ROOT" packs
fi
