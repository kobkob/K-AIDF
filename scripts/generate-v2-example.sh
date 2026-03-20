#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-out-v2}"

PYTHONPATH=src python -m kaidf_gen.cli validate specs/kaidf.metadata-v2.example.yaml
PYTHONPATH=src python -m kaidf_gen.cli generate specs/kaidf.metadata-v2.example.yaml --out "$OUT_DIR" --force

echo "Generated version 2 metadata example in ./${OUT_DIR}"

