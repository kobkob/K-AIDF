from __future__ import annotations

import hmac
import html
import secrets
import threading
import time
from functools import wraps
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from flask import Flask, Response, jsonify, request
from werkzeug.serving import BaseWSGIServer, make_server

from .i18n import _
from .maturity import phase_progress, phase_snapshot
from .mentor import continue_mentor_workflow
from .project import MentorNotInitializedError, read_project_status, resolve_mentor_repo_root
from .tools import is_yolo_enabled

STATIC_DIR = Path(__file__).resolve().parent / "webui_dist"

API_TOKEN_HEADER = "X-KAIDF-Token"
API_TOKEN_PLACEHOLDER = "__KAIDF_API_TOKEN__"
LOCAL_HOSTNAMES = frozenset({"127.0.0.1", "localhost"})

LogSink = Callable[[str], None]
ServerReadyCallback = Callable[[BaseWSGIServer], None]


def _host_allowed(host_header: str, port: int | None) -> bool:
    """Accept only loopback hostnames (DNS-rebinding guard), on this server's port when known."""
    name, sep, host_port = host_header.partition(":")
    if name not in LOCAL_HOSTNAMES:
        return False
    return port is None or (bool(sep) and host_port == str(port))


def _origin_allowed(origin: str, port: int | None) -> bool:
    parts = urlsplit(origin)
    return parts.scheme == "http" and _host_allowed(parts.netloc, port)


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
        "yolo": is_yolo_enabled(),
    }


def create_app(
    project_root: Path,
    repo_root: Path,
    log_sink: LogSink | None = None,
    port: int | None = None,
) -> Flask:
    if not STATIC_DIR.is_dir():
        raise RuntimeError(
            f"Web UI static assets not found at {STATIC_DIR}. "
            "Run `npm run build` in agent-aidf/webui/ first."
        )

    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
    app.config["_server"] = None
    # Per-process secret: the served page embeds it, and every state-changing
    # request must echo it back in API_TOKEN_HEADER. Never persisted.
    api_token = secrets.token_hex(32)
    app.config["API_TOKEN"] = api_token

    def log(line: str) -> None:
        if log_sink is not None:
            log_sink(line)

    @app.before_request
    def _check_host_and_origin():
        # Host must be loopback: a DNS-rebinding page resolves to 127.0.0.1 but keeps its own Host.
        if not _host_allowed(request.host, port):
            return jsonify({"error": "forbidden_host"}), 403
        origin = request.headers.get("Origin")
        if origin is not None and not _origin_allowed(origin, port):
            return jsonify({"error": "forbidden_origin"}), 403
        return None

    def require_api_token(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            provided = request.headers.get(API_TOKEN_HEADER)
            if provided is None:
                return jsonify({"error": "authentication_required"}), 401
            if not hmac.compare_digest(provided.encode("utf-8"), api_token.encode("utf-8")):
                return jsonify({"error": "invalid_token"}), 403
            return view(*args, **kwargs)

        return wrapper

    @app.after_request
    def _log_request(response):
        if request.path.startswith("/api/"):
            log(f"{request.method} {request.path} -> {response.status_code}")
        return response

    @app.get("/api/status")
    def api_status():
        return jsonify(_status_payload(project_root, repo_root))

    @app.post("/api/mentor")
    @require_api_token
    def api_mentor():
        payload = request.get_json(silent=True) or {}
        answer = payload.get("answer") or None
        try:
            mentor_repo_root = resolve_mentor_repo_root(project_root)
        except MentorNotInitializedError as exc:
            return jsonify({"error": str(exc)}), 400
        start = time.monotonic()
        turn = continue_mentor_workflow(mentor_repo_root, answer=answer)
        return jsonify(
            {
                "message": turn.message,
                "pending_question": turn.state.pending_question,
                "current_app_id": turn.state.current_app_id,
                "elapsed_seconds": time.monotonic() - start,
                "token_usage": turn.token_usage,
                **_status_payload(project_root, repo_root),
            }
        )

    @app.post("/api/exit")
    @require_api_token
    def api_exit():
        server = app.config.get("_server")
        if server is not None:
            log(_("Exit requested from the web UI. Stopping the server..."))
            threading.Thread(target=server.shutdown, daemon=True).start()
        return jsonify({"ok": True})

    @app.get("/")
    def index():
        page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        page = page.replace(API_TOKEN_PLACEHOLDER, html.escape(api_token, quote=True))
        response = Response(page, mimetype="text/html")
        response.headers["Cache-Control"] = "no-store"
        return response

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
    app = create_app(project_root, repo_root, log_sink=log_sink, port=port)
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
