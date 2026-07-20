#!/usr/bin/env bash
set -euo pipefail

bash scripts/bootstrap.sh
PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli shell "$@"
