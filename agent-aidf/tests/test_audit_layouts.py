"""The audit against the layouts `kob init` and the generator actually produce.

The scaffold is generated in-process from the sibling kobkob-kaidf-generator checkout, so these
tests prove that the engine and the generator agree on where every artifact lives: a project set
up with `kob init` (the generated root moved to <project>/.kaidf/) and a generated repository
audited directly (what mcp-aidf audits through AIDF_REPO_ROOT).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from agent_aidf.audit import SCAFFOLD_DIRNAME, failed_checks, run_audit
from agent_aidf.project import SCAFFOLD_SPEC_PATH

GENERATOR_REPO = Path(__file__).resolve().parents[2] / "kobkob-kaidf-generator"
GENERATOR_SRC = GENERATOR_REPO / "src"
GENERATOR_SPEC = GENERATOR_REPO / "specs/kaidf.default.yaml"

MENTOR_STATE = '{"phase": "01"}'
CI_WORKFLOW = "jobs:\n  test:\n    steps:\n      - run: pytest\n"

# Checks the scaffold alone satisfies (mentor-state once `kob mentor` has written its state).
SCAFFOLD_OWNED = (
    "kaidf-scaffold",
    "mentor-state",
    "specs-parse",
    "front-matter-v2",
    "skills-manifest",
)

# Check id -> the generated placeholder it reads, relative to the scaffold.
PLACEHOLDER_CHECKS = {
    "pii-masking-rules": "policy/pii-masking-rules.yaml",
    "hitl-config": "policy/hitl-config.yaml",
    "budget-caps": "policy/budget.yaml",
    "local-fallback": "policy/budget.yaml",
    "risk-assessment": "docs/20-ethical-model/risk-assessment.json",
    "explicability-schema": "docs/20-ethical-model/explicability-schema.json",
    "dataset-audit": "data/manifests/dataset-audit.yaml",
}

# What a team writes once it has filled the placeholders in.
FILLED_IN = {
    "policy/pii-masking-rules.yaml": "version: '1.0'\nrules:\n  - field: email\n    mask: hash\n",
    "policy/hitl-config.yaml": "review_required:\n  - decision: publish\n    reviewer_role: dpo\n",
    "policy/budget.yaml": "max_tokens: 4096\nrequest_timeout_seconds: 30\nlocal_fallback: true\n",
    "docs/20-ethical-model/risk-assessment.json": '{"risk_class": "minimal", "risks": []}',
    "docs/20-ethical-model/explicability-schema.json": '{"decision_types": []}',
    "data/manifests/dataset-audit.yaml": "datasets:\n  - id: demo\n    audit_status: passed\n",
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _check(result, check_id: str):
    for dimension in result.dimensions:
        for check in dimension.checks:
            if check.id == check_id:
                return check
    raise AssertionError(check_id)


def _import_generator():
    """Import kaidf_gen from the sibling checkout, not from any installed copy."""
    for name in [name for name in sys.modules if name.split(".")[0] == "kaidf_gen"]:
        del sys.modules[name]
    sys.path.insert(0, str(GENERATOR_SRC))
    try:
        import kaidf_gen
        from kaidf_gen.generator import GenerateOptions, generate
        from kaidf_gen.loader import load_yaml
    finally:
        sys.path.remove(str(GENERATOR_SRC))
    origin = Path(kaidf_gen.__file__).resolve()
    assert origin.is_relative_to(GENERATOR_SRC), f"kaidf_gen was imported from {origin}"
    return load_yaml, generate, GenerateOptions


@pytest.fixture(scope="module")
def generated_scaffold(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The default scaffold, generated once by the sibling generator checkout."""
    if not GENERATOR_SRC.is_dir() or not GENERATOR_SPEC.is_file():
        pytest.skip(f"sibling kobkob-kaidf-generator checkout not found at {GENERATOR_REPO}")
    load_yaml, generate, GenerateOptions = _import_generator()
    out_dir = tmp_path_factory.mktemp("generated")
    return generate(load_yaml(GENERATOR_SPEC), out_dir, GenerateOptions(force=False))


@pytest.fixture
def project(generated_scaffold: Path, tmp_path: Path) -> Path:
    """A tree shaped like `kob init` leaves it: <project>/.kaidf is the generated root, plus the
    spec it was generated from."""
    root = tmp_path / "project"
    scaffold = root / SCAFFOLD_DIRNAME
    shutil.copytree(generated_scaffold, scaffold)
    (scaffold / SCAFFOLD_SPEC_PATH).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(GENERATOR_SPEC, scaffold / SCAFFOLD_SPEC_PATH)
    return root


@pytest.fixture
def standalone(generated_scaffold: Path, tmp_path: Path) -> Path:
    """The generated repository itself, audited directly."""
    root = tmp_path / "kobkob-kaidf"
    shutil.copytree(generated_scaffold, root)
    return root


# --- kob init layout ------------------------------------------------------------------------------


