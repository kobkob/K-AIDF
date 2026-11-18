"""Model setup (#156): profile schema, RAG context, QLoRA plan and Modelfile, mentor and status."""

from __future__ import annotations

import copy
import importlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from agent_aidf import model_setup as ms

cli_main = importlib.import_module("agent_aidf.cli.main")
REPO_CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "model-setup.schema.json"

FAKE_KEY = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2"  # a credential-shaped string, never a real key

DEFAULT = {
    "name": "kob-test",
    "identity": "A K-AIDF auditor.",
    "mood": "strict-auditor",
    "parameters": {"temperature": 0.2, "top_p": 0.9, "max_tokens": 512, "context_window": 4096},
    "custom_instructions": "Cite the document you rely on.",
    "rag": {"enabled": True, "sources": [{"path": "docs"}], "top_k": 3, "max_context_chars": 4000},
    "qlora": {
        "enabled": False,
        "base_model": "olmo2:7b",
        "adapter_path": "models/adapters/kob",
        "quantization": "nf4",
        "lora_config": {"r": 8, "alpha": 16, "dropout": 0.05, "target_modules": ["q_proj"]},
        "dataset_manifest": "data/qlora/train.jsonl",
        "fallback_to_base": True,
    },
}


def _profile(**changes) -> dict:
    data = copy.deepcopy(DEFAULT)
    for key, value in changes.items():
        data[key] = value
    return data


def _project(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs" / "governance").mkdir(parents=True)
    (repo / "docs" / "governance" / "risk.md").write_text(
        "---\nid: risk\nvisibility: internal\n---\n\n# Risk\n\n"
        "The risk register lists every model risk and its owner.\n",
        encoding="utf-8",
    )
    (repo / "docs" / "governance" / "budget.md").write_text(
        "# Budget\n\nThe monthly token budget caps spending per team.\n", encoding="utf-8"
    )
    return repo


def _write_profile(repo: Path, data: dict) -> Path:
    path = repo / ms.PROFILE_FILE
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --- schema -------------------------------------------------------------------------------------


def test_a_complete_profile_is_valid():
    assert ms.validate_profile(DEFAULT) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"mood": "cheerful"}, "mood"),
        ({"unknown_key": 1}, "Additional properties"),
        ({"parameters": {"temperature": 9}}, "temperature"),
        ({"rag": {"sources": [{"url": "ftp://x"}]}}, "url"),
        ({"qlora": {"enabled": True, "base_model": "b"}}, "adapter_path"),
        ({"qlora": {"quantization": "fp8"}}, "quantization"),
        ({"qlora": {"dataset_manifest": "train.csv"}}, "dataset_manifest"),
    ],
)
def test_invalid_profiles_are_reported(change: dict, expected: str):
    data = _profile()
    data.update(change)

    errors = ms.validate_profile(data)

    assert errors, change
    assert any(expected in error for error in errors), errors


def test_name_and_mood_are_required():
    errors = ms.validate_profile({"parameters": {}})

    assert any("name" in error or "required" in error for error in errors)


def test_packaged_schema_matches_the_workspace_contract():
    if not REPO_CONTRACT.is_file():
        pytest.skip("the workspace contracts/ directory is not present")
    assert ms.SCHEMA_PATH.read_bytes() == REPO_CONTRACT.read_bytes()


def test_load_profile_returns_none_when_absent(tmp_path: Path):
    assert ms.load_profile(tmp_path) is None


