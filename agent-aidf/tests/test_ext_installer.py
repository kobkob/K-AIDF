from __future__ import annotations

import hashlib
import importlib
import io
import sys
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


def _approve(preview) -> bool:
    return True


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

    installed = install_extension("https://example.org/demo.tgz", target, confirm=_approve)

    assert requested == ["https://example.org/demo.tgz"]
    assert installed.path == target / "demo-pack"


def test_remote_archive_over_the_size_limit_is_rejected(target, monkeypatch) -> None:
    monkeypatch.setattr(installer, "MAX_ARCHIVE_BYTES", 16)
    monkeypatch.setattr(installer, "fetch_remote_archive", lambda url: b"x" * 64)

    with pytest.raises(InstallError, match="larger than"):
        install_extension("https://example.org/huge.tgz", target, confirm=_approve)


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


# ---------------------------------------------------------------- SHA-256 and consent (#68)

DEMO_URL = "https://example.org/demo.tgz"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _serve(monkeypatch, path: Path, calls: list[str] | None = None) -> None:
    def fake_fetch(url: str) -> bytes:
        if calls is not None:
            calls.append(url)
        return path.read_bytes()

    monkeypatch.setattr(installer, "fetch_remote_archive", fake_fetch)


class _FakeStdin(io.StringIO):
    def __init__(self, text: str, tty: bool) -> None:
        super().__init__(text)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def _as_terminal(monkeypatch, answer: str = "") -> None:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(answer + "\n", tty=True))
    monkeypatch.setattr(sys, "stdout", _FakeStdin("", tty=True))


def _as_pipe(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", _FakeStdin("", tty=False))


def test_local_install_with_matching_sha256_succeeds(archives, target) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})

    installed = install_extension(str(tgz), target, expected_sha256=_sha(tgz))

    assert installed.path == target / "demo-pack"


@pytest.mark.parametrize("form", ["upper", "prefixed"])
def test_sha256_accepts_uppercase_and_prefixed_forms(archives, target, form: str) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    digest = _sha(tgz)
    value = digest.upper() if form == "upper" else f"sha256:{digest}"

    assert install_extension(str(tgz), target, expected_sha256=value).name == "demo-pack"


def test_local_install_with_wrong_sha256_is_refused(archives, target) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})

    with pytest.raises(InstallError, match="SHA-256 mismatch"):
        install_extension(str(tgz), target, expected_sha256="0" * 64)

    assert _leftovers(target) == []


def test_malformed_sha256_is_rejected_before_anything_is_read(archives, target) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})

    with pytest.raises(InstallError, match="64 hexadecimal"):
        install_extension(str(tgz), target, expected_sha256="abc123")


def test_remote_install_with_matching_hash_and_consent_shows_the_preview(
    archives, target, monkeypatch
) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    _serve(monkeypatch, tgz)
    previews = []

    def approve(preview) -> bool:
        previews.append(preview)
        return True

    installed = install_extension(DEMO_URL, target, expected_sha256=_sha(tgz), confirm=approve)

    assert installed.path == target / "demo-pack"
    [preview] = previews
    assert preview.name == "demo-pack"
    assert preview.author == "Tests"
    assert preview.version == "1.0.0"
    assert preview.description == "a demo"
    assert preview.source == DEMO_URL
    assert preview.sha256 == _sha(tgz)


def test_remote_install_with_wrong_hash_is_refused_before_the_operator_is_asked(
    archives, target, monkeypatch
) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    _serve(monkeypatch, tgz)
    asked = []

    with pytest.raises(InstallError, match="SHA-256 mismatch"):
        install_extension(
            DEMO_URL,
            target,
            expected_sha256="f" * 64,
            confirm=lambda preview: asked.append(preview) or True,
        )

    assert asked == []
    assert _leftovers(target) == []


def test_remote_install_without_a_consent_callback_is_refused(
    archives, target, monkeypatch
) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    calls: list[str] = []
    _serve(monkeypatch, tgz, calls)

    with pytest.raises(InstallError, match="needs the operator's consent"):
        install_extension(DEMO_URL, target)

    assert calls == []
    assert _leftovers(target) == []


def test_remote_install_declined_by_the_operator_writes_nothing(
    archives, target, monkeypatch
) -> None:
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    _serve(monkeypatch, tgz)

    with pytest.raises(InstallError, match="cancelled by the operator"):
        install_extension(DEMO_URL, target, confirm=lambda preview: False)

    assert _leftovers(target) == []


def test_cli_prompt_accepts_y_and_installs(archives, target, monkeypatch, capsys) -> None:
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(target))
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    _serve(monkeypatch, tgz)
    _as_terminal(monkeypatch, "y")

    assert cli_main._run_cli(["-x", DEMO_URL]) == 0

    out = sys.stdout.getvalue()  # _as_terminal swapped stdout for a fake that records it
    assert "Autor:      Tests" in out and _sha(tgz) in out
    assert (target / "demo-pack" / "main.py").is_file()


def test_cli_prompt_defaults_to_no(archives, target, monkeypatch, capsys) -> None:
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(target))
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    _serve(monkeypatch, tgz)
    _as_terminal(monkeypatch, "")

    assert cli_main._run_cli(["-x", DEMO_URL]) == 1

    assert "cancelled by the operator" in capsys.readouterr().err
    assert _leftovers(target) == []


def test_cli_non_interactive_remote_install_fails_safely_without_yes(
    archives, target, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(target))
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    _serve(monkeypatch, tgz)
    _as_pipe(monkeypatch)

    assert cli_main._run_cli(["-x", DEMO_URL]) == 1

    assert "--yes" in capsys.readouterr().err
    assert _leftovers(target) == []


def test_cli_yes_flag_installs_without_a_terminal(archives, target, monkeypatch, capsys) -> None:
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(target))
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})
    _serve(monkeypatch, tgz)
    _as_pipe(monkeypatch)

    assert cli_main._run_cli(["-x", DEMO_URL, "--yes"]) == 0

    assert (target / "demo-pack" / "main.py").is_file()
    assert "approving without a prompt" in capsys.readouterr().out


def test_cli_sha256_flag_pins_a_local_archive(archives, target, monkeypatch, capsys) -> None:
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(target))
    tgz = make_tgz(archives / "demo.tgz", {"demo-pack/main.py": VALID_MAIN.encode()})

    assert cli_main._run_cli(["-x", str(tgz), "--sha256", "0" * 64]) == 1

    assert "SHA-256 mismatch" in capsys.readouterr().err
    assert _leftovers(target) == []


def test_cli_rejects_sha256_or_yes_without_a_source(monkeypatch, capsys) -> None:
    assert cli_main._run_cli(["--yes"]) == 2
    assert "apply only with -x" in capsys.readouterr().err
