#!/usr/bin/env bash
set -euo pipefail

bash scripts/bootstrap.sh
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m kaidf_gen.cli validate specs/kaidf.default.yaml
PYTHONPATH=src .venv/bin/python -m kaidf_gen.cli generate specs/kaidf.default.yaml --out out --force
echo "Generated output in ./out"
