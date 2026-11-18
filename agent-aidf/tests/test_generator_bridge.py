"""The generator runs in-process, is found without the workspace layout, and is never installed.

These tests run from an isolated directory outside the repository. The generator is either a
stand-in package written under tmp_path (so no real generator is needed) or, for the integration
test, the kobkob-kaidf-generator checkout named by KAIDF_GENERATOR_DIR when it exists.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from agent_aidf import generator_bridge as bridge

cli_main = importlib.import_module("agent_aidf.cli.main")

REPO_GENERATOR = Path(__file__).resolve().parents[2] / "kobkob-kaidf-generator"


@pytest.fixture(autouse=True)
def _isolate_generator_import(monkeypatch: pytest.MonkeyPatch):
    """Each test sees a clean import state; anything it loads is dropped afterwards."""
    for name in [m for m in sys.modules if m == "kaidf_gen" or m.startswith("kaidf_gen.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.delenv(bridge.GENERATOR_DIR_ENV, raising=False)
    path_before = list(sys.path)
    yield
    sys.path[:] = path_before
    for name in [m for m in sys.modules if m == "kaidf_gen" or m.startswith("kaidf_gen.")]:
        sys.modules.pop(name, None)


def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Make any subprocess start fail the test; returns the list it records attempts in."""
    attempts: list[str] = []

    def refuse(*args, **kwargs):
        attempts.append(str(args[0] if args else kwargs.get("args")))
        raise AssertionError("the generator must not run in a subprocess or pip")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    return attempts


def _stand_in_generator(root: Path, *, fail: str | None = None) -> Path:
    """A minimal `kaidf_gen` package under root/src, with the parts the bridge calls."""
    src = root / "src" / "kaidf_gen"
    (src / "specs").mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "specs" / "kaidf.default.yaml").write_text("version: '1.0'\n", encoding="utf-8")
    (src / "errors.py").write_text("class KaidfGenError(Exception):\n    pass\n", encoding="utf-8")
    (src / "loader.py").write_text(
        "def load_yaml(path):\n    return {'source': str(path)}\n", encoding="utf-8"
    )
    body = (
        "from dataclasses import dataclass\n"
        "from .errors import KaidfGenError\n"
        "@dataclass(frozen=True)\n"
        "class GenerateOptions:\n"
        "    force: bool = False\n"
        "def generate(spec, out_dir, options):\n"
        f"    if {fail!r}:\n"
        f"        raise KaidfGenError({fail or ''!r})\n"
        "    from pathlib import Path\n"
        "    target = Path(out_dir) / 'kobkob-kaidf'\n"
        "    target.mkdir(parents=True, exist_ok=True)\n"
        "    (target / 'README.md').write_text('# stand-in\\n', encoding='utf-8')\n"
        "    (target / 'spec-source.txt').write_text(spec['source'], encoding='utf-8')\n"
        "    return target\n"
    )
    (src / "generator.py").write_text(body, encoding="utf-8")
    return root


# --- resolution ---------------------------------------------------------------------------------


def test_missing_generator_fails_with_the_way_to_provide_it(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(sys.modules, "kaidf_gen", None)  # import raises ImportError

    with pytest.raises(bridge.GeneratorUnavailableError, match="KAIDF_GENERATOR_DIR"):
        bridge.default_spec_path()


def test_override_without_a_package_is_a_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setitem(sys.modules, "kaidf_gen", None)
    monkeypatch.setenv(bridge.GENERATOR_DIR_ENV, str(tmp_path / "not-a-checkout"))

    with pytest.raises(bridge.GeneratorUnavailableError, match="does not contain src/kaidf_gen"):
        bridge.default_spec_path()


def test_override_points_the_import_at_its_checkout(monkeypatch: pytest.MonkeyPatch, tmp_path):
    # Not installed here, and the fixture clears earlier imports, so the override resolves it.
    checkout = _stand_in_generator(tmp_path / "checkout")
    monkeypatch.setenv(bridge.GENERATOR_DIR_ENV, str(checkout))

    spec = bridge.default_spec_path()

    assert spec == checkout / "src" / "kaidf_gen" / "specs" / "kaidf.default.yaml"
    assert str(checkout / "src") in sys.path


def test_the_workspace_sibling_is_not_searched_implicitly(monkeypatch: pytest.MonkeyPatch):
    # The old locator found kobkob-kaidf-generator next to agent-aidf. Without the override it must
    # not, even when that checkout exists on disk.
    monkeypatch.setitem(sys.modules, "kaidf_gen", None)

    with pytest.raises(bridge.GeneratorUnavailableError):
        bridge.default_spec_path()


# --- in-process generation ----------------------------------------------------------------------


def test_generate_repo_runs_in_process_with_no_subprocess_or_pip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    attempts = _no_subprocess(monkeypatch)
    checkout = _stand_in_generator(tmp_path / "checkout")
    monkeypatch.setenv(bridge.GENERATOR_DIR_ENV, str(checkout))
    spec = tmp_path / "my-spec.yaml"
    spec.write_text("version: '1.0'\n", encoding="utf-8")
    out = tmp_path / "out"

    target = bridge.generate_repo(spec, out, force=False)

    assert target == out / "kobkob-kaidf"
    assert (target / "README.md").read_text(encoding="utf-8") == "# stand-in\n"
    assert (target / "spec-source.txt").read_text(encoding="utf-8") == str(spec)
    assert attempts == []


def test_generator_refusals_become_bridge_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    checkout = _stand_in_generator(tmp_path / "checkout", fail="spec is invalid")
    monkeypatch.setenv(bridge.GENERATOR_DIR_ENV, str(checkout))

    with pytest.raises(bridge.GeneratorError, match="spec is invalid"):
        bridge.generate_repo(tmp_path / "x.yaml", tmp_path / "out", force=False)


def test_kob_compile_generates_from_an_isolated_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
):
    attempts = _no_subprocess(monkeypatch)
    checkout = _stand_in_generator(tmp_path / "checkout")
    monkeypatch.setenv(bridge.GENERATOR_DIR_ENV, str(checkout))
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert cli_main._run_cli(["compile", "--out", str(tmp_path / "out")]) == 0

    assert (tmp_path / "out" / "kobkob-kaidf" / "README.md").is_file()
    assert "Generated template framework inside" in capsys.readouterr().out
    assert attempts == []


def test_kob_compile_reports_a_missing_generator_in_one_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
):
    monkeypatch.setitem(sys.modules, "kaidf_gen", None)
    monkeypatch.chdir(tmp_path)

    assert cli_main._run_cli(["compile", "--out", str(tmp_path / "out")]) == 1

    captured = capsys.readouterr()
    assert captured.err.startswith("error: The K-AIDF generator is not installed")
    assert "Traceback" not in captured.err


# --- integration with the real generator ---------------------------------------------------------


@pytest.mark.skipif(
    not (REPO_GENERATOR / "src" / "kaidf_gen" / "__init__.py").is_file(),
    reason="the kobkob-kaidf-generator checkout is not present",
)
def test_real_generator_builds_a_repository_through_the_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _no_subprocess(monkeypatch)
    monkeypatch.setenv(bridge.GENERATOR_DIR_ENV, str(REPO_GENERATOR))
    monkeypatch.chdir(tmp_path)

    assert cli_main._run_cli(["compile", "--out", str(tmp_path / "out")]) == 0

    assert (tmp_path / "out" / "kobkob-kaidf" / "README.md").is_file()
    assert (tmp_path / "out" / "kobkob-kaidf" / "docs").is_dir()