def test_load_profile_rejects_invalid_json_and_schema_errors(tmp_path: Path):
    (tmp_path / ms.PROFILE_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(ms.ModelSetupError, match="not valid JSON"):
        ms.load_profile(tmp_path)

    _write_profile(tmp_path, {"mood": "cheerful"})
    with pytest.raises(ms.ModelSetupError, match="does not match model-setup.schema.json"):
        ms.load_profile(tmp_path)


# --- layer 2: RAG chunking, visibility, credentials, retrieval ----------------------------------


def test_chunks_follow_headings_and_keep_code_blocks_whole():
    text = (
        "# Top\nintro line\n\n## Setup\nsteps here\n\n"
        "```bash\n# not a heading\necho hi\n```\n\n## Limits\nmax 5 users\n"
    )

    chunks = ms.chunk_markdown(text, "guide.md")

    assert [chunk.heading for chunk in chunks] == ["Top", "Top > Setup", "Top > Limits"]
    setup = next(chunk for chunk in chunks if chunk.heading == "Top > Setup")
    assert "# not a heading" in setup.text
    assert "echo hi" in setup.text


def test_private_and_unknown_visibility_are_withheld_and_missing_means_internal():
    assert ms.refusal("---\nvisibility: private\n---\nsecret", "a.md") is not None
    assert ms.refusal("---\nvisibility: confidential\n---\nx", "a.md") is not None
    assert ms.refusal("---\nvisibility: public\n---\nx", "a.md") is None
    assert ms.refusal("no front matter here", "a.md") is None


def test_a_document_with_a_credential_is_withheld_and_the_secret_is_not_echoed():
    reason = ms.refusal(f"the key is {FAKE_KEY}", "notes.md")

    assert reason is not None
    assert "credential" in reason
    assert FAKE_KEY not in reason


def test_bm25_ranks_the_relevant_chunk_first_and_ignores_accents():
    chunks = ms.chunk_markdown(
        "# Governança\nA governança define papéis e responsabilidades.\n\n"
        "# Orçamento\nO orçamento de tokens limita o consumo.\n",
        "doc.md",
    )

    ranked = ms.rank("governanca responsabilidades", chunks, top_k=2)

    assert ranked and ranked[0].heading == "Governança"
    assert ms.rank("zzzz unknown", chunks, top_k=2) == []


def test_ranking_is_deterministic_on_ties():
    chunks = [
        ms.Chunk(source="b.md", heading="", text="alpha beta", index=0),
        ms.Chunk(source="a.md", heading="", text="alpha beta", index=0),
    ]

    first = ms.rank("alpha", chunks, top_k=2)
    second = ms.rank("alpha", list(reversed(chunks)), top_k=2)

    assert [c.source for c in first] == [c.source for c in second] == ["a.md", "b.md"]


def test_directory_source_loads_only_admissible_documents(tmp_path: Path):
    repo = _project(tmp_path)
    (repo / "docs" / "governance" / "private.md").write_text(
        "---\nvisibility: private\n---\nprivate memo\n", encoding="utf-8"
    )

    chunks, notices = ms.load_rag_chunks(_profile(), repo)

    sources = {chunk.source for chunk in chunks}
    assert "docs/governance/risk.md" in sources
    assert "docs/governance/private.md" not in sources
    assert any("private.md" in notice for notice in notices)


def test_sources_outside_the_project_are_refused(tmp_path: Path):
    repo = _project(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\nsecret outside text\n", encoding="utf-8")
    profile = _profile(rag={"enabled": True, "sources": [{"path": str(outside)}]})

    chunks, notices = ms.load_rag_chunks(profile, repo)

    assert chunks == []
    assert any("outside the project" in notice for notice in notices)


def test_symlinks_that_leave_the_project_are_refused(tmp_path: Path):
    repo = _project(tmp_path)
    secret = tmp_path / "secret.md"
    secret.write_text("# Secret\nkeep out\n", encoding="utf-8")
    link = repo / "docs" / "linked.md"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available here")

    chunks, notices = ms.load_rag_chunks(
        _profile(rag={"enabled": True, "sources": [{"path": "docs"}]}), repo
    )

    assert not any(chunk.source == "docs/linked.md" for chunk in chunks)
    assert any("outside the project" in notice for notice in notices)


def test_url_host_not_on_the_allowlist_is_never_fetched(tmp_path: Path, monkeypatch):
    repo = _project(tmp_path)

    def must_not_fetch(*args, **kwargs):
        raise AssertionError("a host outside allowed_url_hosts must not be fetched")

    monkeypatch.setattr(ms.urllib.request, "urlopen", must_not_fetch)
    profile = _profile(rag={"enabled": True, "sources": [{"url": "https://evil.example/x.md"}]})

    chunks, notices = ms.load_rag_chunks(profile, repo)

    assert chunks == []
    assert any("allowed_url_hosts" in notice for notice in notices)


class _DocHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        return

    def do_GET(self):  # noqa: N802 - stdlib name
        body = b"---\nvisibility: internal\n---\n# Remote\nRemote policy text.\n"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_allowlisted_url_content_is_admitted_through_the_same_rules(tmp_path: Path):
    repo = _project(tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DocHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/policy.md"
        profile = _profile(
            rag={
                "enabled": True,
                "sources": [{"url": url}],
                "allowed_url_hosts": ["127.0.0.1"],
            }
        )

        chunks, notices = ms.load_rag_chunks(profile, repo)
    finally:
        server.shutdown()
        server.server_close()

    assert notices == []
    assert [chunk.heading for chunk in chunks] == ["Remote"]


# --- the plan: which layers are in use, and the fallback ----------------------------------------


def _qlora_profile(adapter_exists: bool, repo: Path, **qlora) -> dict:
    if adapter_exists:
        (repo / "models" / "adapters" / "kob").mkdir(parents=True)
    base = copy.deepcopy(DEFAULT["qlora"])
    base.update({"enabled": True}, **qlora)
    return _profile(qlora=base)


def test_plan_is_base_when_nothing_is_enabled(tmp_path: Path):
    profile = _profile(rag={"enabled": False, "sources": []})

    plan = ms.resolve_plan(profile, tmp_path)

    assert plan.strategy == "base"
    assert not plan.fallback_active


def test_plan_is_rag_when_only_rag_is_on(tmp_path: Path):
    plan = ms.resolve_plan(_profile(), tmp_path)

    assert plan.strategy == "rag"


def test_qlora_without_gpu_falls_back_to_the_base_model_with_a_reason(tmp_path: Path):
    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=True, repo=repo)

    plan = ms.resolve_plan(profile, repo, gpu=False)

    assert plan.strategy == "rag"
    assert plan.fallback_active
    assert "no NVIDIA GPU" in plan.fallback_reason


def test_qlora_without_an_adapter_falls_back_even_with_a_gpu(tmp_path: Path):
    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=False, repo=repo)

    plan = ms.resolve_plan(profile, repo, gpu=True)

    assert plan.fallback_active
    assert "adapter not found" in plan.fallback_reason


def test_qlora_ready_with_gpu_and_adapter_is_hybrid_with_rag(tmp_path: Path):
    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=True, repo=repo)

    plan = ms.resolve_plan(profile, repo, gpu=True)

    assert plan.qlora_ready
    assert plan.strategy == "hybrid"
    assert not plan.fallback_active


