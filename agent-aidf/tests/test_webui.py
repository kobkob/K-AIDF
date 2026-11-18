from __future__ import annotations

import re
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent_aidf.webui as webui

PORT = 8501
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(webui, "resolve_mentor_repo_root", lambda _project_root: tmp_path)
    monkeypatch.setattr(webui, "_status_payload", lambda _project, _repo: {"yolo": False})
    turn = SimpleNamespace(
        message="next question",
        state=SimpleNamespace(pending_question="Why?", current_app_id=None),
        token_usage=None,
    )
    monkeypatch.setattr(webui, "continue_mentor_workflow", lambda _root, answer=None: turn)
    return webui.create_app(tmp_path, tmp_path, port=PORT)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def token(app) -> str:
    return app.config["API_TOKEN"]


def _mentor(client, *, token=None, base_url=BASE_URL, origin=None):
    headers = {}
    if token is not None:
        headers[webui.API_TOKEN_HEADER] = token
    if origin is not None:
        headers["Origin"] = origin
    return client.post("/api/mentor", base_url=base_url, headers=headers, json={"answer": None})


def _exit(client, *, token=None, base_url=BASE_URL, origin=None):
    headers = {}
    if token is not None:
        headers[webui.API_TOKEN_HEADER] = token
    if origin is not None:
        headers["Origin"] = origin
    return client.post("/api/exit", base_url=base_url, headers=headers)


# --- session bootstrap and token injection ---------------------------------


def _session(client, token: str):
    """Trade the printed URL's token for the session cookie, as the browser does."""
    response = client.get(f"/?token={token}", base_url=BASE_URL)
    assert response.status_code == 303
    return response


def test_index_without_session_returns_401_and_no_token(client, token):
    response = client.get("/", base_url=BASE_URL)

    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication_required"}
    assert token not in response.get_data(as_text=True)


def test_index_with_wrong_bootstrap_token_is_forbidden(client):
    response = client.get("/?token=" + "0" * 64, base_url=BASE_URL)

    assert response.status_code == 403
    assert response.get_json() == {"error": "invalid_token"}


def test_bootstrap_sets_httponly_strict_cookie_and_redirects_clean(client, token):
    response = _session(client, token)

    assert response.headers["Location"] == "/"
    cookie = response.headers["Set-Cookie"]
    assert f"{webui.SESSION_COOKIE}={token}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie


def test_index_with_session_embeds_per_process_token(client, app, token):
    _session(client, token)

    response = client.get("/", base_url=BASE_URL)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = response.get_data(as_text=True)
    assert webui.API_TOKEN_PLACEHOLDER not in body
    match = re.search(r'<meta name="kaidf-api-token" content="([0-9a-f]+)"', body)
    assert match is not None
    assert match.group(1) == app.config["API_TOKEN"]
    assert len(match.group(1)) == 64


def test_session_cookie_from_another_instance_is_rejected(tmp_path: Path, token):
    other = webui.create_app(tmp_path, tmp_path, port=PORT).test_client()
    other.set_cookie(webui.SESSION_COOKIE, token, domain="127.0.0.1")

    response = other.get("/api/status", base_url=BASE_URL)

    assert response.status_code == 403


def test_token_differs_between_app_instances(tmp_path: Path):
    first = webui.create_app(tmp_path, tmp_path, port=PORT)
    second = webui.create_app(tmp_path, tmp_path, port=PORT)

    assert first.config["API_TOKEN"] != second.config["API_TOKEN"]


# --- POST /api/mentor ------------------------------------------------------


def test_mentor_returns_200_with_valid_token(client, token):
    response = _mentor(client, token=token)

    assert response.status_code == 200
    assert response.get_json()["message"] == "next question"


def test_mentor_returns_401_without_token(client):
    response = _mentor(client)

    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication_required"}


def test_mentor_returns_403_with_wrong_token(client):
    response = _mentor(client, token="not-the-token")

    assert response.status_code == 403
    assert response.get_json() == {"error": "invalid_token"}


def test_mentor_rejects_foreign_host_even_with_valid_token(client, token):
    response = _mentor(client, token=token, base_url="http://evil.example:8501")

    assert response.status_code == 403
    assert response.get_json() == {"error": "forbidden_host"}


def test_mentor_rejects_foreign_origin_even_with_valid_token(client, token):
    response = _mentor(client, token=token, origin="http://evil.example")

    assert response.status_code == 403
    assert response.get_json() == {"error": "forbidden_origin"}


def test_mentor_accepts_matching_local_origin(client, token):
    response = _mentor(client, token=token, origin=BASE_URL)

    assert response.status_code == 200


# --- POST /api/exit --------------------------------------------------------


def test_exit_returns_200_with_valid_token(client, token):
    response = _exit(client, token=token)

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_exit_returns_401_without_token(client):
    response = _exit(client)

    assert response.status_code == 401


def test_exit_returns_403_with_wrong_token(client):
    response = _exit(client, token="not-the-token")

    assert response.status_code == 403


def test_exit_rejects_foreign_host(client, token):
    response = _exit(client, token=token, base_url="http://evil.example:8501")

    assert response.status_code == 403


# --- Host / Origin on read routes ------------------------------------------


def test_status_rejects_dns_rebinding_host(client):
    response = client.get("/api/status", base_url="http://attacker.example:8501")

    assert response.status_code == 403


def test_host_with_wrong_port_is_rejected(client, token):
    response = _mentor(client, token=token, base_url="http://127.0.0.1:9999")

    assert response.status_code == 403


