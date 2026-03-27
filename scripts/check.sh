#!/usr/bin/env bash
set -euo pipefail

./scripts/bootstrap.sh
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m kaidf_gen.cli validate specs/kaidf.default.yaml
