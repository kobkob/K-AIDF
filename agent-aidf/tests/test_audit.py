from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent_aidf import audit
from agent_aidf.audit import DIMENSION_SPECS, classify_tier, run_audit

FRONT_MATTER = (
    "---\n"
    "id: docs/doc.md\n"
    "title: Doc\n"
    "document_class: core-doc\n"
    "phase: 00-overview\n"
    "visibility: internal\n"
    "status: active\n"
    "---\n\n# Doc\n"
)
GOOD_BUDGET = "max_tokens: 4096\nrequest_timeout_seconds: 30\nlocal_fallback: true\n"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _complete_repo(root: Path) -> Path:
    _write(root / ".kaidf/README.md", FRONT_MATTER)
    _write(root / ".kaidf/docs/00-overview/kaidf.md", FRONT_MATTER)
    _write(root / ".kaidf/mentor-workflow.json", '{"phase": "01"}')
    _write(root / ".kaidf/policy/pii-masking-rules.yaml", "rules:\n  - email\n")
    _write(root / ".kaidf/policy/hitl-config.yaml", "reviewer: human\n")
    _write(root / ".kaidf/policy/budget.yaml", GOOD_BUDGET)
    _write(root / "specs/kaidf.yaml", "version: '1.0'\nrepo:\n  name: demo\n")
    _write(root / "docs/20-ethical-model/risk-assessment.json", '{"risk": "low"}')
    _write(root / "docs/20-ethical-model/explicability-schema.json", '{"fields": []}')
    _write(root / "data/manifests/dataset-audit.yaml", "dataset: demo\n")
    _write(root / ".github/workflows/ci.yml", "jobs:\n  test:\n    steps:\n      - run: pytest\n")
    return root


def _scores(result) -> dict[str, int]:
    return {d.id: d.points for d in result.dimensions}


def _check(result, check_id: str):
    for dimension in result.dimensions:
        for check in dimension.checks:
            if check.id == check_id:
                return check
    raise AssertionError(check_id)


def test_complete_repository_scores_100_and_is_platinum(tmp_path: Path) -> None:
    result = run_audit(_complete_repo(tmp_path))

    assert result.score == 100
    assert result.tier == "Platinum"
    assert all(points == 20 for points in _scores(result).values())


def test_empty_directory_scores_zero_and_is_unrated(tmp_path: Path) -> None:
    result = run_audit(tmp_path)

    assert result.score == 0
    assert result.tier == "Non-Compliant / Unrated"


def test_no_credentials_check_needs_files_to_inspect(tmp_path: Path) -> None:
    assert _check(run_audit(tmp_path), "no-credentials").points == 0

    _write(tmp_path / "README.md", "# demo\n")
    assert _check(run_audit(tmp_path), "no-credentials").points == 10


def test_dimension_specs_add_up_to_twenty_points_each_and_one_hundred_in_total() -> None:
    maxima = [sum(max_points for _, _, max_points, _ in checks) for _, _, checks in DIMENSION_SPECS]

    assert maxima == [20, 20, 20, 20, 20]
    assert sum(maxima) == 100


@pytest.mark.parametrize(
    ("score", "tier"),
    [
        (0, "Non-Compliant / Unrated"),
        (59, "Non-Compliant / Unrated"),
        (60, "Silver"),
        (74, "Silver"),
        (75, "Gold"),
        (89, "Gold"),
        (90, "Platinum"),
        (100, "Platinum"),
    ],
)
def test_tier_boundaries(score: int, tier: str) -> None:
    assert classify_tier(score) == tier


