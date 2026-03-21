#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-out-ethical}"

PYTHONPATH=src python -m kaidf_gen.cli validate specs/kaidf.ethical-model-pack.example.yaml
PYTHONPATH=src python -m kaidf_gen.cli generate specs/kaidf.ethical-model-pack.example.yaml --out "$OUT_DIR" --force

echo "Generated ethical-model pack example in ./${OUT_DIR}"
