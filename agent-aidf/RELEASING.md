# Releasing

## Versioning

This project uses SemVer during `0.y.z` development:

- increment `z` for documentation or implementation fixes
- increment `y` for new CLI, orchestration, or web capabilities
- move to `1.0.0` when the agent behavior and external interfaces are stable

## Release Steps

1. Update `CHANGELOG.md`.
2. Confirm the repository baseline still passes in CI.
3. Commit the release notes.
4. Create and push a tag like `v0.1.1`.
5. Let GitHub Actions publish the release from the tag.

