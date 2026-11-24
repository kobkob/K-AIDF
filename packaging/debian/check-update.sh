#!/usr/bin/env bash
# Report whether a newer K-AIDF release exists than this checkout's version. Read-only.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
api="https://api.github.com/repos/kobkob/K-AIDF/releases/latest"

installed="$(sed -n 's/^version = "\(.*\)"/\1/p' "$root/agent-aidf/pyproject.toml" | head -n 1)"
if ! latest="$(curl -fsSL --max-time 15 "$api" |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"].lstrip("v"))')"; then
  echo "check-update: could not read the latest release from $api" >&2
  exit 1
fi

if [[ "$latest" == "$installed" ]]; then
  echo "kaidf $installed is the latest release."
else
  echo "kaidf $installed in this checkout; latest release is $latest. Run: make upgrade"
fi
