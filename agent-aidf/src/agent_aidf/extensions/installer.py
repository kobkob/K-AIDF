"""Install an extension from a local .tgz or an HTTPS .tgz URL into the user extensions directory.

Nothing is written to the destination until the archive has been checked. Extraction happens in a
hidden staging directory inside the target root, which is always removed afterwards, so a rejected
archive leaves the environment as it was.

Validation does not execute the extension. It checks the archive layout, the metadata header, that
`main.py` compiles, and that it defines `register`. Extension code runs only at boot, and only once
it is installed. Installing a remote archive therefore means trusting its author.
"""

from __future__ import annotations

import ast
import re
import shutil
import tarfile
import urllib.error
import urllib.request
import uuid
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .extension_loader import BUILTIN_EXTENSIONS_DIR
from .metadata import ExtensionMetadata, MetadataError, read_metadata

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_BYTES = 50 * 1024 * 1024
MAX_ENTRIES = 500
DOWNLOAD_TIMEOUT_SECONDS = 30

_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class InstallError(Exception):
    """The extension could not be installed. Nothing was left behind in the target directory."""


@dataclass(frozen=True)
class InstalledExtension:
    name: str
    path: Path
    metadata: ExtensionMetadata


def install_extension(source: str, target_root: Path) -> InstalledExtension:
    target_root.mkdir(parents=True, exist_ok=True)
    staging = target_root / f".staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        archive = _resolve_archive(source, staging)
        unpacked = staging / "unpacked"
        unpacked.mkdir()
        _extract(archive, unpacked)
        source_dir = _locate_extension_dir(unpacked)
        metadata = _validate(source_dir / "main.py")
        name = metadata.name.lower()
        if not _NAME.match(name):
            raise InstallError(f"extension name {metadata.name!r} must be a lowercase slug")
        if (BUILTIN_EXTENSIONS_DIR / name).exists():
            raise InstallError(f"{name!r} is a built-in extension name")
        destination = target_root / name
        if destination.exists():
            raise InstallError(f"extension {name!r} is already installed at {destination}")
        _move_into_place(source_dir, destination)
        return InstalledExtension(name=name, path=destination, metadata=metadata)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def fetch_remote_archive(url: str) -> bytes:
    """Download an archive. Kept as its own function so tests can stand in for the network."""
    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            if urlsplit(response.geturl()).scheme != "https":
                raise InstallError("the download redirected to a non-HTTPS address")
            return response.read(MAX_ARCHIVE_BYTES + 1)
    except (urllib.error.URLError, OSError) as exc:
        raise InstallError(f"download failed: {exc}") from exc


def _resolve_archive(source: str, staging: Path) -> Path:
    if "://" in source:
        if urlsplit(source).scheme != "https":
            raise InstallError("remote archives must use an https:// URL")
        _require_tgz_name(urlsplit(source).path)
        data = fetch_remote_archive(source)
        if len(data) > MAX_ARCHIVE_BYTES:
            raise InstallError(f"archive is larger than {MAX_ARCHIVE_BYTES} bytes")
        archive = staging / "download.tgz"
        archive.write_bytes(data)
        return archive

    path = Path(source).expanduser()
    _require_tgz_name(path.name)
    if not path.is_file():
        raise InstallError(f"no such archive: {source}")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise InstallError(f"archive is larger than {MAX_ARCHIVE_BYTES} bytes")
    return path


def _require_tgz_name(name: str) -> None:
    lowered = name.lower()
    if not (lowered.endswith(".tgz") or lowered.endswith(".tar.gz")):
        raise InstallError("the source must be a .tgz (or .tar.gz) archive")


def _extract(archive: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            if len(members) > MAX_ENTRIES:
                raise InstallError(f"archive has more than {MAX_ENTRIES} entries")
            plan: list[tuple[tarfile.TarInfo, Path]] = []
            total = 0
            for member in members:
                relative = _safe_relative_path(member.name)
                if member.isdir():
                    plan.append((member, relative))
                    continue
                if not member.isreg():
                    raise InstallError(
                        f"archive entry {member.name!r} is not a regular file or directory"
                    )
                total += member.size
                if total > MAX_EXTRACTED_BYTES:
                    raise InstallError(f"archive expands to more than {MAX_EXTRACTED_BYTES} bytes")
                plan.append((member, relative))

            # Files are written by hand rather than via tar.extract, so no archive-supplied
            # mode, owner or link can reach the filesystem.
            for member, relative in plan:
                target = destination / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                source_file = tar.extractfile(member)
                if source_file is None:
                    raise InstallError(f"cannot read archive entry {member.name!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with source_file, target.open("wb") as out:
                    shutil.copyfileobj(source_file, out)
    except InstallError:
        raise
    except (tarfile.TarError, OSError, EOFError, zlib.error) as exc:
        raise InstallError(f"not a valid gzip-compressed tar archive: {exc}") from exc


def _safe_relative_path(name: str) -> Path:
    if not name or name.startswith("/") or "\\" in name or ":" in name.split("/")[0]:
        raise InstallError(f"unsafe archive path {name!r}")
    parts = [part for part in PurePosixPath(name).parts if part not in ("", ".")]
    if not parts or ".." in parts:
        raise InstallError(f"unsafe archive path {name!r}")
    return Path(*parts)


def _locate_extension_dir(unpacked: Path) -> Path:
    if (unpacked / "main.py").is_file():
        return unpacked
    candidates = [child for child in unpacked.iterdir() if (child / "main.py").is_file()]
    if len(candidates) != 1 or not candidates[0].is_dir():
        raise InstallError(
            "the archive must hold main.py at its root or in exactly one top-level directory"
        )
    return candidates[0]


def _validate(main: Path) -> ExtensionMetadata:
    try:
        metadata = read_metadata(main)
    except MetadataError as exc:
        raise InstallError(str(exc)) from exc
    try:
        source = main.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InstallError(f"{main.name} is not valid UTF-8: {exc}") from exc
    try:
        tree = ast.parse(source, filename=str(main))
    except SyntaxError as exc:
        raise InstallError(f"{main.name} has a syntax error: {exc}") from exc
    defines_register = any(
        isinstance(node, ast.FunctionDef) and node.name == "register" for node in tree.body
    )
    if not defines_register:
        raise InstallError(f"{main.name} must define register(hooks)")
    return metadata


def _move_into_place(source_dir: Path, destination: Path) -> None:
    try:
        shutil.move(str(source_dir), str(destination))
    except OSError as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise InstallError(f"could not write {destination}: {exc}") from exc
