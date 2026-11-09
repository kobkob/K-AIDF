from __future__ import annotations

import importlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from agent_aidf.extensions.extension_loader import (
    BUILTIN_COMMANDS,
    BUILTIN_EXTENSIONS_DIR,
    inventory,
    load_extensions,
    render_inventory_text,
    user_extensions_dir,
)
from agent_aidf.extensions.installer import install_extension
from agent_aidf.extensions.integrity import INSTALL_RECORD_NAME, verify_install

cli_main = importlib.import_module("agent_aidf.cli.main")

HEADER = """\
# Extension: {name}
# Description: test extension
# Version: 0.2.0
# Author: Tests
# Entrypoints: cli, prompt
# Topics: testing
"""

FULL_BODY = """
def register(hooks):
    def add(parser):
        parser.add_argument("--demo-flag", default=None)

    def run(args):
        return None

    def configure(sub):
        sub.add_argument("--loud", action="store_true")

    def run_hello(args):
        return 0

    hooks.add_cli_arguments(add)
    hooks.add_cli_handler(run)
    hooks.add_subcommand("hello", "Say hello", configure, run_hello)
    hooks.add_prompt_interceptor(lambda prompt: None)
"""

PLAIN_BODY = "\ndef register(hooks):\n    pass\n"


def _main(name: str, body: str) -> str:
    return HEADER.format(name=name) + body


def _write(root: Path, folder: str, source: str) -> Path:
    directory = root / folder
    directory.mkdir(parents=True)
    (directory / "main.py").write_text(source, encoding="utf-8")
    return directory


