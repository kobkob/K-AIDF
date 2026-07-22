from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.serving import BaseWSGIServer, make_server

from .i18n import _
from .maturity import phase_progress, phase_snapshot
from .mentor import continue_mentor_workflow
from .project import read_project_status

STATIC_DIR = Path(__file__).resolve().parent / "webui_dist"

LogSink = Callable[[str], None]
ServerReadyCallback = Callable[[BaseWSGIServer], None]


def _status_payload(project_root: Path, repo_root: Path) -> dict:
    status = read_project_status(project_root, repo_root)
    current, total = phase_progress(status)
    return {
        "project_root": str(status.project_root),
        "repo_root": str(status.repo_root),
        "has_kaidf": status.has_kaidf,
        "pack_count": status.pack_count,
        "mentor_step_count": status.mentor_step_count,
        "mentor_pending_category": status.mentor_pending_category,
        "mentor_current_app_url": status.mentor_current_app_url,
        "current_phase": current,
        "total_phases": total,
        "phases": phase_snapshot(status),
    }


def create_app(project_root: Path, repo_root: Path, log_sink: LogSink | None = None) -> Flask:
    if not STATIC_DIR.is_dir():
        raise RuntimeError(
            f"Web UI static assets not found at {STATIC_DIR}. "
            "Run `npm run build` in agent-aidf/webui/ first."
        )

    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
    app.config["_server"] = None

    def log(line: str) -> None:
        if log_sink is not None:
            log_sink(line)

    @app.after_request
    def _log_request(response):
        if request.path.startswith("/api/"):
            log(f"{request.method} {request.path} -> {response.status_code}")
        return response

    @app.get("/api/status")
    def api_status():
        return jsonify(_status_payload(project_root, repo_root))

    @app.post("/api/mentor")
    def api_mentor():
        payload = request.get_json(silent=True) or {}
        answer = payload.get("answer") or None
        turn = continue_mentor_workflow(repo_root, answer=answer)
        return jsonify(
            {
                "message": turn.message,
                "pending_question": turn.state.pending_question,
                "current_app_id": turn.state.current_app_id,
                **_status_payload(project_root, repo_root),
            }
        )

    @app.post("/api/exit")
    def api_exit():
        server = app.config.get("_server")
        if server is not None:
            log(_("Exit requested from the web UI. Stopping the server..."))
            threading.Thread(target=server.shutdown, daemon=True).start()
        return jsonify({"ok": True})

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    return app


def run_webui(
    project_root: Path,
    repo_root: Path,
    host: str = "127.0.0.1",
    port: int = 8501,
    log_sink: LogSink | None = None,
    on_server_ready: ServerReadyCallback | None = None,
) -> None:
    """Serve the kob web UI until stopped via /api/exit, Ctrl+C, or an external shutdown() call."""
    app = create_app(project_root, repo_root, log_sink=log_sink)
    server = make_server(host, port, app)
    app.config["_server"] = server
    if on_server_ready is not None:
        on_server_ready(server)
    if log_sink is not None:
        log_sink(_("Web UI listening on http://{host}:{port}").format(host=host, port=port))
    try:
        server.serve_forever()
    finally:
        if log_sink is not None:
            log_sink(_("Web UI stopped."))
