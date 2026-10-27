from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent_aidf import audit
from agent_aidf.audit import (
    DIMENSION_SPECS,
    SEVERITY_ORDER,
    classify_tier,
    failed_checks,
    has_critical_findings,
    render_audit_report,
    run_audit,
)
from agent_aidf.cli.main import _run_cli

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


SKILLS_FIXTURE_PATH = "data/manifests/skills.yaml"
VALID_SKILLS = (
    'version: "1.0"\n'
    "skills:\n"
    '  - id: "kaidf-audit"\n'
    '    command: "kob audit"\n'
    "    permissions:\n"
    '      filesystem: "read"\n'
)


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
    _write(root / SKILLS_FIXTURE_PATH, VALID_SKILLS)
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
    assert _check(run_audit(tmp_path), "kaidf-scaffold").points == 4


@pytest.mark.parametrize("content", ["not json", "[1, 2]", ""])
def test_mentor_state_must_be_a_json_object(tmp_path: Path, content: str) -> None:
    _write(tmp_path / ".kaidf/mentor-workflow.json", content)

    assert _check(run_audit(tmp_path), "mentor-state").points == 0


def test_mentor_state_valid_object_scores(tmp_path: Path) -> None:
    _write(tmp_path / ".kaidf/mentor-workflow.json", '{"phase": "01"}')

    assert _check(run_audit(tmp_path), "mentor-state").points == 4


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
    assert check.points == 1


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


def test_skills_manifest_must_be_a_valid_registry(tmp_path: Path) -> None:
    manifest = tmp_path / SKILLS_FIXTURE_PATH
    cases = {
        "missing": None,
        "empty file": "",
        "not a mapping": "- a list\n",
        "no version": "skills:\n  - id: a\n    command: x\n    permissions: {}\n",
        "no skills list": 'version: "1.0"\nskills: nope\n',
        "empty skills list": 'version: "1.0"\nskills: []\n',
        "entry not a mapping": 'version: "1.0"\nskills:\n  - just-text\n',
        "no id": 'version: "1.0"\nskills:\n  - command: x\n    permissions: {}\n',
        "blank id": 'version: "1.0"\nskills:\n  - id: " "\n    command: x\n    permissions: {}\n',
        "duplicate id": (
            'version: "1.0"\nskills:\n'
            "  - id: a\n    command: x\n    permissions: {}\n"
            "  - id: a\n    command: y\n    permissions: {}\n"
        ),
        "no command": 'version: "1.0"\nskills:\n  - id: a\n    permissions: {}\n',
        "no permissions": 'version: "1.0"\nskills:\n  - id: a\n    command: x\n',
    }
    for label, content in cases.items():
        if content is None:
            manifest.unlink(missing_ok=True)
        else:
            _write(manifest, content)
        check = _check(run_audit(tmp_path), "skills-manifest")
        assert check.points == 0, f"{label}: {check.detail}"

    _write(manifest, VALID_SKILLS)
    check = _check(run_audit(tmp_path), "skills-manifest")
    assert check.points == 4
    assert check.detail == "1 skill(s) registered in data/manifests/skills.yaml"


def test_every_check_has_a_remediation_and_failing_results_carry_it(tmp_path: Path) -> None:
    result = run_audit(tmp_path)

    for dimension in result.dimensions:
        for check in dimension.checks:
            assert check.remediation, check.id
    failing = _check(result, "skills-manifest")
    assert "skills list" in failing.remediation


def test_json_export_includes_remediations(tmp_path: Path) -> None:
    payload = run_audit(tmp_path).to_dict()

    check = payload["dimensions"][1]["checks"][0]
    assert check["remediation"]


def test_every_check_has_a_severity_from_the_taxonomy(tmp_path: Path) -> None:
    from agent_aidf.audit import SEVERITIES, SEVERITY_ORDER

    result = run_audit(tmp_path)

    for dimension in result.dimensions:
        for check in dimension.checks:
            assert check.severity in SEVERITY_ORDER, check.id
            assert SEVERITIES[check.id] == check.severity
    assert _check(result, "no-credentials").severity == "critical"
    assert _check(result, "pii-masking-rules").severity == "critical"
    assert _check(result, "budget-caps").severity == "high"
    assert _check(result, "blocking-gates").severity == "high"
    assert _check(result, "risk-assessment").severity == "medium"
    assert _check(result, "front-matter-v2").severity == "low"


