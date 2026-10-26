from __future__ import annotations

from pathlib import Path

import pytest

from agent_aidf.extensions.metadata import MetadataError, parse_metadata_text, read_metadata

VALID_HEADER = """\
# Extension: Demo
# Description: A demo extension
# Version: 1.2.3
# Author: Kobkob LLC
# Entrypoints: cli, prompt
# Topics: demo, testing
"""


def test_parses_all_required_fields() -> None:
    metadata = parse_metadata_text(VALID_HEADER + "\ndef register(hooks):\n    pass\n")

    assert metadata.name == "Demo"
    assert metadata.description == "A demo extension"
    assert metadata.version == "1.2.3"
    assert metadata.author == "Kobkob LLC"
    assert metadata.entrypoints == ("cli", "prompt")
    assert metadata.topics == ("demo", "testing")


def test_tolerates_blank_lines_and_unrelated_comments() -> None:
    text = "#!/usr/bin/env python3\n\n# Some note about the file\n" + VALID_HEADER

    assert parse_metadata_text(text).name == "Demo"


def test_header_after_code_is_ignored() -> None:
    text = "import os\n" + VALID_HEADER

    with pytest.raises(MetadataError, match="missing metadata"):
        parse_metadata_text(text)


def test_reports_every_missing_field() -> None:
    with pytest.raises(MetadataError) as excinfo:
        parse_metadata_text("# Extension: Demo\n")

    message = str(excinfo.value)
    for field in ("Description", "Version", "Author", "Entrypoints", "Topics"):
        assert field in message


def test_rejects_duplicate_field() -> None:
    with pytest.raises(MetadataError, match="duplicate 'Version'"):
        parse_metadata_text(VALID_HEADER + "# Version: 9.9.9\n")


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "1.2.3-beta", "one"])
def test_rejects_non_semver_version(version: str) -> None:
    text = VALID_HEADER.replace("Version: 1.2.3", f"Version: {version}")

    with pytest.raises(MetadataError, match="Version must be x.y.z"):
        parse_metadata_text(text)


def test_rejects_unknown_entrypoint() -> None:
    text = VALID_HEADER.replace("Entrypoints: cli, prompt", "Entrypoints: cli, http")

    with pytest.raises(MetadataError, match="Entrypoints must be from"):
        parse_metadata_text(text)


def test_rejects_empty_topics() -> None:
    text = VALID_HEADER.replace("Topics: demo, testing", "Topics:")

    with pytest.raises(MetadataError, match="missing metadata: Topics"):
        parse_metadata_text(text)


def test_read_metadata_reads_a_file(tmp_path: Path) -> None:
    main = tmp_path / "main.py"
    main.write_text(VALID_HEADER + "\ndef register(hooks):\n    pass\n", encoding="utf-8")

    assert read_metadata(main).version == "1.2.3"


def test_read_metadata_does_not_execute_the_file(tmp_path: Path) -> None:
    marker = tmp_path / "ran.txt"
    main = tmp_path / "main.py"
    main.write_text(
        VALID_HEADER + f"\nopen({str(marker)!r}, 'w').write('x')\n",
        encoding="utf-8",
    )

    read_metadata(main)

    assert not marker.exists()


def test_read_metadata_reports_unreadable_path(tmp_path: Path) -> None:
    with pytest.raises(MetadataError, match="cannot read"):
        read_metadata(tmp_path / "missing" / "main.py")


def test_builtin_headers_are_valid() -> None:
    from agent_aidf.extensions.extension_loader import BUILTIN_EXTENSIONS_DIR

    for main in sorted(BUILTIN_EXTENSIONS_DIR.glob("*/main.py")):
        assert read_metadata(main).entrypoints, main