def test_localhost_hostname_is_accepted(client, token):
    response = _mentor(client, token=token, base_url=f"http://localhost:{PORT}")

    assert response.status_code == 200


def test_without_known_port_any_loopback_port_is_accepted(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(webui, "_status_payload", lambda _project, _repo: {})
    app = webui.create_app(tmp_path, tmp_path)
    client = app.test_client()
    headers = {webui.API_TOKEN_HEADER: app.config["API_TOKEN"]}

    response = client.get("/api/status", base_url="http://127.0.0.1:12345", headers=headers)

    assert response.status_code == 200


# --- GET /api/status requires a session or the token -----------------------


def test_status_without_credentials_returns_401(client):
    response = client.get("/api/status", base_url=BASE_URL)

    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication_required"}


def test_status_with_wrong_header_returns_403(client):
    response = client.get(
        "/api/status", base_url=BASE_URL, headers={webui.API_TOKEN_HEADER: "nope"}
    )

    assert response.status_code == 403


def test_status_with_session_cookie_returns_200(client, token):
    _session(client, token)

    response = client.get("/api/status", base_url=BASE_URL)

    assert response.status_code == 200


def test_status_with_token_header_returns_200(client, token):
    response = client.get("/api/status", base_url=BASE_URL, headers={webui.API_TOKEN_HEADER: token})

    assert response.status_code == 200


def test_status_with_wrong_session_cookie_returns_403(client):
    client.set_cookie(webui.SESSION_COOKIE, "0" * 64, domain="127.0.0.1")

    response = client.get("/api/status", base_url=BASE_URL)

    assert response.status_code == 403


# --- log redaction ----------------------------------------------------------


def test_werkzeug_log_redacts_the_bootstrap_token(app, token, caplog):
    import logging

    logger = logging.getLogger("werkzeug")
    with caplog.at_level(logging.INFO, logger="werkzeug"):
        logger.info('127.0.0.1 - - "GET /?token=%s HTTP/1.1" 303 -', token)

    assert token not in caplog.text
    assert "token=<redacted>" in caplog.text


# --- header logo ------------------------------------------------------------


def test_kob_logo_is_served_as_png(client):
    response = client.get("/brand/kob-logo.png", base_url=BASE_URL)

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data.startswith(b"\x89PNG\r\n\x1a\n")


def test_kob_logo_route_still_applies_host_guard(client):
    response = client.get("/brand/kob-logo.png", base_url="http://evil.example")

    assert response.status_code == 403


def test_kob_logo_asset_ships_inside_the_package():
    assert (webui.UI_ASSETS_DIR / webui.KOB_LOGO_FILENAME).is_file()


def test_built_bundle_references_the_kob_logo():
    bundles = list((webui.STATIC_DIR / "assets").glob("*.js"))

    assert bundles, "run `npm run build` in agent-aidf/webui/"
    assert any(b"/brand/kob-logo.png" in path.read_bytes() for path in bundles)


# --- concurrency: the real run_webui server --------------------------------


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _run_webui_in_thread(tmp_path: Path):
    ready = threading.Event()
    holder: dict = {}

    def on_ready(server):
        holder["server"] = server
        ready.set()

    port = _free_port()
    thread = threading.Thread(
        target=webui.run_webui,
        args=(tmp_path, tmp_path),
        kwargs={"host": "127.0.0.1", "port": port, "on_server_ready": on_ready},
        daemon=True,
    )
    thread.start()
    assert ready.wait(10), "run_webui never reported a ready server"
    server = holder["server"]
    return server, server.app.config["API_TOKEN"], f"http://127.0.0.1:{port}", thread


def _http_status(method: str, url: str, token: str, body: bytes | None = None) -> int:
    request = urllib.request.Request(url, method=method, data=body)
    request.add_header(webui.API_TOKEN_HEADER, token)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


@pytest.fixture
def busy_server(tmp_path: Path, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def slow_mentor(_root, answer=None):
        entered.set()
        release.wait(15)
        return SimpleNamespace(
            message="late",
            state=SimpleNamespace(pending_question=None, current_app_id=None),
            token_usage=None,
        )

    monkeypatch.setattr(webui, "resolve_mentor_repo_root", lambda _project_root: tmp_path)
    monkeypatch.setattr(webui, "continue_mentor_workflow", slow_mentor)
    monkeypatch.setattr(webui, "_status_payload", lambda _project, _repo: {"yolo": False})
    server, token, base, thread = _run_webui_in_thread(tmp_path)
    mentor = threading.Thread(
        target=_http_status,
        args=("POST", f"{base}/api/mentor", token, b'{"answer": null}'),
        daemon=True,
    )
    mentor.start()
    assert entered.wait(10), "the mentor call never started"
    yield base, token
    release.set()
    server.shutdown()
    thread.join(timeout=10)


def test_status_answers_while_a_mentor_call_is_in_flight(busy_server):
    base, token = busy_server

    started = time.monotonic()
    status = _http_status("GET", f"{base}/api/status", token)
    elapsed = time.monotonic() - started

    assert status == 200
    assert elapsed < 5, f"/api/status waited {elapsed:.1f}s behind a mentor call"


def test_exit_is_not_queued_behind_a_mentor_call(busy_server):
    base, token = busy_server

    started = time.monotonic()
    status = _http_status("POST", f"{base}/api/exit", token)
    elapsed = time.monotonic() - started

    assert status == 200
    assert elapsed < 5, f"/api/exit waited {elapsed:.1f}s behind a mentor call"
