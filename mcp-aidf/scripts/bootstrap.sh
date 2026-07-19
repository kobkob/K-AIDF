#!/usr/bin/env bash
set -euo pipefail

if [[ ! -x .venv/bin/python ]]; then
  python -m venv .venv
fi

STAMP_FILE=".venv/.bootstrap-stamp"
LOCK_DIR=".venv/.bootstrap-lock"

while ! mkdir "${LOCK_DIR}" 2>/dev/null; do
  sleep 0.1
done

cleanup() {
  rmdir "${LOCK_DIR}" >/dev/null 2>&1 || true
}

trap cleanup EXIT

if [[ ! -f "${STAMP_FILE}" ]] || [[ requirements.txt -nt "${STAMP_FILE}" ]]; then
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt
  touch "${STAMP_FILE}"
fi
