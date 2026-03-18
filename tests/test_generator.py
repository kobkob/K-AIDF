from pathlib import Path

import pytest

from kaidf_gen.errors import GenerationError, TemplateNotFoundError, UnsafePathError
from kaidf_gen.generator import GenerateOptions, generate
from kaidf_gen.loader import load_yaml
from kaidf_gen.template_loader import list_library_keys, load_template_by_key


def test_generate_default_spec_writes_expected_files(tmp_path: Path) -> None:
    spec = load_yaml("specs/kaidf.default.yaml")

    target = generate(spec, tmp_path / "out", GenerateOptions(force=False))

    assert target == tmp_path / "out" / "kobkob-kaidf"
    assert (target / "README.md").exists()
    assert (target / "docs/00-overview/kaidf.md").exists()
    assert (target / "docs/01-intent-constraints/exit-criteria.md").read_text(encoding="utf-8").startswith(
        "# Exit Criteria"
    )


def test_generate_rejects_non_empty_output_without_force(tmp_path: Path) -> None:
    spec = load_yaml("specs/kaidf.default.yaml")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(GenerationError, match="Output directory is not empty"):
        generate(spec, out_dir, GenerateOptions(force=False))


def test_generate_allows_non_empty_output_with_force(tmp_path: Path) -> None:
    spec = load_yaml("specs/kaidf.default.yaml")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "keep.txt").write_text("keep", encoding="utf-8")

    target = generate(spec, out_dir, GenerateOptions(force=True))

    assert target == out_dir / "kobkob-kaidf"
    assert (target / "README.md").exists()


def test_generate_rejects_unsafe_paths(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {"name": "demo", "files": [{"path": "../escape.txt", "inline": "x"}]},
        "sections": [],
    }

    with pytest.raises(UnsafePathError, match="Unsafe path"):
        generate(spec, tmp_path, GenerateOptions(force=False))


def test_generate_raises_for_missing_template_key(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {"name": "demo", "files": [{"path": "README.md", "content": "library:nope.md"}]},
        "sections": [],
    }

    with pytest.raises(TemplateNotFoundError, match="Template key not found"):
        generate(spec, tmp_path, GenerateOptions(force=False))


def test_generate_stringifies_inline_content(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {"name": "demo", "files": [{"path": "data.txt", "inline": {"a": 1}}]},
        "sections": [],
    }

    target = generate(spec, tmp_path, GenerateOptions(force=False))

    assert (target / "data.txt").read_text(encoding="utf-8") == "{'a': 1}"


def test_template_library_exposes_expected_key() -> None:
    keys = list_library_keys()

    assert "root/README.md" in keys
    assert load_template_by_key("root/README.md")
