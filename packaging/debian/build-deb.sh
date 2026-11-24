#!/usr/bin/env bash
# Build the kaidf .deb from this source tree, without network access or pip.
#
# Usage: packaging/debian/build-deb.sh [OUT_DIR]     (default OUT_DIR: <repo>/dist)
#
# Layout inside the package:
#   /usr/bin/kob                          launcher (see kob in this directory)
#   /usr/lib/kaidf/agent/src/agent_aidf   the agent
#   /usr/lib/kaidf/generator/src/kaidf_gen the generator, found via KAIDF_GENERATOR_DIR
#   /usr/share/doc/kaidf/copyright        the license
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
out="${1:-$root/dist}"

version="$(sed -n 's/^version = "\(.*\)"/\1/p' "$root/agent-aidf/pyproject.toml" | head -n 1)"
if [[ -z "$version" ]]; then
  echo "build-deb: cannot read the version from agent-aidf/pyproject.toml" >&2
  exit 1
fi
if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "build-deb: dpkg-deb is required (apt install dpkg)" >&2
  exit 1
fi

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
pkg="$stage/kaidf_${version}_all"

mkdir -p \
  "$pkg/DEBIAN" \
  "$pkg/usr/bin" \
  "$pkg/usr/lib/kaidf/agent/src" \
  "$pkg/usr/lib/kaidf/generator/src" \
  "$pkg/usr/share/doc/kaidf"

cp -r "$root/agent-aidf/src/agent_aidf" "$pkg/usr/lib/kaidf/agent/src/"
cp -r "$root/kobkob-kaidf-generator/src/kaidf_gen" "$pkg/usr/lib/kaidf/generator/src/"
find "$pkg/usr/lib/kaidf" -name __pycache__ -type d -prune -exec rm -rf {} +

install -m 0755 "$here/kob" "$pkg/usr/bin/kob"
install -m 0644 "$root/LICENSE" "$pkg/usr/share/doc/kaidf/copyright"
sed "s/@VERSION@/$version/" "$here/control.in" > "$pkg/DEBIAN/control"

mkdir -p "$out"
deb="$out/kaidf_${version}_all.deb"
dpkg-deb --root-owner-group --build "$pkg" "$deb" >/dev/null
echo "$deb"