def _tgz(path: Path, files: dict[str, bytes]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def _row(data: dict, ext_id: str) -> dict:
    return next(row for row in data["extensions"] if row["id"] == ext_id)


@pytest.fixture
def user_root(tmp_path: Path) -> Path:
    root = tmp_path / "user"
    root.mkdir()
    return root


def test_lists_registrations_of_a_loaded_extension(user_root) -> None:
    _write(user_root, "demo", _main("Demo", FULL_BODY))
    registry = load_extensions(roots=[user_root], disabled=[])
    data = inventory(registry)

    row = _row(data, "demo")
    assert row["state"] == "loaded"
    assert row["origin"] == "user"
    assert row["name"] == "Demo"
    assert row["version"] == "0.2.0"
    assert row["author"] == "Tests"
    assert row["error"] is None
    assert row["registered"] == {
        "arguments": 1,
        "cli_handlers": 1,
        "subcommands": ["hello"],
        "prompt_interceptors": 1,
    }
    # Installed by hand, not by the installer: there is no record to verify against.
    assert row["integrity"] == {"status": "no-record", "archive_sha256": None, "changes": []}


def test_failed_extension_is_listed_with_its_error(user_root) -> None:
    _write(
        user_root,
        "broken",
        _main("Broken", "\ndef register(hooks):\n    raise RuntimeError('boom')\n"),
    )
    registry = load_extensions(roots=[user_root], disabled=[])
    row = _row(inventory(registry), "broken")

    assert row["state"] == "failed"
    assert row["error"] == "boom"
    assert row["name"] == "Broken"
    assert row["registered"]["subcommands"] == []
    assert row["registered"]["prompt_interceptors"] == 0


def test_disabled_and_shadowed_extensions_are_listed(user_root, tmp_path) -> None:
    builtin_like = tmp_path / "builtin-like"
    builtin_like.mkdir()
    _write(builtin_like, "dup", _main("Dup", PLAIN_BODY))
    _write(user_root, "dup", _main("Dup", PLAIN_BODY))
    _write(user_root, "off", _main("Off", PLAIN_BODY))
    registry = load_extensions(roots=[builtin_like, user_root], disabled=["off"])
    data = inventory(registry)

    assert _row(data, "off")["state"] == "disabled"
    assert _row(data, "off")["name"] == "Off"
    states = sorted(row["state"] for row in data["extensions"] if row["id"] == "dup")
    assert states == ["loaded", "shadowed"]


def test_builtin_extensions_report_integrity_not_applicable() -> None:
    registry = load_extensions(roots=[BUILTIN_EXTENSIONS_DIR], disabled=[])
    data = inventory(registry)

    assert {row["id"] for row in data["extensions"]} >= {"words", "ext"}
    for row in data["extensions"]:
        assert row["origin"] == "built-in"
        assert row["integrity"]["status"] == "not-applicable"


def test_installed_extension_verifies_then_reports_each_kind_of_change(tmp_path, user_root) -> None:
    archive = _tgz(
        tmp_path / "demo.tgz",
        {
            "demo/main.py": _main("Demo", FULL_BODY).encode("utf-8"),
            "demo/data.txt": b"original\n",
        },
    )
    installed = install_extension(str(archive), user_root)
    record = json.loads((installed.path / INSTALL_RECORD_NAME).read_text(encoding="utf-8"))
    assert record["archive_sha256"]
    assert set(record["files"]) == {"main.py", "data.txt"}

    def integrity() -> dict:
        return _row(inventory(load_extensions(roots=[user_root], disabled=[])), "demo")["integrity"]

    verified = integrity()
    assert verified["status"] == "verified"
    assert verified["archive_sha256"] == record["archive_sha256"]
    assert verified["changes"] == []

    (installed.path / "data.txt").write_text("tampered\n", encoding="utf-8")
    assert integrity()["changes"] == ["modified: data.txt"]

    (installed.path / "data.txt").write_text("original\n", encoding="utf-8")
    (installed.path / "extra.py").write_text("X = 1\n", encoding="utf-8")
    assert integrity()["changes"] == ["added: extra.py"]

    (installed.path / "extra.py").unlink()
    (installed.path / "data.txt").unlink()
    assert integrity()["changes"] == ["missing: data.txt"]


def test_bytecode_written_by_importing_does_not_count_as_a_change(tmp_path, user_root) -> None:
    archive = _tgz(
        tmp_path / "demo.tgz", {"demo/main.py": _main("Demo", PLAIN_BODY).encode("utf-8")}
    )
    installed = install_extension(str(archive), user_root)
    cache = installed.path / "__pycache__"
    cache.mkdir()
    (cache / "main.cpython-311.pyc").write_bytes(b"\x00bytecode")

    assert verify_install(installed.path).status == "verified"


def test_unreadable_record_is_reported(user_root) -> None:
    directory = _write(user_root, "demo", _main("Demo", PLAIN_BODY))
    (directory / INSTALL_RECORD_NAME).write_text("not json", encoding="utf-8")

    assert verify_install(directory).status == "unreadable"


def test_text_output_shows_failed_state(user_root) -> None:
    _write(
        user_root,
        "broken",
        _main("Broken", "\ndef register(hooks):\n    raise ValueError('nope')\n"),
    )
    data = inventory(load_extensions(roots=[user_root], disabled=[]))
    text = render_inventory_text(data)

    assert "broken  0.2.0  Tests  [user, failed]" in text
    assert "error:       nope" in text


def test_text_output_flags_modified_installs(tmp_path, user_root) -> None:
    archive = _tgz(
        tmp_path / "demo.tgz", {"demo/main.py": _main("Demo", PLAIN_BODY).encode("utf-8")}
    )
    installed = install_extension(str(archive), user_root)
    (installed.path / "main.py").write_text(
        _main("Demo", PLAIN_BODY) + "# edited\n", encoding="utf-8"
    )

    text = render_inventory_text(inventory(load_extensions(roots=[user_root], disabled=[])))

    assert "MODIFIED since install: modified: main.py" in text


def test_text_output_for_empty_inventory() -> None:
    text = render_inventory_text(inventory(load_extensions(roots=[], disabled=[])))
    assert "No extensions found." in text


def test_cli_json_lists_builtin_and_user_extensions(capsys) -> None:
    user = user_extensions_dir()
    _write(user, "demo", _main("Demo", FULL_BODY))

    assert cli_main._run_cli(["ext", "list", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)

    assert data["schema_version"] == 1
    assert data["builtin_dir"] == str(BUILTIN_EXTENSIONS_DIR)
    assert data["user_dir"] == str(user)
    ids = {row["id"] for row in data["extensions"]}
    assert {"words", "ext", "demo"} <= ids
    assert _row(data, "demo")["registered"]["subcommands"] == ["hello"]


def test_cli_text_lists_extensions(capsys) -> None:
    assert cli_main._run_cli(["ext", "list"]) == 0
    out = capsys.readouterr().out

    assert "words" in out
    assert "[built-in, loaded]" in out


def test_cli_ext_without_subcommand_is_a_usage_error(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main._run_cli(["ext"])
    assert excinfo.value.code == 2


def test_ext_and_appliance_are_builtin_commands() -> None:
    assert {"ext", "appliance"} <= BUILTIN_COMMANDS
