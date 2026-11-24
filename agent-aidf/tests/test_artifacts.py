from __future__ import annotations

from pathlib import Path

import pytest

from agent_aidf.artifacts import (
    grounding_block,
    template_sections,
)

# A realistic-looking key that the audit's credential patterns match and that is not an example.
FAKE_KEY = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4"

ICB_TEMPLATE = """# Intent & Constraint Brief (ICB)

## Problem Statement

## Business Objective

## Non-Negotiables

## Constraints
"""

VALID_ICB = """---
id: icb-onboarding
title: Intent & Constraint Brief
document_class: icb
phase: 01_intent_constraints
visibility: internal
status: draft
---
# Intent & Constraint Brief (ICB)

## Problem Statement
New hires take too long to become productive.

## Business Objective
Shorten the time to the first merged change.

## Non-Negotiables
A human approves every change.

## Constraints
Local-first.
"""


def _phase(repo: Path, phase_dir: str = "01_intent_constraints") -> Path:
    folder = repo / "docs" / phase_dir / "templates"
    folder.mkdir(parents=True)
    (folder / "ICB.md").write_text(ICB_TEMPLATE, encoding="utf-8")
    return repo


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _phase(tmp_path / ".kaidf")


# --- grounding ----------------------------------------------------------------------------------


def test_grounding_carries_template_sections_front_matter_and_criteria(repo: Path) -> None:
    block = grounding_block(repo, "01_intent_constraints")

    assert "--- template: ICB.md ---" in block
    assert "## Problem Statement" in block
    assert "Front Matter every document must start with" in block
    assert "document_class: <template name, lowercase>" in block
    assert "phase: 01_intent_constraints" in block
    assert "Criteria the audit applies" in block
    assert "Never write a credential" in block


def test_grounding_is_empty_when_the_phase_has_no_templates(tmp_path: Path) -> None:
    assert grounding_block(tmp_path, "01_intent_constraints") == ""


def test_grounding_finds_a_dashed_scaffold_directory(tmp_path: Path) -> None:
    folder = tmp_path / "docs" / "01-intent-constraints" / "templates"
    folder.mkdir(parents=True)
    (folder / "ICB.md").write_text(ICB_TEMPLATE, encoding="utf-8")

    assert "## Problem Statement" in grounding_block(tmp_path, "01_intent_constraints")


def test_grounding_includes_a_golden_example_only_when_the_project_ships_one(repo: Path) -> None:
    assert "Golden example" not in grounding_block(repo, "01_intent_constraints")

    examples = repo / "docs" / "01_intent_constraints" / "examples"
    examples.mkdir(parents=True)
    (examples / "accepted-icb.md").write_text(VALID_ICB, encoding="utf-8")

    block = grounding_block(repo, "01_intent_constraints")
    assert "Golden example, accepted-icb.md" in block
    assert "New hires take too long" in block


def test_grounding_stays_within_its_budget(repo: Path) -> None:
    templates = repo / "docs" / "01_intent_constraints" / "templates"
    (templates / "Huge.md").write_text("## Section\n" + "x" * 50_000, encoding="utf-8")

    block = grounding_block(repo, "01_intent_constraints", budget=3000)

    assert len(block) <= 3000
    assert "truncated" in block


def test_template_sections_are_the_level_two_headings() -> None:
    assert template_sections(ICB_TEMPLATE) == [
        "Problem Statement",
        "Business Objective",
        "Non-Negotiables",
        "Constraints",
    ]
