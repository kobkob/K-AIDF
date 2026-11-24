from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agent_aidf.artifacts import (
    MAX_REPAIR_ATTEMPTS,
    document_problems,
    grounding_block,
    repair_draft,
    template_sections,
)
from agent_aidf.mentor import _phase_ready_for_acceptance
from agent_aidf.repo import Document
from agent_aidf.tools import ProposedAction

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


# --- document checks ----------------------------------------------------------------------------


def test_a_complete_draft_has_no_problems(repo: Path) -> None:
    assert (
        document_problems(
            "docs/01_intent_constraints/ICB.md", VALID_ICB, repo, "01_intent_constraints"
        )
        == []
    )


def test_missing_front_matter_is_reported_by_field(repo: Path) -> None:
    text = VALID_ICB.replace("id: icb-onboarding\n", "").replace("status: draft\n", "")

    problems = document_problems(
        "docs/01_intent_constraints/ICB.md", text, repo, "01_intent_constraints"
    )

    assert any("Front Matter is missing: id, status" in problem for problem in problems)


def test_a_draft_without_any_front_matter_is_rejected(repo: Path) -> None:
    problems = document_problems(
        "docs/01_intent_constraints/ICB.md", "# Plain draft\n", repo, "01_intent_constraints"
    )

    assert any("missing" in problem for problem in problems)


def test_unknown_visibility_is_reported(repo: Path) -> None:
    text = VALID_ICB.replace("visibility: internal", "visibility: everyone")

    problems = document_problems(
        "docs/01_intent_constraints/ICB.md", text, repo, "01_intent_constraints"
    )

    assert any("visibility 'everyone'" in problem for problem in problems)


def test_a_missing_template_section_is_reported(repo: Path) -> None:
    text = VALID_ICB.replace("## Constraints\nLocal-first.\n", "")

    problems = document_problems(
        "docs/01_intent_constraints/ICB.md", text, repo, "01_intent_constraints"
    )

    assert problems == ["missing template section(s): Constraints"]


def test_an_echo_of_the_template_is_reported(repo: Path) -> None:
    front = VALID_ICB.split("---\n", 2)[1]
    echo = f"---\n{front}---\n{ICB_TEMPLATE}"

    problems = document_problems(
        "docs/01_intent_constraints/ICB.md", echo, repo, "01_intent_constraints"
    )

    assert any("echoes the template" in problem for problem in problems)


def test_a_credential_is_reported_by_kind_and_never_by_value(repo: Path) -> None:
    text = VALID_ICB.replace("Local-first.", f"Use key {FAKE_KEY} for the model.")

    problems = document_problems(
        "docs/01_intent_constraints/ICB.md", text, repo, "01_intent_constraints"
    )

    assert any("contains a credential" in problem for problem in problems)
    assert all(FAKE_KEY not in problem for problem in problems)


def test_a_draft_may_not_overwrite_a_canonical_template(repo: Path) -> None:
    problems = document_problems(
        "docs/01_intent_constraints/templates/ICB.md", VALID_ICB, repo, "01_intent_constraints"
    )

    assert any("must not overwrite a canonical template" in problem for problem in problems)


def test_invalid_json_and_yaml_are_reported_and_valid_ones_pass(tmp_path: Path) -> None:
    assert document_problems("data/x.json", "{not json", tmp_path) != []
    assert document_problems("data/x.json", '{"risk": "low"}', tmp_path) == []
    assert document_problems("data/x.yaml", "key: [unclosed", tmp_path) != []
    assert document_problems("data/x.yaml", "key: value\n", tmp_path) == []


# --- self-repair --------------------------------------------------------------------------------


def _draft(content: str = VALID_ICB) -> ProposedAction:
    return ProposedAction(
        kind="write_file", path="docs/01_intent_constraints/ICB.md", content=content
    )


def _repair_block(content: str) -> str:
    import json

    payload = {
        "action": "write_file",
        "path": "docs/01_intent_constraints/ICB.md",
        "content": content,
    }
    return f"Corrected.\n<<<KOB_ACTION\n{json.dumps(payload)}\nKOB_ACTION>>>"


