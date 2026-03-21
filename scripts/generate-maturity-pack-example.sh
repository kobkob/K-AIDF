#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-out-maturity}"

PYTHONPATH=src python -m kaidf_gen.cli validate specs/kaidf.maturity-model-pack.example.yaml
PYTHONPATH=src python -m kaidf_gen.cli generate specs/kaidf.maturity-model-pack.example.yaml --out "$OUT_DIR" --force

echo "Generated maturity-model pack example in ./${OUT_DIR}"
