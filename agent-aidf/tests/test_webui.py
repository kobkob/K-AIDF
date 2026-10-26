from __future__ import annotations

import re
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


# --- token injection -------------------------------------------------------


def test_index_embeds_per_process_token(client, app):
    response = client.get("/", base_url=BASE_URL)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = response.get_data(as_text=True)
    assert webui.API_TOKEN_PLACEHOLDER not in body
    match = re.search(r'<meta name="kaidf-api-token" content="([0-9a-f]+)"', body)
    assert match is not None
    assert match.group(1) == app.config["API_TOKEN"]
    assert len(match.group(1)) == 64


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

    response = client.get("/api/status", base_url="http://127.0.0.1:12345")

    assert response.status_code == 200


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
