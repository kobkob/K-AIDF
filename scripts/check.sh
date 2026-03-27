#!/usr/bin/env bash
set -euo pipefail

bash scripts/bootstrap.sh
PYTHONPATH=src .venv/bin/python -m pytest -q
