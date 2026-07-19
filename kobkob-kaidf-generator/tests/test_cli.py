from pathlib import Path

import pytest

from kaidf_gen.cli import main


def test_validate_command_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["validate", "specs/kaidf.default.yaml"])

    assert excinfo.value.code == 0
    assert "Spec is valid" in capsys.readouterr().out


def test_generate_command_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_dir = tmp_path / "out"

    with pytest.raises(SystemExit) as excinfo:
        main(["generate", "specs/kaidf.default.yaml", "--out", str(out_dir)])

    assert excinfo.value.code == 0
    assert "Generated:" in capsys.readouterr().out
    assert (out_dir / "kobkob-kaidf" / "README.md").exists()


def test_validate_command_returns_error_code_for_missing_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.yaml"

    with pytest.raises(SystemExit) as excinfo:
        main(["validate", str(missing)])

    assert excinfo.value.code == 2
    assert "Spec file not found" in capsys.readouterr().err
