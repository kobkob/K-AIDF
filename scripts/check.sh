#!/usr/bin/env bash
set -euo pipefail

./scripts/bootstrap.sh
PYTHONPATH=src .venv/bin/python -m pytest -q
