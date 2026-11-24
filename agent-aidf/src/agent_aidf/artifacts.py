"""Grounding and validation for the documents the mentor drafts.

Three things live here, and all of them use the same rules as the audit (document_rules.py):

- ``grounding_block``: the context the model gets for a phase: the canonical template of each
  deliverable, its required sections, the Front Matter it must emit, a golden example when the
  project has one, and the criteria the audit will apply.
- ``document_problems``: the deterministic checks a draft must pass before it is offered to the
  operator or accepted: front matter, visibility, credentials, template sections, and echoes of
  the template.
- ``repair_draft``: a bounded self-repair loop. A failing draft goes back to the model with the
  concrete problems, up to ``MAX_REPAIR_ATTEMPTS`` times, and is only returned once it passes.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from .document_rules import CRITERIA_SUMMARY

MAX_REPAIR_ATTEMPTS = 2
GROUNDING_BUDGET_CHARS = 6000
_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_TRUNCATED = "\n[... truncated to fit the context budget]"


def _phase_dir_candidates(phase_dir: str) -> list[str]:
    """The mentor writes `01_intent_constraints`; generated scaffolds use dashes. Look at both."""
    return list(dict.fromkeys([phase_dir, phase_dir.replace("_", "-")]))


def phase_templates(repo_root: Path, phase_dir: str) -> list[tuple[Path, str]]:
    """Every Markdown template of a phase, as (path, text), in a stable order."""
    found: list[tuple[Path, str]] = []
    for candidate in _phase_dir_candidates(phase_dir):
        folder = repo_root / "docs" / candidate / "templates"
        if folder.is_dir():
            for path in sorted(folder.glob("*.md")):
                found.append((path, path.read_text(encoding="utf-8", errors="replace")))
            break
    return found


def phase_examples(repo_root: Path, phase_dir: str) -> list[tuple[Path, str]]:
    """Golden examples a project ships for a phase (docs/<phase>/examples/*.md), if any."""
    for candidate in _phase_dir_candidates(phase_dir):
        folder = repo_root / "docs" / candidate / "examples"
        if folder.is_dir():
            return [
                (path, path.read_text(encoding="utf-8", errors="replace"))
                for path in sorted(folder.glob("*.md"))
            ]
    return []


def template_sections(text: str) -> list[str]:
    """The `##` section titles of a template, in order."""
    return [match.group(1).strip() for match in _SECTION.finditer(text)]


def _template_for(
    relative: str, templates: list[tuple[Path, str]], document_class: str
) -> str | None:
    """The template a document is drafted from: same file name, or same document class."""
    name = PurePosixPath(relative).name.lower()
    wanted = document_class.lower()
    for path, text in templates:
        if path.name.lower() == name or path.stem.lower() == wanted:
            return text
    return None


def _truncate(text: str, budget: int) -> str:
    if len(text) <= budget:
        return text
    return text[: max(0, budget - len(_TRUNCATED))] + _TRUNCATED


def grounding_block(
    repo_root: Path, phase_dir: str, *, budget: int = GROUNDING_BUDGET_CHARS
) -> str:
    """The grounding context for one phase, within `budget` characters. Empty when none applies."""
    templates = phase_templates(repo_root, phase_dir)
    examples = phase_examples(repo_root, phase_dir)
    if not templates and not examples:
        return ""

    # The template and the criteria come first: they are what the draft must meet. The example,
    # when there is one, takes the rest of the budget.
    lines = [
        "Grounding for this phase. Draft every deliverable from its canonical template below and "
        "meet the criteria. Do not repeat this block back to the user.",
    ]
    lines.append("Canonical templates (each `##` section must appear, with real content):")
    per_template = max(600, (budget * 2 // 3) // max(1, len(templates)))
    for path, text in templates:
        lines.append(f"--- template: {path.name} ---")
        lines.append(_truncate(text.strip(), per_template))
    lines.append("Front Matter every document must start with:")
    lines.extend(
        [
            "---",
            "id: <stable-kebab-case-id>",
            "title: <title>",
            "document_class: <template name, lowercase>",
            f"phase: {phase_dir}",
            "visibility: internal",
            "status: draft",
            "---",
        ]
    )
    lines.append("Criteria the audit applies to these documents:")
    lines.extend(f"- {rule}" for rule in CRITERIA_SUMMARY)
    if examples:
        left = max(200, budget - len("\n".join(lines)) - 200)
        path, text = examples[0]
        lines.append(f"Golden example, {path.name} (same class of document, accepted):")
        lines.append(_truncate(text.strip(), left))
    return _truncate("\n".join(lines), budget)
