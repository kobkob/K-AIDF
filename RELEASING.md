# Releasing

## Versioning

This project uses SemVer during `0.y.z` development:

- increment `z` for backward-compatible fixes
- increment `y` for new protocol capabilities, auth behavior, or deployment changes
- move to `1.0.0` when MCP behavior and connector-facing contracts are stable

## Release Steps

1. Update the version string in `app.py` if the server-reported version changes.
2. Update `CHANGELOG.md`.
3. Run:

```bash
python -m py_compile app.py
python -c "import app"
```

4. Commit the release changes.
5. Create and push a tag like `v0.1.1`.
6. Let GitHub Actions publish the release from the tag.