def test_a_passing_draft_needs_no_repair(repo: Path) -> None:
    calls: list[str] = []

    outcome = repair_draft(
        repo, _draft(), ask=lambda p: calls.append(p) or "", phase_dir="01_intent_constraints"
    )

    assert outcome.attempts == 0
    assert outcome.action is not None
    assert calls == []


def test_an_invalid_draft_is_repaired_on_the_next_attempt(repo: Path) -> None:
    broken = VALID_ICB.replace("## Constraints\nLocal-first.\n", "")
    replies = [_repair_block(VALID_ICB)]
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return replies.pop(0)

    outcome = repair_draft(repo, _draft(broken), ask=ask, phase_dir="01_intent_constraints")

    assert outcome.attempts == 1
    assert outcome.action is not None
    assert outcome.action.content == VALID_ICB
    # The model is told the concrete problem, not just that something was wrong.
    assert "missing template section(s): Constraints" in prompts[0]


def test_repair_gives_up_after_the_bounded_attempts(repo: Path) -> None:
    broken = "# Still not a brief\n"
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return _repair_block(broken)

    outcome = repair_draft(repo, _draft(broken), ask=ask, phase_dir="01_intent_constraints")

    assert outcome.action is None
    assert outcome.attempts == MAX_REPAIR_ATTEMPTS
    assert len(prompts) == MAX_REPAIR_ATTEMPTS
    assert outcome.problems


def test_a_reply_that_is_not_a_repair_counts_as_a_failed_attempt(repo: Path) -> None:
    broken = "# Still not a brief\n"

    outcome = repair_draft(
        repo,
        _draft(broken),
        ask=lambda _p: "I cannot help with that.",
        phase_dir="01_intent_constraints",
    )

    assert outcome.action is None
    assert outcome.attempts == MAX_REPAIR_ATTEMPTS


def test_a_repair_for_a_different_path_is_not_accepted(repo: Path) -> None:
    import json

    broken = "# Still not a brief\n"
    other = {"action": "write_file", "path": "docs/elsewhere.md", "content": VALID_ICB}
    reply = f"<<<KOB_ACTION\n{json.dumps(other)}\nKOB_ACTION>>>"

    outcome = repair_draft(
        repo, _draft(broken), ask=lambda _p: reply, phase_dir="01_intent_constraints"
    )

    assert outcome.action is None


# --- acceptance gate ----------------------------------------------------------------------------


def _document(path: str, **overrides) -> Document:
    base = Document(
        id="icb-onboarding",
        path=path,
        title="Intent & Constraint Brief",
        document_class="icb",
        phase="01_intent_constraints",
        visibility="internal",
        status="draft",
        doctrine_category="",
        canonical_doctrine=False,
        variant_domain=None,
        pack=None,
        maturity_level=None,
        assessment_type=None,
        ethical_domain=None,
        control_type=None,
        risk_type=None,
        content="",
        body=VALID_ICB.split("---\n", 2)[2].lstrip("\n"),
    )
    return replace(base, **overrides)


def test_acceptance_needs_documents_that_pass_the_checks(repo: Path) -> None:
    good = _document("docs/01_intent_constraints/ICB.md")
    assert _phase_ready_for_acceptance([good], "01_intent_constraints", repo) is True

    missing_section = _document(
        "docs/01_intent_constraints/ICB.md",
        body=VALID_ICB.split("---\n", 2)[2]
        .lstrip("\n")
        .replace("## Constraints\nLocal-first.\n", ""),
    )
    assert _phase_ready_for_acceptance([missing_section], "01_intent_constraints", repo) is False


def test_acceptance_refuses_a_document_with_a_bad_visibility(repo: Path) -> None:
    bad = _document("docs/01_intent_constraints/ICB.md", visibility="everyone")

    assert _phase_ready_for_acceptance([bad], "01_intent_constraints", repo) is False
