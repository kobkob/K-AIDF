#!/usr/bin/env bash
set -euo pipefail

# Cloud notebooks (Kaggle, Colab) and minimal containers can ship a Python without ensurepip.
# Then `python -m venv` fails, or leaves a venv with no pip. In that case the venv is created
# with --system-site-packages and nothing is installed: it reuses the parent interpreter's
# packages, which must include the generator's runtime dependencies.
RUNTIME_MODULES=(yaml jsonschema)
PARENT_MARKER=".venv/.parent-packages"

create_venv() {
  if python -m venv .venv 2>/dev/null && .venv/bin/python -m pip --version >/dev/null 2>&1; then
    return 0
  fi
  echo "bootstrap: a full venv is unavailable (ensurepip missing?); reusing the parent packages" >&2
  rm -rf .venv
  python -m venv --without-pip --system-site-packages .venv
  touch "${PARENT_MARKER}"
}

if [[ ! -x .venv/bin/python ]]; then
  create_venv
fi

if [[ -f "${PARENT_MARKER}" ]]; then
  for module in "${RUNTIME_MODULES[@]}"; do
    if ! .venv/bin/python -c "import ${module}" 2>/dev/null; then
      echo "bootstrap: '${module}' cannot be imported from the parent Python; install it there (python -m pip install PyYAML jsonschema)" >&2
      exit 1
    fi
  done
  exit 0
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

if [[ ! -f "${STAMP_FILE}" ]] || [[ pyproject.toml -nt "${STAMP_FILE}" ]]; then
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -e ".[dev]"
  touch "${STAMP_FILE}"
fi
