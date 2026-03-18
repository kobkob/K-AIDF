# Releasing

## Versioning

This project uses SemVer during `0.y.z` development:

- increment `z` for backward-compatible fixes
- increment `y` for new features or notable contract changes
- move to `1.0.0` when the generated repository contract is considered stable

## Release Steps

1. Update `pyproject.toml` version.
2. Move relevant notes from `CHANGELOG.md` under `Unreleased` into a dated release section.
3. Run:

```bash
PYTHONPATH=src python -m pytest -q
python -m kaidf_gen.cli validate specs/kaidf.default.yaml
```

4. Commit the release changes.
5. Create and push a tag like `v0.1.1`.
6. Let GitHub Actions publish the release from the tag.