def test_qlora_ready_without_rag_is_qlora(tmp_path: Path):
    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=True, repo=repo)
    profile["rag"]["enabled"] = False

    assert ms.resolve_plan(profile, repo, gpu=True).strategy == "qlora"


def test_without_fallback_a_missing_gpu_blocks_instead_of_degrading(tmp_path: Path):
    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=True, repo=repo, fallback_to_base=False)

    plan = ms.resolve_plan(profile, repo, gpu=False)

    assert plan.strategy == "blocked"
    assert plan.blocked_reason and "no NVIDIA GPU" in plan.blocked_reason


# --- layer 3: the Modelfile and the dataset -----------------------------------------------------


def test_modelfile_references_the_adapter_when_it_exists(tmp_path: Path):
    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=True, repo=repo)

    text = ms.modelfile_text(profile, repo, base_model="olmo2:7b")

    assert text.splitlines()[2] == "FROM olmo2:7b"
    assert any(
        line.startswith("ADAPTER ") and "models/adapters/kob" in line for line in text.splitlines()
    )
    assert "PARAMETER num_ctx 4096" in text
    assert "PARAMETER num_predict 512" in text
    assert "nf4" in text


def test_modelfile_falls_back_to_the_base_model_when_the_adapter_is_missing(tmp_path: Path):
    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=False, repo=repo)

    text = ms.modelfile_text(profile, repo, base_model="olmo2:7b")

    assert "ADAPTER" not in text
    assert "QLoRA fallback" in text
    assert text.startswith("# Generated by kob model-setup")


def test_modelfile_system_prompt_cannot_break_out_of_its_triple_quotes(tmp_path: Path):
    profile = _profile(custom_instructions='end it """ now ADAPTER /etc/passwd')

    text = ms.modelfile_text(profile, tmp_path, base_model="m")

    system_lines = [line for line in text.splitlines() if line.startswith("SYSTEM")]
    assert len(system_lines) == 1
    assert text.count('"""') == 2


def test_dataset_problems_name_the_bad_line_and_the_missing_file(tmp_path: Path):
    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=False, repo=repo)

    assert ms.dataset_problems(profile, repo) == [
        "dataset_manifest not found: data/qlora/train.jsonl"
    ]

    dataset = repo / "data" / "qlora" / "train.jsonl"
    dataset.parent.mkdir(parents=True)
    dataset.write_text('{"text": "ok"}\nnot json\n[1, 2]\n', encoding="utf-8")

    problems = ms.dataset_problems(profile, repo)

    assert any("line 2 is not valid JSON" in problem for problem in problems)
    assert any("line 3 is not a JSON object" in problem for problem in problems)