def test_fresh_kob_init_project_passes_every_scaffold_owned_check(project: Path) -> None:
    _write(project / SCAFFOLD_DIRNAME / "mentor-workflow.json", MENTOR_STATE)

    result = run_audit(project)

    assert result.scaffold_path == str(project / SCAFFOLD_DIRNAME)
    for check_id in SCAFFOLD_OWNED:
        check = _check(result, check_id)
        assert check.points == check.max_points, (check_id, check.detail)
    assert _check(result, "kaidf-scaffold").detail == ".kaidf/ has README.md and docs/"
    assert _check(result, "specs-parse").detail == "1 of 1 YAML specs parse as mappings"
    assert _check(result, "skills-manifest").detail == (
        "1 skill(s) registered in .kaidf/data/manifests/skills.yaml"
    )
    assert _check(result, "no-credentials").points == 10, _check(result, "no-credentials").detail


def test_project_markdown_outside_the_scaffold_is_not_scanned_for_front_matter(
    project: Path,
) -> None:
    # The project's own documentation is not a K-AIDF document: it must not lower the score.
    _write(project / "README.md", "# My application\n")
    _write(project / "docs/architecture.md", "# Architecture\n")

    check = _check(run_audit(project), "front-matter-v2")

    assert check.points == check.max_points, check.detail
    assert "Markdown documents complete" in check.detail


def test_generated_placeholders_score_zero_and_ask_to_be_filled_in(project: Path) -> None:
    result = run_audit(project)

    for check_id, relative in PLACEHOLDER_CHECKS.items():
        check = _check(result, check_id)
        shown = f"{SCAFFOLD_DIRNAME}/{relative}"
        assert check.points == 0, check_id
        assert check.detail == f"{shown} is still the generator placeholder"
        assert check.remediation.startswith(f"Fill in {shown}"), check.remediation
        assert "Create " not in check.remediation and "Add " not in check.remediation


def test_only_placeholders_mentor_state_and_ci_fail_on_a_fresh_project(project: Path) -> None:
    # Nothing fails because of where a file is: the only open items on a fresh `kob init` project
    # are the placeholders to fill in, the mentor state `kob mentor` writes, and the CI workflow
    # the project itself owns.
    result = run_audit(project)

    failing = {check.id for _, check in failed_checks(result)}

    assert failing == set(PLACEHOLDER_CHECKS) | {"mentor-state", "ci-workflows", "blocking-gates"}


def test_kob_init_project_reaches_100_once_the_placeholders_are_filled_in(project: Path) -> None:
    scaffold = project / SCAFFOLD_DIRNAME
    _write(scaffold / "mentor-workflow.json", MENTOR_STATE)
    for relative, content in FILLED_IN.items():
        _write(scaffold / relative, content)
    _write(project / ".github/workflows/ci.yml", CI_WORKFLOW)

    result = run_audit(project)

    assert result.score == 100, [(check.id, check.detail) for _, check in failed_checks(result)]
    assert result.tier == "Platinum"


# --- standalone generated repository --------------------------------------------------------------


def test_standalone_generated_repository_resolves_scaffold_checks_at_its_root(
    standalone: Path,
) -> None:
    _write(standalone / "mentor-workflow.json", MENTOR_STATE)
    _write(standalone / "specs/kaidf.yaml", GENERATOR_SPEC.read_text(encoding="utf-8"))

    result = run_audit(standalone)

    assert result.scaffold_path == str(standalone)
    for check_id in SCAFFOLD_OWNED:
        check = _check(result, check_id)
        assert check.points == check.max_points, (check_id, check.detail)
    assert "standalone scaffold" in _check(result, "kaidf-scaffold").detail
    assert _check(result, "skills-manifest").detail == (
        "1 skill(s) registered in data/manifests/skills.yaml"
    )
    for check_id, relative in PLACEHOLDER_CHECKS.items():
        check = _check(result, check_id)
        assert check.points == 0, check_id
        assert check.remediation.startswith(f"Fill in {relative}"), check.remediation
        assert SCAFFOLD_DIRNAME not in check.remediation


def test_standalone_repository_is_not_told_to_run_kob_mentor(standalone: Path) -> None:
    # `kob mentor` refuses to run without a .kaidf/ project, so the standalone wording points
    # at the owning project instead.
    check = _check(run_audit(standalone), "mentor-state")

    assert check.points == 0
    assert "kob mentor" not in check.remediation
    assert check.remediation == (
        "Audit this repository from the project that contains it as .kaidf/, or write "
        "mentor-workflow.json as a valid JSON object."
    )


def test_standalone_generated_repository_reaches_100_once_filled_in(standalone: Path) -> None:
    _write(standalone / "mentor-workflow.json", MENTOR_STATE)
    _write(standalone / "specs/kaidf.yaml", "version: '1.0'\n")
    for relative, content in FILLED_IN.items():
        _write(standalone / relative, content)
    _write(standalone / ".github/workflows/ci.yml", CI_WORKFLOW)

    result = run_audit(standalone)

    assert result.score == 100, [(check.id, check.detail) for _, check in failed_checks(result)]
