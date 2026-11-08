#!/usr/bin/env bash
# Sets a new release version in every version source of the workspace, then
# checks the four changelogs and prints what the release workflow will verify.
#
# Usage: scripts/bump-version.sh <version>
#        <version> is X.Y.Z or X.Y.Z-rcN (release candidate); no leading "v".
#
# Updated in place:
#   version = "<version>"         agent-aidf/pyproject.toml
#                                 kobkob-kaidf-generator/pyproject.toml
#                                 mcp-aidf/pyproject.toml
#   SERVER_VERSION = "<version>"  mcp-aidf/app.py
#
# Not updated: CHANGELOG.md, agent-aidf/CHANGELOG.md,
# kobkob-kaidf-generator/CHANGELOG.md and mcp-aidf/CHANGELOG.md. For each one
# the script only reports whether it already has a "## [<version>]" section or
# has notes under "## [Unreleased]" waiting to be moved there. A changelog with
# neither is an error (exit 1) after the version sites have been updated.
set -euo pipefail

usage() {
  echo "Usage: $0 <version>   (e.g. 0.7.0 or 0.7.0-rc1)" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
VERSION="$1"
if ! [[ "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]]; then
  echo "error: '${VERSION}' is not a version like X.Y.Z or X.Y.Z-rcN" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# A version only contains [0-9A-Za-z.-]; the dot is its one regex metacharacter.
VERSION_RE="$(printf '%s' "${VERSION}" | sed 's/\./\\./g')"

FAILURES=0

# set_assignment <file> <name>
# Rewrites the one line of <file> that reads `<name> = "..."` at column 0.
set_assignment() {
  local file="$1" name="$2" matches tmp
  if [[ ! -f "${file}" ]]; then
    echo "error: ${file} not found" >&2
    exit 1
  fi
  matches="$(grep -c "^${name} = \"[^\"]*\"" "${file}" || true)"
  if [[ "${matches}" -ne 1 ]]; then
    echo "error: expected exactly one line '${name} = \"...\"' in ${file}, found ${matches}" >&2
    exit 1
  fi
  tmp="${file}.bump.tmp"
  sed "s/^\(${name} = \)\"[^\"]*\"/\1\"${VERSION}\"/" "${file}" > "${tmp}"
  cat "${tmp}" > "${file}" # keeps the file's mode and inode
  rm -f "${tmp}"
  echo "set   ${file}: ${name} = \"${VERSION}\""
}

# check_changelog <file>
check_changelog() {
  local file="$1" unreleased
  if [[ ! -f "${file}" ]]; then
    echo "FAIL  ${file}: file not found"
    FAILURES=$((FAILURES + 1))
    return
  fi
  if grep -q "^## \[${VERSION_RE}\]" "${file}"; then
    echo "ok    ${file}: has a '## [${VERSION}]' section"
    return
  fi
  # Non-blank, non-heading lines between "## [Unreleased]" and the next "## [" heading.
  unreleased="$(sed -n '/^## \[Unreleased\]/,/^## \[/p' "${file}" | grep -v '^#' | grep '[^[:space:]]' || true)"
  if [[ -n "${unreleased}" ]]; then
    echo "todo  ${file}: move the notes under '## [Unreleased]' to '## [${VERSION}] - $(date +%Y-%m-%d)'"
  else
    echo "FAIL  ${file}: neither a '## [${VERSION}]' section nor notes under '## [Unreleased]'"
    FAILURES=$((FAILURES + 1))
  fi
}

echo "Setting version ${VERSION}"
set_assignment agent-aidf/pyproject.toml version
set_assignment kobkob-kaidf-generator/pyproject.toml version
set_assignment mcp-aidf/pyproject.toml version
set_assignment mcp-aidf/app.py SERVER_VERSION

echo
echo "Changelogs (not edited by this script)"
check_changelog CHANGELOG.md
check_changelog agent-aidf/CHANGELOG.md
check_changelog kobkob-kaidf-generator/CHANGELOG.md
check_changelog mcp-aidf/CHANGELOG.md

echo
echo "On tag v${VERSION}, .github/workflows/release.yml will verify:"
echo "  - version = \"${VERSION}\" in agent-aidf/pyproject.toml, kobkob-kaidf-generator/pyproject.toml and mcp-aidf/pyproject.toml"
echo "  - SERVER_VERSION = \"${VERSION}\" in mcp-aidf/app.py"
echo "  - a '## [${VERSION}]' heading in CHANGELOG.md, agent-aidf/CHANGELOG.md, kobkob-kaidf-generator/CHANGELOG.md and mcp-aidf/CHANGELOG.md"
echo "Then run: scripts/check-version.sh ${VERSION}   (make check-version VERSION=${VERSION})"

if [[ "${FAILURES}" -gt 0 ]]; then
  echo "error: ${FAILURES} changelog(s) have nothing for version ${VERSION}" >&2
  exit 1
fi
