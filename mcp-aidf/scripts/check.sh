#!/usr/bin/env bash
set -euo pipefail

bash scripts/bootstrap.sh
# Same runner as CI (pytest collects both unittest- and pytest-style tests).
# KAIDF_REQUIRE_ENGINE makes a missing agent-aidf fail instead of silently skipping.
KAIDF_REQUIRE_ENGINE=1 .venv/bin/python -m pytest -q
.venv/bin/python -m py_compile app.py
