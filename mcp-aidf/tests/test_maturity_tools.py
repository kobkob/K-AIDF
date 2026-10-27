from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import app
import maturity

TOKEN = "test-bearer-token-0123456789abcdef"
SCOPED_TOKEN = "scoped-token-0123456789abcdefghij"
SEVERITY_ORDER = ("critical", "high", "medium", "low")
SEVERITIES = set(SEVERITY_ORDER)


@pytest.fixture(autouse=True)
def primary_token(monkeypatch):
    monkeypatch.setattr(app, "ACTIVE_BEARER_TOKEN", TOKEN)
    monkeypatch.setattr(app, "TOKEN_SCOPES", {})


@pytest.fixture
def client():
    return app.app.test_client()


@pytest.fixture
def engine():
    # The audit engine lives in agent-aidf. Skip, rather than fail, where it is not installed.
    return pytest.importorskip("agent_aidf.audit")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


FRONT_MATTER = (
    "---\nid: docs/doc.md\ntitle: Doc\ndocument_class: core-doc\nphase: 00-overview\n"
    "visibility: internal\nstatus: active\n---\n\n# Doc\n"
)


def _compliant_repo(root: Path) -> Path:
    _write(root / ".kaidf/README.md", FRONT_MATTER)
    _write(root / ".kaidf/docs/00-overview/kaidf.md", FRONT_MATTER)
    _write(root / ".kaidf/mentor-workflow.json", '{"phase": "01"}')
    _write(root / ".kaidf/policy/pii-masking-rules.yaml", "rules:\n  - email\n")
    _write(root / ".kaidf/policy/hitl-config.yaml", "reviewer: human\n")
    _write(
        root / ".kaidf/policy/budget.yaml",
        "max_tokens: 4096\nrequest_timeout_seconds: 30\nlocal_fallback: true\n",
    )
    _write(root / "specs/kaidf.yaml", "version: '1.0'\n")
    _write(root / "docs/20-ethical-model/risk-assessment.json", '{"risk": "low"}')
    _write(root / "docs/20-ethical-model/explicability-schema.json", '{"fields": []}')
    _write(root / "data/manifests/dataset-audit.yaml", "dataset: demo\n")
    _write(
        root / "data/manifests/skills.yaml",
        'version: "1.0"\nskills:\n  - id: "kaidf-audit"\n    command: "kob audit"\n'
        '    permissions:\n      filesystem: "read"\n',
    )
    _write(root / ".github/workflows/ci.yml", "jobs:\n  test:\n    steps:\n      - run: pytest\n")
    return root


def _call(client, name: str, arguments: dict | None = None, token: str = TOKEN):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }
    return client.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}"})


def _payload(response) -> dict:
    return json.loads(response.get_json()["result"]["content"][0]["text"])


def _error(response) -> dict:
    return response.get_json()["error"]


@pytest.fixture
def repo_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("AIDF_REPO_ROOT", str(root))
    return root


# --- registration -------------------------------------------------------------------------------


def test_both_tools_are_listed_with_their_schemas(client) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    tools = {
        tool["name"]: tool
        for tool in client.post(
            "/mcp", json=body, headers={"Authorization": f"Bearer {TOKEN}"}
        ).get_json()["result"]["tools"]
    }

    assert {"search", "fetch", "get_maturity_scorecard", "evaluate_repository_maturity"} <= set(
        tools
    )
    evaluate_schema = tools["evaluate_repository_maturity"]["inputSchema"]["properties"]
    assert set(evaluate_schema) == {"path", "format"}
    assert evaluate_schema["format"]["enum"] == ["json", "prompt"]


# --- get_maturity_scorecard ---------------------------------------------------------------------


def test_scorecard_returns_the_engine_matrix(client, engine) -> None:
    response = _call(client, "get_maturity_scorecard")

    matrix = _payload(response)
    assert response.status_code == 200
    assert matrix["framework"] == "KAIDF-AMM"
    assert matrix["total_points"] == 100
    assert len(matrix["dimensions"]) == 5
    assert matrix["severity_order"] == ["critical", "high", "medium", "low"]
    for dimension in matrix["dimensions"]:
        assert dimension["max_points"] == 20
        for check in dimension["checks"]:
            assert check["severity"] in SEVERITIES
            assert check["remediation"]
    assert matrix["tiers"][0]["name"] == "Platinum"


