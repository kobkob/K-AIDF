"""Read the metadata header of an extension's main.py without importing or executing it.

The header is a run of comment lines at the top of the file:

    # Extension: <Nome>
    # Description: <Descrição>
    # Version: <x.y.z>
    # Author: <Autor>
    # Entrypoints: <cli, prompt>
    # Topics: <topicos separados por virgula>

Reading stops at the first line of code, so a large extension costs only a few lines of I/O at
boot, and a malicious file cannot run anything just by being scanned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FIELDS = ("Extension", "Description", "Version", "Author", "Entrypoints", "Topics")
KNOWN_ENTRYPOINTS = frozenset({"cli", "prompt"})

# Only the leading comment block is scanned; this bounds the work for any file.
MAX_HEADER_LINES = 64

_HEADER_LINE = re.compile(r"^#\s?([A-Za-z]+):\s*(.*?)\s*$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


class MetadataError(ValueError):
    """The extension header is missing, malformed, or names an unknown entrypoint."""


@dataclass(frozen=True)
class ExtensionMetadata:
    name: str
    description: str
    version: str
    author: str
    entrypoints: tuple[str, ...]
    topics: tuple[str, ...]


def parse_metadata_text(text: str, source: str = "main.py") -> ExtensionMetadata:
    values: dict[str, str] = {}
    for line_number, raw in enumerate(text.splitlines()[:MAX_HEADER_LINES], start=1):
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("#"):
            break
        match = _HEADER_LINE.match(line)
        if match is None or match.group(1) not in REQUIRED_FIELDS:
            continue
        key, value = match.group(1), match.group(2)
        if key in values:
            raise MetadataError(f"{source}: duplicate '{key}' at line {line_number}")
        values[key] = value

    missing = [field for field in REQUIRED_FIELDS if not values.get(field)]
    if missing:
        raise MetadataError(f"{source}: missing metadata: {', '.join(missing)}")

    version = values["Version"]
    if not _VERSION.match(version):
        raise MetadataError(f"{source}: Version must be x.y.z, got {version!r}")

    entrypoints = _split_list(values["Entrypoints"])
    unknown = [entry for entry in entrypoints if entry not in KNOWN_ENTRYPOINTS]
    if not entrypoints or unknown:
        bad = ", ".join(unknown) or values["Entrypoints"]
        raise MetadataError(
            f"{source}: Entrypoints must be from {', '.join(sorted(KNOWN_ENTRYPOINTS))}, got {bad}"
        )

    topics = _split_list(values["Topics"])
    if not topics:
        raise MetadataError(f"{source}: Topics must list at least one topic")

    return ExtensionMetadata(
        name=values["Extension"],
        description=values["Description"],
        version=version,
        author=values["Author"],
        entrypoints=tuple(entrypoints),
        topics=tuple(topics),
    )


def read_metadata(path: Path) -> ExtensionMetadata:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            head = "".join(handle.readline() for _ in range(MAX_HEADER_LINES))
    except OSError as exc:
        raise MetadataError(f"{path}: cannot read: {exc}") from exc
    return parse_metadata_text(head, source=str(path))


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
