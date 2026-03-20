#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m kaidf_gen.cli validate specs/kaidf.default.yaml

