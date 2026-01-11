#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -e .
kaidf-gen validate specs/kaidf.default.yaml
kaidf-gen generate specs/kaidf.default.yaml --out out --force
echo "Generated output in ./out"
