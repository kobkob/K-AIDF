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
    assert (target / "docs/00-overview/manifesto.md").exists()
    assert (target / "docs/00-overview/best-practices.md").exists()
    assert (target / "docs/00-overview/governance.md").exists()
    assert (target / "docs/00-overview/maturity.md").exists()
    assert (target / "docs/00-overview/implementation.md").exists()
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


def test_generate_emits_front_matter_with_defaults_and_overrides(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {
            "name": "demo",
            "metadata_defaults": {"visibility": "internal", "status": "active"},
            "files": [],
        },
        "sections": [
            {
                "path": "docs/01-intent-constraints",
                "metadata_defaults": {"phase": "01-intent-constraints"},
                "files": [
                    {
                        "path": "prompt.md",
                        "inline": "# Prompt\n",
                        "front_matter": {
                            "id": "docs/01-intent-constraints/prompt.md",
                            "title": "Prompt",
                            "document_class": "prompt-doc",
                        },
                    }
                ],
            }
        ],
    }

    target = generate(spec, tmp_path, GenerateOptions(force=False))
    content = (target / "docs/01-intent-constraints/prompt.md").read_text(encoding="utf-8")

    assert content.startswith(
        "---\n"
        "id: docs/01-intent-constraints/prompt.md\n"
        "title: Prompt\n"
        "document_class: prompt-doc\n"
        "phase: 01-intent-constraints\n"
        "visibility: internal\n"
        "status: active\n"
        "---\n\n"
    )


def test_generate_requires_complete_front_matter_after_merging_defaults(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {"name": "demo", "files": []},
        "sections": [
            {
                "path": "docs/00-overview",
                "files": [
                    {
                        "path": "kaidf.md",
                        "inline": "# K-AIDF\n",
                        "front_matter": {
                            "id": "docs/00-overview/kaidf.md",
                            "title": "K-AIDF",
                        },
                    }
                ],
            }
        ],
    }

    with pytest.raises(GenerationError, match="Missing front matter fields"):
        generate(spec, tmp_path, GenerateOptions(force=False))


def test_generate_rejects_front_matter_for_non_markdown_files(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {
            "name": "demo",
            "files": [
                {
                    "path": "data.csv",
                    "inline": "a,b\n1,2\n",
                    "front_matter": {
                        "id": "data.csv",
                        "title": "Data",
                        "document_class": "template-doc",
                        "phase": "root",
                        "visibility": "internal",
                        "status": "active",
                    },
                }
            ],
        },
        "sections": [],
    }

    with pytest.raises(GenerationError, match="Front matter is only supported for markdown files"):
        generate(spec, tmp_path, GenerateOptions(force=False))


def test_generate_rejects_duplicate_front_matter_blocks(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {
            "name": "demo",
            "files": [
                {
                    "path": "prompt.md",
                    "inline": "---\nlegacy: true\n---\n# Prompt\n",
                    "front_matter": {
                        "id": "prompt.md",
                        "title": "Prompt",
                        "document_class": "prompt-doc",
                        "phase": "root",
                        "visibility": "internal",
                        "status": "active",
                    },
                }
            ],
        },
        "sections": [],
    }

    with pytest.raises(GenerationError, match="Content already contains front matter"):
        generate(spec, tmp_path, GenerateOptions(force=False))


def test_template_library_exposes_expected_key() -> None:
    keys = list_library_keys()

    assert "root/README.md" in keys
    assert load_template_by_key("root/README.md")