def test_scorecard_is_available_to_scoped_tokens(client, engine, monkeypatch) -> None:
    monkeypatch.setattr(app, "TOKEN_SCOPES", {SCOPED_TOKEN: frozenset({"tenant-a"})})

    response = _call(client, "get_maturity_scorecard", token=SCOPED_TOKEN)

    assert response.status_code == 200
    assert _payload(response)["total_points"] == 100


# --- evaluate_repository_maturity: payload shape -------------------------------------------------


def test_failing_repository_lists_violations_gaps_and_backlog(
    client, engine, repo_root: Path
) -> None:
    response = _call(client, "evaluate_repository_maturity")

    evaluation = _payload(response)
    assert response.status_code == 200
    assert evaluation["repo_root"] == str(repo_root.resolve())
    assert 0 <= evaluation["score"] < 100
    assert evaluation["max_score"] == 100
    assert [d["id"] for d in evaluation["dimensions"]]
    assert all({"points", "max_points"} <= set(d) for d in evaluation["dimensions"])

    violations = evaluation["violations"]
    assert violations, "an empty repository must have violations"
    ranks = [SEVERITY_ORDER.index(v["severity"]) for v in violations]
    assert ranks == sorted(ranks), "violations are ordered by severity, critical first"
    assert all(v["gap_points"] == v["max_points"] - v["points"] > 0 for v in violations)
    assert all(v["remediation"] and v["detail"] for v in violations)

    gaps = evaluation["gaps_by_severity"]
    assert set(gaps) == SEVERITIES
    assert sum(gaps.values()) == len(violations)
    assert gaps["critical"] >= 1, "an empty repository fails the critical credential check"


def test_backlog_follows_the_violation_order(client, engine, repo_root: Path) -> None:
    evaluation = _payload(_call(client, "evaluate_repository_maturity"))

    backlog = evaluation["recommendations"]
    assert [item["priority"] for item in backlog] == list(range(1, len(backlog) + 1))
    assert [item["check_id"] for item in backlog] == [
        v["check_id"] for v in evaluation["violations"]
    ]
    assert all(item["action"] for item in backlog)
    assert backlog[0]["severity"] == "critical"


def test_compliant_repository_has_no_violations_and_no_backlog(
    client, engine, repo_root: Path
) -> None:
    _compliant_repo(repo_root)

    evaluation = _payload(_call(client, "evaluate_repository_maturity"))

    assert evaluation["score"] == 100
    assert evaluation["tier"] == "Platinum"
    assert evaluation["violations"] == []
    assert evaluation["recommendations"] == []
    assert evaluation["gaps_by_severity"] == {s: 0 for s in SEVERITIES}


def test_prompt_format_embeds_the_evaluation_for_a_local_model(
    client, engine, repo_root: Path
) -> None:
    response = _call(client, "evaluate_repository_maturity", {"format": "prompt"})

    text = response.get_json()["result"]["content"][0]["text"]
    assert "Diagnóstico" in text
    assert "Backlog de mitigação" in text
    assert '"violations"' in text
    assert '"recommendations"' in text


def test_json_is_the_default_format(client, engine, repo_root: Path) -> None:
    evaluation = _payload(_call(client, "evaluate_repository_maturity"))

    assert "violations" in evaluation


# --- path handling ------------------------------------------------------------------------------


def test_relative_path_is_taken_from_the_configured_root(client, engine, repo_root: Path) -> None:
    (repo_root / "service").mkdir()

    evaluation = _payload(_call(client, "evaluate_repository_maturity", {"path": "service"}))

    assert evaluation["repo_root"] == str((repo_root / "service").resolve())


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("../escape", "outside the configured repository root"),
        ("/etc", "outside the configured repository root"),
        ("missing-dir", "does not exist"),
    ],
)
def test_invalid_paths_are_rejected_with_invalid_params(
    client, engine, repo_root: Path, path: str, message: str
) -> None:
    response = _call(client, "evaluate_repository_maturity", {"path": path})

    assert response.status_code == 400
    assert _error(response)["code"] == -32602
    assert message in _error(response)["message"]


def test_a_file_is_not_a_valid_evaluation_target(client, engine, repo_root: Path) -> None:
    (repo_root / "README.md").write_text("# hi\n", encoding="utf-8")

    response = _call(client, "evaluate_repository_maturity", {"path": "README.md"})

    assert _error(response)["code"] == -32602
    assert "not a directory" in _error(response)["message"]


