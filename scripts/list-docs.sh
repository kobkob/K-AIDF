#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=src python -m agent_aidf.cli docs "$@"
