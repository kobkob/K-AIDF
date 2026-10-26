from __future__ import annotations

import importlib
import io
import tarfile
from pathlib import Path

import pytest

from agent_aidf.extensions import installer
from agent_aidf.extensions.installer import InstallError, install_extension

cli_main = importlib.import_module("agent_aidf.cli.main")

VALID_MAIN = """\
# Extension: demo-pack
# Description: a demo
# Version: 1.0.0
# Author: Tests
# Entrypoints: cli
# Topics: demo
def register(hooks):
    pass
"""


def make_tgz(path: Path, members: dict[str, bytes], symlinks: dict[str, str] | None = None) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name, target in (symlinks or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return path


@pytest.fixture
def target(tmp_path: Path) -> Path:
    return tmp_path / "user-extensions"


@pytest.fixture
def archives(tmp_path: Path) -> Path:
    directory = tmp_path / "archives"
    directory.mkdir()
    return directory


def _leftovers(target: Path) -> list[str]:
    return sorted(p.name for p in target.iterdir()) if target.exists() else []


def test_installs_archive_with_one_top_level_directory(archives, target) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})

    installed = install_extension(str(tgz), target)

    assert installed.name == "demo-pack"
    assert (target / "demo-pack" / "main.py").is_file()
    assert installed.metadata.version == "1.0.0"
    assert _leftovers(target) == ["demo-pack"]


def test_installs_archive_with_main_py_at_root(archives, target) -> None:
    tgz = make_tgz(archives / "root.tar.gz", {"main.py": VALID_MAIN.encode()})

    installed = install_extension(str(tgz), target)

    assert installed.path == target / "demo-pack"
    assert (target / "demo-pack" / "main.py").is_file()


def test_rejects_non_archive_suffix(archives, target) -> None:
    zipped = archives / "demo.zip"
    zipped.write_bytes(b"not a tgz")

    with pytest.raises(InstallError, match=r"must be a \.tgz"):
        install_extension(str(zipped), target)
    assert _leftovers(target) == []


def test_rejects_missing_file(archives, target) -> None:
    with pytest.raises(InstallError, match="no such archive"):
        install_extension(str(archives / "absent.tgz"), target)


def test_rejects_file_that_is_not_gzip(archives, target) -> None:
    fake = archives / "fake.tgz"
    fake.write_bytes(b"plain text, definitely not gzip")

    with pytest.raises(InstallError, match="not a valid gzip"):
        install_extension(str(fake), target)
    assert _leftovers(target) == []


@pytest.mark.parametrize("bad_name", ["../escape/main.py", "/abs/main.py", "a/../../main.py"])
def test_rejects_path_traversal(archives, target, bad_name: str) -> None:
    tgz = make_tgz(archives / "evil.tgz", {bad_name: VALID_MAIN.encode()})

    with pytest.raises(InstallError, match="unsafe archive path"):
        install_extension(str(tgz), target)
    assert _leftovers(target) == []
    assert not (archives.parent / "escape").exists()


def test_rejects_symlink_entries(archives, target) -> None:
    tgz = make_tgz(
        archives / "link.tgz",
        {"demo/main.py": VALID_MAIN.encode()},
        symlinks={"demo/config": "/etc/passwd"},
    )

    with pytest.raises(InstallError, match="not a regular file or directory"):
        install_extension(str(tgz), target)
    assert _leftovers(target) == []


def test_rejects_archive_without_main_py(archives, target) -> None:
    tgz = make_tgz(archives / "nomain.tgz", {"demo/readme.md": b"# hi"})

    with pytest.raises(InstallError, match="must hold main.py"):
        install_extension(str(tgz), target)
    assert _leftovers(target) == []


def test_rejects_two_candidate_directories(archives, target) -> None:
    tgz = make_tgz(
        archives / "two.tgz",
        {"a/main.py": VALID_MAIN.encode(), "b/main.py": VALID_MAIN.encode()},
    )

    with pytest.raises(InstallError, match="exactly one top-level directory"):
        install_extension(str(tgz), target)


def test_rejects_invalid_metadata_and_leaves_nothing(archives, target) -> None:
    bad = VALID_MAIN.replace("Version: 1.0.0", "Version: latest")
    tgz = make_tgz(archives / "bad.tgz", {"demo/main.py": bad.encode()})

    with pytest.raises(InstallError, match="Version must be x.y.z"):
        install_extension(str(tgz), target)
    assert _leftovers(target) == []


def test_rejects_syntax_error_without_running_code(archives, target, tmp_path) -> None:
    marker = tmp_path / "ran"
    code = VALID_MAIN + f"\nopen({str(marker)!r}, 'w').write('x'\n"
    tgz = make_tgz(archives / "syntax.tgz", {"demo/main.py": code.encode()})

    with pytest.raises(InstallError, match="syntax error"):
        install_extension(str(tgz), target)
    assert not marker.exists()
    assert _leftovers(target) == []


