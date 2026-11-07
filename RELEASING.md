# Releasing

K-AIDF is one repository with three components, `agent-aidf`, `kobkob-kaidf-generator` and `mcp-aidf`, that share one version number and one release. A single tag `vX.Y.Z` at the repository root releases all three; components are never tagged or released on their own.

## Versioning

- SemVer while in `0.y.z` development: increment `z` for fixes, `y` for new capabilities or contract changes, and move to `1.0.0` when the external interfaces are stable
- the version is written in four places, and all four must equal the tag without its `v`:
  - `agent-aidf/pyproject.toml` (`version = "..."`)
  - `kobkob-kaidf-generator/pyproject.toml` (`version = "..."`)
  - `mcp-aidf/pyproject.toml` (`version = "..."`)
  - `mcp-aidf/app.py` (`SERVER_VERSION = "..."`, reported in `serverInfo`)
- `agent_aidf.__version__` and `kaidf_gen.__version__` are read from the installed package metadata, so they follow `pyproject.toml` and are not edited by hand
- release candidates are `X.Y.Z-rcN`, tagged `vX.Y.Z-rcN`. The tag, the four version sites and the changelog headings all use the `-rcN` spelling; Python packaging normalizes it to `X.Y.ZrcN` in wheel and sdist file names and in the package metadata

## Steps

1. Start from an up-to-date `main` with a clean working tree and green CI.
2. Set the version in the four version sites:

   ```bash
   scripts/bump-version.sh X.Y.Z
   ```

   The script edits the four files and reports, for each of the four changelogs, whether it already has a `## [X.Y.Z]` section or has `[Unreleased]` notes to move. It does not edit changelogs.

3. Update the four changelogs: `CHANGELOG.md`, `agent-aidf/CHANGELOG.md`, `kobkob-kaidf-generator/CHANGELOG.md` and `mcp-aidf/CHANGELOG.md`. In each, move the notes under `## [Unreleased]` to a new `## [X.Y.Z] - YYYY-MM-DD` section and leave the empty `## [Unreleased]` heading above it. A component without changes still gets a `## [X.Y.Z]` section that says so (for example "version aligned with the workspace release; no functional changes"), because the release workflow requires the heading in all four files. Root entries name the component in backticks and reference issues as `(#NN)`.
4. Check that everything agrees and still passes:

   ```bash
   make check-version VERSION=X.Y.Z   # same as: scripts/check-version.sh X.Y.Z
   make test-all
   ```

5. Commit, push, tag, and push the tag:

   ```bash
   git commit -am "chore(release): bump version to vX.Y.Z"
   git push origin main
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

   If the branch policy requires it, make the bump on a short-lived release branch, merge it through a pull request, and create the tag on the resulting commit on `main`.

## What the tag triggers

Pushing a `v*` tag runs `.github/workflows/release.yml`:

1. `verify-version` runs `scripts/check-version.sh` against the tag: the four version sites must equal the tag without the `v`, and the four changelogs must have a `## [X.Y.Z]` heading. A mismatch fails the run before anything is built.
2. The three component CI workflows (`agent-aidf-ci.yml`, `kobkob-kaidf-generator-ci.yml`, `mcp-aidf-ci.yml`) run through `workflow_call`: markdownlint, `ruff check`, `ruff format --check`, the test suites and the generator's default-spec validation.
3. `build` produces the assets: an sdist and a wheel for `agent-aidf` and for `kobkob-kaidf-generator` (`python -m build`), and `mcp-aidf-X.Y.Z.tar.gz` holding `app.py`, `maturity.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `README.md`, `CHANGELOG.md` and `LICENSE`. They are uploaded as the `release-assets` workflow artifact.
4. `release` creates the GitHub Release for the tag, with generated release notes and the built files attached. A tag that contains a `-` (such as `v0.7.0-rc1`) is published as a prerelease.

The artifacts land in two places: the `release-assets` artifact of the workflow run (kept for the repository's artifact retention period) and, permanently, as assets of the GitHub Release at `https://github.com/kobkob/K-AIDF/releases/tag/vX.Y.Z`.

The packages are not published to PyPI, because no trusted publisher is configured. `release.yml` ends with a comment that says where the publishing job goes once one exists.

## If the release run fails

Fix the cause on `main` first. Then delete the tag locally and remotely, and tag again from the fixed commit:

```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

If the run got as far as creating the GitHub Release, delete that release first (`gh release delete vX.Y.Z --yes`) so the new run starts clean.
