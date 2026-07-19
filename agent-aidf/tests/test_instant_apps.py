from __future__ import annotations

import socket
import json
from urllib import request
from pathlib import Path

from agent_aidf.instant_apps import (
    append_mentor_note,
    apply_mentor_update,
    create_instant_app,
    ensure_persistent_instant_app,
    get_instant_app,
    list_instant_apps,
    load_instant_app_runtime,
    run_instant_app,
    stop_instant_app,
)


def test_create_persistent_instant_app_under_dot_kaidf_apps(tmp_path: Path) -> None:
    repo = tmp_path / ".kaidf"
    repo.mkdir()

    app = create_instant_app(repo, app_id="Mentor Web", mode="persistent", kind="web")

    assert app.app_id == "mentor-web"
    assert app.mode == "persistent"
    assert app.kind == "web"
    assert app.root == repo / "apps" / "mentor-web"
    assert app.entrypoint == app.root / "main.py"
    assert (app.root / "app.json").is_file()
    assert (app.root / "index.html").is_file()


def test_create_ephemeral_instant_app_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / ".kaidf"
    repo.mkdir()

    app = create_instant_app(repo, app_id="Scratch Shell", mode="ephemeral", kind="shell")

    assert app.app_id == "scratch-shell"
    assert app.mode == "ephemeral"
    assert app.kind == "shell"
    assert app.root.parent != repo
    assert (app.root / "main.py").is_file()
    assert list_instant_apps(repo) == []


def test_get_instant_app_resolves_by_persistent_id(tmp_path: Path) -> None:
    repo = tmp_path / ".kaidf"
    repo.mkdir()
    created = create_instant_app(repo, app_id="mentor-shell", mode="persistent", kind="shell")

    loaded = get_instant_app(repo, "mentor-shell")

    assert loaded == created


def test_ensure_persistent_instant_app_reuses_existing_app(tmp_path: Path) -> None:
    repo = tmp_path / ".kaidf"
    repo.mkdir()
    create_instant_app(repo, app_id="mentor-web-app", mode="persistent", kind="web")

    app, created = ensure_persistent_instant_app(repo, app_id="mentor-web-app", kind="web")

    assert created is False
    assert app.app_id == "mentor-web-app"


def test_append_mentor_note_writes_to_app_directory(tmp_path: Path) -> None:
    repo = tmp_path / ".kaidf"
    repo.mkdir()
    create_instant_app(repo, app_id="mentor-shell", mode="persistent", kind="shell")

    notes_path = append_mentor_note(repo, "mentor-shell", heading="Step 1", body="Question: q\nAnswer: a")

    assert notes_path.is_file()
    content = notes_path.read_text(encoding="utf-8")
    assert "Step 1" in content
    assert "Answer: a" in content


def test_apply_mentor_update_refreshes_web_app_files(tmp_path: Path) -> None:
    repo = tmp_path / ".kaidf"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    create_instant_app(repo, app_id="mentor-web-app", mode="persistent", kind="web")

    brief_path = apply_mentor_update(
        repo,
        "mentor-web-app",
        step=2,
        category="implementation",
        question="What should we build next?",
        answer="Build a localhost review page with clear human validation.",
        mentor_reply="Focus on a guided browser review screen and keep the scope small.",
    )

    assert brief_path.is_file()
    index_html = (repo / "apps" / "mentor-web-app" / "index.html").read_text(encoding="utf-8")
    main_py = (repo / "apps" / "mentor-web-app" / "main.py").read_text(encoding="utf-8")
    brief_payload = json.loads((repo / "apps" / "mentor-web-app" / "mentor-brief.json").read_text(encoding="utf-8"))
    readme = (repo / "apps" / "mentor-web-app" / "README.md").read_text(encoding="utf-8")
    assert "localhost review page" in index_html
    assert "Current mentor question" in index_html
    assert "/api/answers" in index_html
    assert "MentorAppHandler" in main_py
    assert brief_payload["question"] == "What should we build next?"
    assert brief_payload["doc_links"]
    assert brief_payload["doc_links"][0]["href"].startswith("file://")
    assert "Current Intent" in readme


def test_run_and_stop_web_instant_app_runtime(tmp_path: Path) -> None:
    repo = tmp_path / ".kaidf"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    create_instant_app(repo, app_id="mentor-web-app", mode="persistent", kind="web")
    apply_mentor_update(
        repo,
        "mentor-web-app",
        step=1,
        category="manifesto",
        question="What should we build next?",
        answer="Build a localhost review page with clear human validation.",
        mentor_reply="Keep the page interactive and preserve the review trail.",
    )
    port = _free_port()

    runtime = run_instant_app(repo, "mentor-web-app", port=port)
    loaded = load_instant_app_runtime(repo, "mentor-web-app")

    assert runtime.status == "running"
    assert runtime.port == port
    assert runtime.pid is not None
    assert loaded is not None
    assert loaded.status == "running"
    state = json.loads(request.urlopen(f"http://127.0.0.1:{port}/api/state").read().decode("utf-8"))
    assert state["question"] == "What should we build next?"
    post = request.Request(
        f"http://127.0.0.1:{port}/api/answers",
        data=json.dumps({"text": "We need approval notes and doc links."}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    saved = json.loads(request.urlopen(post).read().decode("utf-8"))
    assert saved["text"] == "We need approval notes and doc links."
    refreshed = json.loads(request.urlopen(f"http://127.0.0.1:{port}/api/state").read().decode("utf-8"))
    assert refreshed["answers"][-1]["text"] == "We need approval notes and doc links."

    stopped = stop_instant_app(repo, "mentor-web-app")

    assert stopped.status == "stopped"
    assert stopped.pid is None
    loaded_stopped = load_instant_app_runtime(repo, "mentor-web-app")
    assert loaded_stopped is not None
    assert loaded_stopped.status == "stopped"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