def test_failed_checks_filter_by_minimum_severity(tmp_path: Path) -> None:
    from agent_aidf.audit import failed_checks

    result = run_audit(tmp_path)
    ids = lambda checks: {check.id for _, check in checks}  # noqa: E731

    critical = ids(failed_checks(result, "critical"))
    high = ids(failed_checks(result, "high"))
    everything = ids(failed_checks(result))

    assert critical == {"no-credentials", "pii-masking-rules"}
    assert critical < high < everything
    assert "budget-caps" in high and "budget-caps" not in critical
    assert "front-matter-v2" in everything and "front-matter-v2" not in high


def test_failed_checks_reject_an_unknown_severity(tmp_path: Path) -> None:
    from agent_aidf.audit import failed_checks

    with pytest.raises(ValueError, match="Unknown severity 'urgent'"):
        failed_checks(run_audit(tmp_path), "urgent")


def test_has_critical_findings_only_when_a_critical_check_fails(tmp_path: Path) -> None:
    from agent_aidf.audit import has_critical_findings

    assert has_critical_findings(run_audit(tmp_path)) is True
    assert has_critical_findings(run_audit(_complete_repo(tmp_path / "ok"))) is False


def test_text_report_shows_only_findings_at_the_chosen_severity(tmp_path: Path) -> None:
    from agent_aidf.audit import render_audit_report

    result = run_audit(tmp_path)

    critical_only = render_audit_report(result, "critical")
    assert "[CRITICAL]" in critical_only
    assert "[HIGH]" not in critical_only and "[LOW]" not in critical_only

    complete = render_audit_report(run_audit(_complete_repo(tmp_path / "ok")), "high")
    assert "No findings at severity high or above." in complete


def test_json_export_carries_the_severity_of_every_check(tmp_path: Path) -> None:
    payload = run_audit(tmp_path).to_dict()

    severities = {c["id"]: c["severity"] for d in payload["dimensions"] for c in d["checks"]}
    assert severities["no-credentials"] == "critical"
    assert len(severities) == 15


# --- edge-case suite: missing governance, partial compliance, CLI flags, isolation -------------

SECRET_LINE = 'api_key = "abcdefghijklmnopqrstu"\n'


def _snapshot(root: Path) -> dict[str, bytes | None]:
    """Every path under root with its bytes (None for directories), to prove a run wrote nothing."""
    return {
        str(path.relative_to(root)): (path.read_bytes() if path.is_file() else None)
        for path in sorted(root.rglob("*"))
    }


def _all_titles(result) -> dict[str, str]:
    return {check.id: check.title for dim in result.dimensions for check in dim.checks}


# 1. Repository without governance -----------------------------------------------------------


