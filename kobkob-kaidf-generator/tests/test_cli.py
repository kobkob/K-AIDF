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


def test_validate_command_reports_malformed_yaml_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text("version: '1.0'\nrepo: [unclosed\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["validate", str(broken)])

    captured = capsys.readouterr()
    assert excinfo.value.code == 2
    assert "Malformed YAML" in captured.err
    assert "line" in captured.err
    assert "Traceback" not in captured.err


def test_generate_command_rejects_duplicate_paths_before_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "dup.yaml"
    spec.write_text(
        "version: '1.0'\n"
        "repo:\n"
        "  name: demo\n"
        "  files: []\n"
        "sections:\n"
        "  - path: docs/00-overview\n"
        "    files:\n"
        "      - path: kaidf.md\n"
        "        inline: 'a'\n"
        "      - path: kaidf.md\n"
        "        inline: 'b'\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    with pytest.raises(SystemExit) as excinfo:
        main(["generate", str(spec), "--out", str(out_dir)])

    assert excinfo.value.code == 2
    assert "Duplicate output path 'docs/00-overview/kaidf.md'" in capsys.readouterr().err
    assert not out_dir.exists()
