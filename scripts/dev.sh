#!/usr/bin/env bash
set -euo pipefail

if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -m pytest --version >/dev/null 2>&1; then
  rm -rf .venv
  python -m venv --system-site-packages .venv
fi

source .venv/bin/activate
PYTHONPATH=src .venv/bin/python -m pytest -q

if [[ -n "${AIDF_REPO_ROOT:-}" ]]; then
  PYTHONPATH=src .venv/bin/python -m agent_aidf.cli --repo "$AIDF_REPO_ROOT" packs
fi
