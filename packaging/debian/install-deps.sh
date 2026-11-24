#!/bin/sh
# Create or refresh /usr/lib/kaidf/venv with the libraries in requirements.txt.
# Run by the package's postinst. Safe to run again: pip only installs what is missing or too old.
set -e

KAIDF_HOME="${KAIDF_HOME:-/usr/lib/kaidf}"
KAIDF_VENV="${KAIDF_VENV:-$KAIDF_HOME/venv}"

if [ ! -x "$KAIDF_VENV/bin/python" ]; then
  python3 -m venv "$KAIDF_VENV" || {
    echo "kaidf: could not create $KAIDF_VENV. Install python3-venv and run this again." >&2
    exit 1
  }
fi

"$KAIDF_VENV/bin/python" -m pip install --quiet --disable-pip-version-check \
  -r "$KAIDF_HOME/requirements.txt" || {
  echo "kaidf: could not install the Python libraries (is the network reachable?)." >&2
  echo "kaidf: run  sudo $KAIDF_HOME/install-deps.sh  again once it is." >&2
  exit 1
}
