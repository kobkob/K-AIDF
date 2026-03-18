#!/usr/bin/env bash
set -euo pipefail

if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -m pytest --version >/dev/null 2>&1; then
  rm -rf .venv
  python -m venv --system-site-packages .venv
fi

source .venv/bin/activate
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m kaidf_gen.cli validate specs/kaidf.default.yaml
PYTHONPATH=src .venv/bin/python -m kaidf_gen.cli generate specs/kaidf.default.yaml --out out --force
echo "Generated output in ./out"