def test_symlink_pointing_outside_the_root_is_rejected(
    client, engine, repo_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo_root / "link").symlink_to(outside, target_is_directory=True)

    response = _call(client, "evaluate_repository_maturity", {"path": "link"})

    assert _error(response)["code"] == -32602
    assert "outside the configured repository root" in _error(response)["message"]


def test_outside_paths_do_not_reveal_whether_they_exist(
    client, engine, repo_root: Path, tmp_path: Path
) -> None:
    existing_outside = tmp_path / "elsewhere"
    existing_outside.mkdir()

    real = _call(client, "evaluate_repository_maturity", {"path": str(existing_outside)})
    missing = _call(client, "evaluate_repository_maturity", {"path": str(tmp_path / "nope")})

    assert _error(real)["message"] == _error(missing)["message"]


def test_resolve_evaluation_path_defaults_to_the_root(tmp_path: Path) -> None:
    assert maturity.resolve_evaluation_path(tmp_path, None) == tmp_path.resolve()
    assert maturity.resolve_evaluation_path(tmp_path, "   ") == tmp_path.resolve()


# --- request validation and configuration -----------------------------------------------------


def test_unknown_format_is_rejected(client, engine, repo_root: Path) -> None:
    response = _call(client, "evaluate_repository_maturity", {"format": "xml"})

    assert _error(response)["code"] == -32602


def test_non_string_path_is_rejected(client, engine, repo_root: Path) -> None:
    response = _call(client, "evaluate_repository_maturity", {"path": 7})

    assert _error(response)["code"] == -32602
    assert "must be a string" in _error(response)["message"]


def test_missing_repository_root_configuration_is_a_server_error(client, monkeypatch) -> None:
    monkeypatch.delenv("AIDF_REPO_ROOT", raising=False)

    response = _call(client, "evaluate_repository_maturity")

    assert response.status_code == 503
    assert "AIDF_REPO_ROOT is not configured" in _error(response)["message"]


# --- authorization ------------------------------------------------------------------------------


def test_scoped_tokens_cannot_evaluate_a_repository(client, repo_root: Path, monkeypatch) -> None:
    monkeypatch.setattr(app, "TOKEN_SCOPES", {SCOPED_TOKEN: frozenset({"tenant-a"})})

    response = _call(client, "evaluate_repository_maturity", token=SCOPED_TOKEN)

    assert response.status_code == 403
    assert _error(response)["code"] == -32001


def test_unauthenticated_calls_are_refused(client, repo_root: Path) -> None:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "evaluate_repository_maturity", "arguments": {}},
    }

    assert client.post("/mcp", json=body).status_code == 401


# --- engine availability ------------------------------------------------------------------------


def test_deployment_without_the_engine_gets_a_clear_503(
    client, repo_root: Path, monkeypatch
) -> None:
    # A None entry makes `from agent_aidf import audit` raise ImportError, as in a Docker image
    # that does not ship agent-aidf.
    monkeypatch.setitem(sys.modules, "agent_aidf", None)

    scorecard = _call(client, "get_maturity_scorecard")
    evaluation = _call(client, "evaluate_repository_maturity")

    for response in (scorecard, evaluation):
        assert response.status_code == 503
        assert _error(response)["code"] == -32000
        assert "not installed" in _error(response)["message"]


def test_search_and_fetch_still_work_without_the_engine(
    client, repo_root: Path, monkeypatch
) -> None:
    monkeypatch.setitem(sys.modules, "agent_aidf", None)
    _write(repo_root / "README.md", "# Demo\n")

    response = _call(client, "search", {"query": "demo"})

    assert response.status_code == 200


# --- isolation ----------------------------------------------------------------------------------


def test_evaluation_is_read_only(client, engine, repo_root: Path) -> None:
    _compliant_repo(repo_root)
    before = {p.relative_to(repo_root): p.read_bytes() for p in repo_root.rglob("*") if p.is_file()}

    _call(client, "evaluate_repository_maturity")
    _call(client, "evaluate_repository_maturity", {"format": "prompt"})

    after = {p.relative_to(repo_root): p.read_bytes() for p in repo_root.rglob("*") if p.is_file()}
    assert after == before
