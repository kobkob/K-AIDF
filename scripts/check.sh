#!/usr/bin/env bash
set -euo pipefail

bash scripts/bootstrap.sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python -m py_compile app.py