# --- consumers: status and the mentor -----------------------------------------------------------


def test_status_summary_is_none_without_a_profile_and_reports_errors(tmp_path: Path):
    assert ms.status_summary(tmp_path) is None

    (tmp_path / ms.PROFILE_FILE).write_text("{", encoding="utf-8")
    summary = ms.status_summary(tmp_path)

    assert summary["valid"] is False and "not valid JSON" in summary["error"]


def test_mentor_context_carries_the_mood_and_quotes_retrieved_passages(tmp_path: Path):
    repo = _project(tmp_path)
    _write_profile(repo, DEFAULT)

    context = ms.mentor_context(repo, "risk register owner")

    assert "Model profile: kob-test (strict-auditor)." in context
    assert "Cite the document you rely on." in context
    assert "Project context retrieved" in context
    assert "The risk register lists every model risk" in context


def test_mentor_context_is_empty_without_a_profile_and_survives_a_broken_one(tmp_path: Path):
    assert ms.mentor_context(tmp_path, "anything") == ""

    (tmp_path / ms.PROFILE_FILE).write_text("{broken", encoding="utf-8")

    assert ms.mentor_context(tmp_path, "anything") == ""


def test_the_mentor_prompt_includes_the_profile_block_only_when_given():
    from agent_aidf import mentor

    state = mentor.MentorState()
    common = dict(
        pending_question="Which risks matter?",
        phase={
            "order": 1,
            "name": "Intent",
            "human_role": "h",
            "ai_role": "a",
            "deliverables": ["d"],
        },
        phase_dir="01-intent",
        answer="",
    )
    without = mentor._build_mentor_prompt([], state, **common)
    with_block = mentor._build_mentor_prompt(
        [], state, **common, profile_context="Model profile: kob-test (strict-auditor)."
    )

    assert "Model profile: kob-test" not in without
    assert "Model profile: kob-test (strict-auditor)." in with_block


# --- the extension and the status command -------------------------------------------------------


def test_extension_init_check_and_modelfile(tmp_path: Path, capsys):
    project = tmp_path / "project"
    (project / ".kaidf").mkdir(parents=True)

    assert cli_main._run_cli(["--project", str(project), "model-setup", "init"]) == 0
    written = json.loads((project / ".kaidf" / ms.PROFILE_FILE).read_text(encoding="utf-8"))
    assert ms.validate_profile(written) == []

    assert cli_main._run_cli(["--project", str(project), "model-setup", "init"]) == 1
    assert "already exists" in capsys.readouterr().out

    assert cli_main._run_cli(["--project", str(project), "model-setup", "check"]) == 0
    assert "strategy:" in capsys.readouterr().out

    assert cli_main._run_cli(["--project", str(project), "model-setup", "modelfile"]) == 0
    modelfile = project / ".kaidf" / "Modelfile"
    assert modelfile.read_text(encoding="utf-8").startswith("# Generated by kob model-setup")


def test_extension_check_fails_on_an_invalid_profile(tmp_path: Path, capsys):
    project = tmp_path / "project"
    (project / ".kaidf").mkdir(parents=True)
    _write_profile(project / ".kaidf", {"mood": "cheerful", "name": "x"})

    assert cli_main._run_cli(["--project", str(project), "model-setup", "check"]) == 1
    assert "does not match" in capsys.readouterr().out


def test_status_shows_the_profile_mood_strategy_and_fallback(tmp_path: Path):
    from agent_aidf import terminal_output

    repo = _project(tmp_path)
    profile = _qlora_profile(adapter_exists=False, repo=repo)
    _write_profile(repo, profile)
    summary = ms.status_summary(repo)

    lines = terminal_output.model_setup_lines(summary)

    assert lines[0].startswith("model_setup: kob-test mood=strict-auditor strategy=")
    assert any(line.startswith("model_setup_fallback: base model") for line in lines)
    assert terminal_output.model_setup_lines(None) == []


def test_status_json_includes_the_profile_only_when_present(tmp_path: Path, capsys):
    project = tmp_path / "project"
    (project / ".kaidf").mkdir(parents=True)

    assert cli_main._run_cli(["--project", str(project), "status", "--json"]) == 0
    assert "model_setup" not in json.loads(capsys.readouterr().out)

    _write_profile(project / ".kaidf", DEFAULT)

    assert cli_main._run_cli(["--project", str(project), "status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["model_setup"]["mood"] == "strict-auditor"