def test_repo_without_kaidf_scaffold_or_specs_fails_those_checks(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Plain project\n")

    result = run_audit(tmp_path)

    assert _check(result, "kaidf-scaffold").points == 0
    assert "missing" in _check(result, "kaidf-scaffold").detail
    assert _check(result, "specs-parse").points == 0
    assert _check(result, "mentor-state").points == 0
    # A README without secrets passes the credential check, which is the only point it can earn.
    assert result.score == _check(result, "no-credentials").points
    assert result.tier == classify_tier(result.score)


@pytest.mark.parametrize(
    "setup",
    [
        pytest.param(lambda root: None, id="empty-directory"),
        pytest.param(lambda root: _write(root / ".kaidf", "not a directory\n"), id="kaidf-is-file"),
        pytest.param(
            lambda root: _write(root / "specs/broken.yaml", "k: [unclosed\n"), id="bad-yaml"
        ),
        pytest.param(
            lambda root: _write(root / ".kaidf/mentor-workflow.json", "[1, 2, 3]"),
            id="mentor-state-not-object",
        ),
        pytest.param(
            lambda root: _write(root / ".kaidf/policy/pii-masking-rules.yaml", "- just a list\n"),
            id="pii-rules-not-mapping",
        ),
        pytest.param(
            lambda root: (root / "binary.bin").write_bytes(b"\x00\xff\xfe" * 100),
            id="binary-only",
        ),
    ],
)
def test_degenerate_repositories_score_without_raising(tmp_path: Path, setup) -> None:
    setup(tmp_path)

    result = run_audit(tmp_path)

    assert 0 <= result.score <= 100
    assert len(result.dimensions) == len(DIMENSION_SPECS)
    assert result.tier in {tier for tier, _ in audit.TIERS} | {audit.UNRATED}


def test_empty_repository_reports_every_check_with_a_detail(tmp_path: Path) -> None:
    result = run_audit(tmp_path)

    for dimension in result.dimensions:
        for check in dimension.checks:
            assert check.detail, check.id
            assert 0 <= check.points <= check.max_points


def test_repository_without_governance_is_flagged_as_critical(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Plain project\n")

    result = run_audit(tmp_path)

    assert has_critical_findings(result)


# 2. Partial compliance -----------------------------------------------------------------------


def test_partial_scaffold_earns_points_for_each_part_present(tmp_path: Path) -> None:
    _write(tmp_path / ".kaidf/README.md", FRONT_MATTER)
    _write(tmp_path / ".kaidf/docs/00-overview/kaidf.md", FRONT_MATTER)

    result = run_audit(tmp_path)

    scaffold = _check(result, "kaidf-scaffold")
    assert scaffold.points == scaffold.max_points
    assert _check(result, "mentor-state").points == 0
    assert 0 < result.score < 100


def test_specs_score_is_proportional_to_the_valid_fraction(tmp_path: Path) -> None:
    _write(tmp_path / "specs/good.yaml", "version: '1.0'\n")
    _write(tmp_path / "specs/bad.yaml", "k: [unclosed\n")
    _write(tmp_path / "specs/also-bad.yaml", "k: [unclosed\n")
    _write(tmp_path / "specs/fine.yaml", "a: 1\n")

    check = _check(run_audit(tmp_path), "specs-parse")

    assert check.points == round(check.max_points * 2 / 4)


def test_front_matter_score_is_proportional_to_complete_documents(tmp_path: Path) -> None:
    _write(tmp_path / ".kaidf/docs/a.md", FRONT_MATTER)
    _write(tmp_path / ".kaidf/docs/b.md", FRONT_MATTER)
    _write(tmp_path / ".kaidf/docs/c.md", "# no front matter\n")
    _write(tmp_path / ".kaidf/docs/d.md", "# no front matter\n")

    check = _check(run_audit(tmp_path), "front-matter-v2")

    assert check.points == round(check.max_points * 2 / 4)
    assert "2 of 4" in check.detail


def test_intent_folder_only_earns_the_generic_checks(tmp_path: Path) -> None:
    # There is no intent-constraints check. docs/01_intent_constraints/ can only score through the
    # generic checks that scan every file: the credential scan and the front-matter scan.
    _write(tmp_path / "docs/01_intent_constraints/intent.md", FRONT_MATTER)

    result = run_audit(tmp_path)

    earned = {check.id for dim in result.dimensions for check in dim.checks if check.points > 0}
    assert earned == {"no-credentials", "front-matter-v2"}
    assert (
        result.score
        == _check(result, "no-credentials").points + _check(result, "front-matter-v2").points
    )


def test_removing_artifacts_lowers_the_score_by_their_weight(tmp_path: Path) -> None:
    _complete_repo(tmp_path)
    (tmp_path / "data/manifests/dataset-audit.yaml").unlink()
    (tmp_path / "docs/20-ethical-model/risk-assessment.json").unlink()

    result = run_audit(tmp_path)

    lost = _check(result, "dataset-audit").max_points + _check(result, "risk-assessment").max_points
    assert result.score == 100 - lost
    assert result.tier == classify_tier(result.score)


# 3. Command-line flags -----------------------------------------------------------------------


@pytest.fixture
def clean_cwd(tmp_path: Path, monkeypatch) -> Path:
    """Run the CLI from an empty directory so any stray write would show up there."""
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir


def test_severity_flag_filters_findings_to_the_requested_level(
    tmp_path: Path, clean_cwd, capsys
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    result = run_audit(repo)
    titles = _all_titles(result)

    for level in SEVERITY_ORDER:
        report = "".join(render_audit_report(result, level).split())
        expected = {check.id for _, check in failed_checks(result, level)}
        for check_id, title in titles.items():
            normalized = "".join(title.split())
            if check_id in expected:
                assert normalized in report, (level, check_id)
            else:
                assert normalized not in report, (level, check_id)


@pytest.mark.parametrize("level", SEVERITY_ORDER)
def test_cli_accepts_every_severity_level(tmp_path: Path, clean_cwd, capsys, level) -> None:
    assert _run_cli(["audit", str(tmp_path), "--severity", level]) == 0


def test_cli_rejects_an_unknown_severity(tmp_path: Path, clean_cwd, capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        _run_cli(["audit", str(tmp_path), "--severity", "urgent"])

    assert excinfo.value.code == 2


def test_fail_on_critical_exits_zero_without_critical_findings(
    tmp_path: Path, clean_cwd, capsys
) -> None:
    _complete_repo(tmp_path)
    # Removing the CI workflow fails only high-severity checks, never a critical one.
    (tmp_path / ".github/workflows/ci.yml").unlink()
    result = run_audit(tmp_path)
    assert not has_critical_findings(result)

    assert _run_cli(["audit", str(tmp_path), "--fail-on-critical"]) == 0
    assert "critical findings" not in capsys.readouterr().err


def test_fail_on_critical_exits_one_when_a_critical_check_fails(
    tmp_path: Path, clean_cwd, capsys
) -> None:
    _complete_repo(tmp_path)
    _write(tmp_path / "config.py", SECRET_LINE)

    assert _run_cli(["audit", str(tmp_path), "--fail-on-critical"]) == 1
    assert "critical findings are present" in capsys.readouterr().err


def test_audit_without_the_flag_still_exits_zero_on_critical_findings(
    tmp_path: Path, clean_cwd, capsys
) -> None:
    _complete_repo(tmp_path)
    _write(tmp_path / "config.py", SECRET_LINE)

    assert _run_cli(["audit", str(tmp_path)]) == 0


def test_fail_on_critical_with_json_output_still_fails(tmp_path: Path, clean_cwd, capsys) -> None:
    _complete_repo(tmp_path)
    _write(tmp_path / "config.py", SECRET_LINE)

    assert _run_cli(["audit", str(tmp_path), "--json", "--fail-on-critical"]) == 1


# 4. Isolation and cleanup --------------------------------------------------------------------


def test_run_audit_is_read_only(tmp_path: Path) -> None:
    _complete_repo(tmp_path)
    before = _snapshot(tmp_path)

    run_audit(tmp_path)

    assert _snapshot(tmp_path) == before


def test_cli_run_leaves_the_repository_and_the_cwd_untouched(
    tmp_path: Path, clean_cwd, capsys
) -> None:
    _complete_repo(tmp_path)
    _write(tmp_path / "config.py", SECRET_LINE)
    before = _snapshot(tmp_path)

    _run_cli(["audit", str(tmp_path), "--severity", "low", "--fail-on-critical"])
    _run_cli(["audit", str(tmp_path), "--json"])

    assert _snapshot(tmp_path) == before
    assert list(clean_cwd.iterdir()) == []


def test_extension_state_is_redirected_into_tmp_path(tmp_path: Path) -> None:
    # The autouse fixture in conftest.py points the user extensions directory at tmp_path, so a
    # CLI run never reads or writes ~/.kob.
    import os

    assert os.environ["KOB_EXTENSIONS_DIR"].startswith(str(tmp_path))