def test_rejects_module_without_register(archives, target) -> None:
    code = VALID_MAIN.replace("def register(hooks):\n    pass\n", "X = 1\n")
    tgz = make_tgz(archives / "noreg.tgz", {"demo/main.py": code.encode()})

    with pytest.raises(InstallError, match=r"must define register\(hooks\)"):
        install_extension(str(tgz), target)


def test_rejects_non_utf8_source(archives, target) -> None:
    code = VALID_MAIN.encode() + b"\n# \xff\xfe\n"
    tgz = make_tgz(archives / "latin.tgz", {"demo/main.py": code})

    with pytest.raises(InstallError, match="not valid UTF-8"):
        install_extension(str(tgz), target)


def test_refuses_to_overwrite_an_installed_extension(archives, target) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo/main.py": VALID_MAIN.encode()})
    install_extension(str(tgz), target)
    (target / "demo-pack" / "keep.txt").write_text("mine", encoding="utf-8")

    with pytest.raises(InstallError, match="already installed"):
        install_extension(str(tgz), target)
    assert (target / "demo-pack" / "keep.txt").read_text(encoding="utf-8") == "mine"


def test_refuses_built_in_extension_names(archives, target) -> None:
    code = VALID_MAIN.replace("# Extension: demo-pack", "# Extension: Words")
    tgz = make_tgz(archives / "words.tgz", {"main.py": code.encode()})

    with pytest.raises(InstallError, match="built-in extension name"):
        install_extension(str(tgz), target)
    assert _leftovers(target) == []


def test_rejects_name_that_is_not_a_slug(archives, target) -> None:
    code = VALID_MAIN.replace("# Extension: demo-pack", "# Extension: Bad/Name")
    tgz = make_tgz(archives / "slug.tgz", {"main.py": code.encode()})

    with pytest.raises(InstallError, match="lowercase slug"):
        install_extension(str(tgz), target)


def test_rejects_archives_over_the_extracted_size_limit(archives, target, monkeypatch) -> None:
    monkeypatch.setattr(installer, "MAX_EXTRACTED_BYTES", 10)
    tgz = make_tgz(archives / "big.tgz", {"demo/main.py": VALID_MAIN.encode()})

    with pytest.raises(InstallError, match="expands to more than"):
        install_extension(str(tgz), target)
    assert _leftovers(target) == []


def test_rejects_plain_http_urls(target) -> None:
    with pytest.raises(InstallError, match="must use an https"):
        install_extension("http://example.org/demo.tgz", target)


def test_installs_from_https_url_using_fetched_bytes(archives, target, monkeypatch) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        data = VALID_MAIN.encode()
        info = tarfile.TarInfo("demo/main.py")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    requested: list[str] = []

    def fake_fetch(url: str) -> bytes:
        requested.append(url)
        return buffer.getvalue()

    monkeypatch.setattr(installer, "fetch_remote_archive", fake_fetch)

    installed = install_extension("https://example.org/demo.tgz", target)

    assert requested == ["https://example.org/demo.tgz"]
    assert installed.path == target / "demo-pack"


def test_remote_archive_over_the_size_limit_is_rejected(target, monkeypatch) -> None:
    monkeypatch.setattr(installer, "MAX_ARCHIVE_BYTES", 16)
    monkeypatch.setattr(installer, "fetch_remote_archive", lambda url: b"x" * 64)

    with pytest.raises(InstallError, match="larger than"):
        install_extension("https://example.org/huge.tgz", target)


def test_fetch_rejects_redirect_to_http(monkeypatch) -> None:
    class Redirected:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def geturl(self):
            return "http://mirror.example.org/demo.tgz"

        def read(self, _n):
            return b""

    monkeypatch.setattr(installer.urllib.request, "urlopen", lambda *a, **k: Redirected())

    with pytest.raises(InstallError, match="non-HTTPS"):
        installer.fetch_remote_archive("https://example.org/demo.tgz")


def test_cli_flag_installs_and_reports_success(archives, target, monkeypatch, capsys) -> None:
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(target))
    tgz = make_tgz(archives / "demo.tgz", {"demo/main.py": VALID_MAIN.encode()})

    assert cli_main._run_cli(["-x", str(tgz)]) == 0

    assert (target / "demo-pack" / "main.py").is_file()
    assert "Installed extension demo-pack 1.0.0" in capsys.readouterr().out


def test_cli_flag_reports_failure_without_touching_the_environment(
    archives, target, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(target))
    bad = archives / "bad.tgz"
    bad.write_bytes(b"not gzip")

    assert cli_main._run_cli(["--ext", str(bad)]) == 1

    assert "could not install extension" in capsys.readouterr().err
    assert _leftovers(target) == []
