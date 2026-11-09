"""Install records and integrity checks for user-installed extensions.

When the installer writes an extension it also writes `.kob-install.json` into the extension
directory. The record holds the archive's SHA-256 (the digest the operator approved) and the
SHA-256 of every file that was installed. `kob ext list` recomputes the file digests and reports
what changed since the install.

This detects a modified or added file that the record does not reflect. It does not defend against
someone who can rewrite the record too; for that, keep the extensions directory read-only or
compare the archive digest against a value recorded outside the machine.

`__pycache__` is ignored: importing an extension writes bytecode there, which is not a change to
the extension.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

INSTALL_RECORD_NAME = ".kob-install.json"
RECORD_SCHEMA = 1
_IGNORED_DIR = "__pycache__"

STATUS_VERIFIED = "verified"
STATUS_MODIFIED = "modified"
STATUS_NO_RECORD = "no-record"
STATUS_UNREADABLE = "unreadable"
STATUS_NOT_APPLICABLE = "not-applicable"


@dataclass(frozen=True)
class InstallIntegrity:
    status: str
    archive_sha256: str | None = None
    changes: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "archive_sha256": self.archive_sha256,
            "changes": list(self.changes),
        }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digests(root: Path) -> dict[str, str]:
    """Relative POSIX path -> SHA-256 for every file under root, minus the record and bytecode."""
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if _IGNORED_DIR in relative.parts or relative.as_posix() == INSTALL_RECORD_NAME:
            continue
        if path.is_symlink():
            digests[relative.as_posix()] = "symlink:" + os.readlink(path)
        elif path.is_file():
            digests[relative.as_posix()] = file_sha256(path)
    return digests


def write_install_record(source_dir: Path, *, name: str, source: str, archive_sha256: str) -> None:
    record = {
        "schema": RECORD_SCHEMA,
        "name": name,
        "source": source,
        "archive_sha256": archive_sha256,
        "files": tree_digests(source_dir),
    }
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    (source_dir / INSTALL_RECORD_NAME).write_text(text, encoding="utf-8")


def verify_install(path: Path) -> InstallIntegrity:
    record_path = path / INSTALL_RECORD_NAME
    if not record_path.is_file():
        return InstallIntegrity(STATUS_NO_RECORD)
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("schema") != RECORD_SCHEMA:
            raise ValueError("unknown record schema")
        recorded = record["files"]
        archive = str(record["archive_sha256"])
        if not isinstance(recorded, dict):
            raise ValueError("files is not an object")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return InstallIntegrity(STATUS_UNREADABLE)

    actual = tree_digests(path)
    changes: list[str] = []
    for relative in sorted(recorded.keys() | actual.keys()):
        if relative not in actual:
            changes.append(f"missing: {relative}")
        elif relative not in recorded:
            changes.append(f"added: {relative}")
        elif actual[relative] != recorded[relative]:
            changes.append(f"modified: {relative}")
    if changes:
        return InstallIntegrity(STATUS_MODIFIED, archive, tuple(changes))
    return InstallIntegrity(STATUS_VERIFIED, archive)