def test_run_audit_rejects_a_missing_repository(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        run_audit(tmp_path / "missing")


def test_secret_assignment_fails_the_credential_check(tmp_path: Path) -> None:
    root = _complete_repo(tmp_path)
    _write(root / "config.py", 'api_key = "abcdefghijklmnop1234"\n')

    check = _check(run_audit(root), "no-credentials")

    assert check.points == 0
    assert "config.py: hard-coded credential assignment" in check.detail


@pytest.mark.parametrize(
    ("content", "label"),
    [
        ("token = sk-" + "a" * 24 + "\n", "OpenAI-style secret key"),
        ("key = AKIA" + "ABCDEFGHIJKLMNOP" + "\n", "AWS access key id"),
        ("key = AIza" + "x" * 35 + "\n", "Google API key"),
        ("-----BEGIN RSA PRIVATE KEY-----\n", "private key block"),
    ],
)
def test_known_credential_shapes_are_reported(tmp_path: Path, content: str, label: str) -> None:
    _write(tmp_path / "notes.txt", content)

    check = _check(run_audit(tmp_path), "no-credentials")

    assert check.points == 0
    assert label in check.detail


def test_findings_list_is_truncated_after_five_entries(tmp_path: Path) -> None:
    for index in range(7):
        _write(tmp_path / f"leak{index}.txt", 'password = "abcdefghijklmnop1234"\n')

    check = _check(run_audit(tmp_path), "no-credentials")

    assert check.detail.endswith(" ...")
    assert check.detail.count("leak") == 5


def test_binary_and_oversized_files_are_not_scanned(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "blob.bin").write_bytes(b"\0" + b'password = "abcdefghijklmnop1234"')
    _write(tmp_path / "big.txt", 'password = "abcdefghijklmnop1234"\n')
    monkeypatch.setattr(audit, "MAX_SCAN_BYTES", 10)

    check = _check(run_audit(tmp_path), "no-credentials")

    assert check.points == 10


def test_tracked_env_file_fails_but_example_and_untracked_files_do_not(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _write(tmp_path / ".env.example", "API_KEY=\n")
    _write(tmp_path / ".env", "API_KEY=local\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".env.example"], check=True)

    untracked = _check(run_audit(tmp_path), "no-credentials")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".env"], check=True)
    tracked = _check(run_audit(tmp_path), "no-credentials")

    assert untracked.points == 10
    assert tracked.points == 0
    assert ".env: environment file is tracked" in tracked.detail


def test_untracked_secret_is_ignored_in_a_git_repository(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _write(tmp_path / "README.md", "# demo\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    _write(tmp_path / "leak.py", 'api_key = "abcdefghijklmnop1234"\n')

    assert _check(run_audit(tmp_path), "no-credentials").points == 10


def test_pii_rules_must_be_a_non_empty_mapping(tmp_path: Path) -> None:
    rules = tmp_path / ".kaidf/policy/pii-masking-rules.yaml"
    for content in ["", "- just-a-list\n", "a: [unclosed\n"]:
        _write(rules, content)
        assert _check(run_audit(tmp_path), "pii-masking-rules").points == 0
    _write(rules, "email: mask\n")
    assert _check(run_audit(tmp_path), "pii-masking-rules").points == 10


def test_kaidf_scaffold_needs_readme_and_docs(tmp_path: Path) -> None:
    _write(tmp_path / ".kaidf/README.md", "# kaidf\n")
    assert _check(run_audit(tmp_path), "kaidf-scaffold").points == 0
    _write(tmp_path / ".kaidf/docs/index.md", "# docs\n")
    assert _check(run_audit(tmp_path), "kaidf-scaffold").points == 5


@pytest.mark.parametrize("content", ["not json", "[1, 2]", ""])
def test_mentor_state_must_be_a_json_object(tmp_path: Path, content: str) -> None:
    _write(tmp_path / ".kaidf/mentor-workflow.json", content)

    assert _check(run_audit(tmp_path), "mentor-state").points == 0


def test_mentor_state_valid_object_scores(tmp_path: Path) -> None:
    _write(tmp_path / ".kaidf/mentor-workflow.json", '{"phase": "01"}')

    assert _check(run_audit(tmp_path), "mentor-state").points == 5


def test_specs_score_is_the_fraction_that_parses(tmp_path: Path) -> None:
    assert _check(run_audit(tmp_path), "specs-parse").points == 0
    _write(tmp_path / "specs/good.yaml", "version: '1.0'\n")
    _write(tmp_path / "specs/bad.yml", "- a list\n")

    check = _check(run_audit(tmp_path), "specs-parse")

    assert check.points == 2
    assert check.detail == "1 of 2 YAML specs parse as mappings"


def test_front_matter_score_is_the_fraction_of_complete_documents(tmp_path: Path) -> None:
    assert _check(run_audit(tmp_path), "front-matter-v2").points == 0
    _write(tmp_path / "docs/a.md", FRONT_MATTER)
    _write(tmp_path / "docs/b.md", "# no front matter\n")
    (tmp_path / "docs/c.md").write_bytes(b"\0binary")
    _write(tmp_path / ".venv/lib/ignored.md", "# not counted\n")
    _write(tmp_path / "out-demo/ignored.md", "# not counted\n")

    check = _check(run_audit(tmp_path), "front-matter-v2")

    assert check.detail == "1 of 3 Markdown documents complete"
    assert check.points == 2


@pytest.mark.parametrize(
    ("relative", "check_id"),
    [
        ("docs/20-ethical-model/risk-assessment.json", "risk-assessment"),
        ("docs/20-ethical-model/explicability-schema.json", "explicability-schema"),
        (".kaidf/policy/hitl-config.yaml", "hitl-config"),
        ("data/manifests/dataset-audit.yaml", "dataset-audit"),
    ],
)
def test_regulatory_artifacts_must_exist_and_be_non_empty(
    tmp_path: Path, relative: str, check_id: str
) -> None:
    assert _check(run_audit(tmp_path), check_id).points == 0
    _write(tmp_path / relative, "")
    assert _check(run_audit(tmp_path), check_id).points == 0
    _write(tmp_path / relative, "present: true\n")
    assert _check(run_audit(tmp_path), check_id).points == 5


def test_ci_workflows_and_blocking_gates(tmp_path: Path) -> None:
    assert _check(run_audit(tmp_path), "ci-workflows").points == 0
    assert _check(run_audit(tmp_path), "blocking-gates").points == 0

    _write(tmp_path / ".github/workflows/ci.yml", "steps:\n  - run: pytest\n")
    assert _check(run_audit(tmp_path), "ci-workflows").points == 10
    assert _check(run_audit(tmp_path), "blocking-gates").points == 10

    _write(
        tmp_path / ".github/workflows/lint.yml",
        "steps:\n  - run: ruff\n    continue-on-error: true\n",
    )
    gate = _check(run_audit(tmp_path), "blocking-gates")
    assert gate.points == 0
    assert "lint.yml sets continue-on-error: true" in gate.detail


@pytest.mark.parametrize(
    "budget",
    [
        "max_tokens: 0\nrequest_timeout_seconds: 30\n",
        "max_tokens: true\nrequest_timeout_seconds: 30\n",
        "max_tokens: 100\nrequest_timeout_seconds: '30'\n",
        "max_tokens: 100\nrequest_timeout_seconds: true\n",
        "max_tokens: 100\n",
        "",
    ],
)
def test_budget_caps_require_positive_numbers(tmp_path: Path, budget: str) -> None:
    _write(tmp_path / ".kaidf/policy/budget.yaml", budget)

    assert _check(run_audit(tmp_path), "budget-caps").points == 0


def test_budget_caps_accept_positive_numbers(tmp_path: Path) -> None:
    _write(
        tmp_path / ".kaidf/policy/budget.yaml", "max_tokens: 4096\nrequest_timeout_seconds: 2.5\n"
    )

    assert _check(run_audit(tmp_path), "budget-caps").points == 10


def test_local_fallback_must_be_explicitly_true(tmp_path: Path) -> None:
    _write(tmp_path / ".kaidf/policy/budget.yaml", "local_fallback: false\n")
    assert _check(run_audit(tmp_path), "local-fallback").points == 0

    _write(tmp_path / ".kaidf/policy/budget.yaml", GOOD_BUDGET)
    assert _check(run_audit(tmp_path), "local-fallback").points == 10


def test_audit_result_exposes_repo_path_and_dimensions(tmp_path: Path) -> None:
    result = run_audit(_complete_repo(tmp_path))

    assert result.repo_path == str(tmp_path.resolve())
    assert [d.id for d in result.dimensions] == [
        "data-sovereignty",
        "methodology-as-code",
        "regulatory-compliance",
        "deterministic-guardrails",
        "cost-infrastructure-health",
    ]
