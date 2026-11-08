#!/usr/bin/env bash
# Checks that a release version matches every version source in the workspace.
#
# Usage: scripts/check-version.sh <version>
#        <version> is X.Y.Z or X.Y.Z-rcN; a leading "v" is ignored, so the
#        release workflow can pass the tag name as is.
#
# Checked:
#   version = "<version>"         agent-aidf/pyproject.toml
#                                 kobkob-kaidf-generator/pyproject.toml
#                                 mcp-aidf/pyproject.toml
#   SERVER_VERSION = "<version>"  mcp-aidf/app.py
#   a "## [<version>]" heading    CHANGELOG.md, agent-aidf/CHANGELOG.md,
#                                 kobkob-kaidf-generator/CHANGELOG.md,
#                                 mcp-aidf/CHANGELOG.md
#
# Exit status: 0 when every check passes, 1 when any fails, 2 on bad usage.
# .github/workflows/release.yml runs this against the pushed tag; run it
# locally before tagging with `make check-version VERSION=X.Y.Z`.
set -euo pipefail

usage() {
  echo "Usage: $0 <version>   (e.g. 0.6.1, v0.6.1 or 0.7.0-rc1)" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
VERSION="${1#v}"
if ! [[ "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]]; then
  echo "error: '${1}' is not a version like X.Y.Z or X.Y.Z-rcN" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# A version only contains [0-9A-Za-z.-]; the dot is its one regex metacharacter.
VERSION_RE="$(printf '%s' "${VERSION}" | sed 's/\./\\./g')"

FAILURES=0

report() { # report <ok|FAIL> <message>
  if [[ "$1" == ok ]]; then
    echo "ok    $2"
  else
    echo "FAIL  $2"
    FAILURES=$((FAILURES + 1))
  fi
}

# check_assignment <file> <name>
# The first line of <file> that reads `<name> = "..."` at column 0 must hold VERSION.
check_assignment() {
  local file="$1" name="$2" found
  if [[ ! -f "${file}" ]]; then
    report FAIL "${file}: file not found"
    return
  fi
  found="$(sed -n "s/^${name} = \"\([^\"]*\)\".*$/\1/p" "${file}" | head -n 1)"
  if [[ -z "${found}" ]]; then
    report FAIL "${file}: no line '${name} = \"...\"' found"
  elif [[ "${found}" == "${VERSION}" ]]; then
    report ok "${file}: ${name} = \"${found}\""
  else
    report FAIL "${file}: ${name} = \"${found}\", expected \"${VERSION}\""
  fi
}

# check_changelog <file>
# <file> must have a Keep a Changelog heading for VERSION: `## [<version>]`.
check_changelog() {
  local file="$1"
  if [[ ! -f "${file}" ]]; then
    report FAIL "${file}: file not found"
    return
  fi
  if grep -q "^## \[${VERSION_RE}\]" "${file}"; then
    report ok "${file}: has a '## [${VERSION}]' section"
  else
    report FAIL "${file}: no '## [${VERSION}]' section (move the [Unreleased] notes under '## [${VERSION}] - YYYY-MM-DD')"
  fi
}

echo "Checking the workspace against version ${VERSION}"
check_assignment agent-aidf/pyproject.toml version
check_assignment kobkob-kaidf-generator/pyproject.toml version
check_assignment mcp-aidf/pyproject.toml version
check_assignment mcp-aidf/app.py SERVER_VERSION
check_changelog CHANGELOG.md
check_changelog agent-aidf/CHANGELOG.md
check_changelog kobkob-kaidf-generator/CHANGELOG.md
check_changelog mcp-aidf/CHANGELOG.md

if [[ "${FAILURES}" -gt 0 ]]; then
  echo "error: ${FAILURES} check(s) failed for version ${VERSION}" >&2
  exit 1
fi
echo "All version sources and changelogs match ${VERSION}"
