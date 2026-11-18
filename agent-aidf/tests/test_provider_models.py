"""`kob models`: resolve the active provider, list its /v1/models, fail in one line offline."""

from __future__ import annotations

import importlib
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agent_aidf import provider_models as pm

cli_main = importlib.import_module("agent_aidf.cli.main")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        return

    def do_GET(self):  # noqa: N802 - stdlib name
        server = self.server
        server.seen.append(dict(self.headers.items()))
        if server.delay:
            time.sleep(server.delay)
        raw = server.body if isinstance(server.body, bytes) else json.dumps(server.body).encode()
        self.send_response(server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def provider(monkeypatch):
    """A local OpenAI-compatible server. Tests set .status, .body or .delay before the call."""
    for var in (
        "AIDF_CHAT_PROVIDER",
        "OLLAMA_HOST",
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "AIDF_MODEL",
        "AIDF_OLLAMA_MODEL",
        "OLLAMA_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    server.status = 200
    server.body = {"object": "list", "data": [{"id": "olmo2:7b"}, {"id": "llama3:8b"}]}
    server.delay = 0
    server.seen = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


def _base(server) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}"


def _refused_url() -> str:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return f"http://127.0.0.1:{port}/v1/models"


# --- URL and provider resolution ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("http://localhost:11434", "http://localhost:11434/v1/models"),
        ("http://localhost:11434/", "http://localhost:11434/v1/models"),
        ("https://api.openai.com/v1", "https://api.openai.com/v1/models"),
        ("https://api.openai.com/v1/", "https://api.openai.com/v1/models"),
    ],
)
def test_models_url_accepts_bases_with_or_without_v1(base: str, expected: str):
    assert pm.models_url(base) == expected


def test_default_provider_is_local_ollama(provider):
    endpoint = pm.provider_endpoint()

    assert endpoint.provider == "ollama"
    assert endpoint.base_url == "http://localhost:11434"
    assert endpoint.api_key is None
    assert endpoint.active_model == "olmo2:7b-1124-instruct-q4_K_M"


def test_ollama_host_and_model_come_from_the_environment(provider, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://gpu-box:11434")
    monkeypatch.setenv("AIDF_MODEL", "llama3:8b")

    endpoint = pm.provider_endpoint()

    assert endpoint.base_url == "http://gpu-box:11434"
    assert endpoint.active_model == "llama3:8b"


def test_openai_provider_uses_its_base_url_key_and_model(provider, monkeypatch):
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5-mini")

    endpoint = pm.provider_endpoint()

    assert endpoint.provider == "openai"
    assert endpoint.base_url == "https://proxy.example/v1"
    assert endpoint.api_key == "sk-test"
    assert endpoint.active_model == "gpt-5-mini"


def test_provider_none_has_nothing_to_list(provider, monkeypatch):
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "none")

    with pytest.raises(pm.ModelsUnavailableError, match="nothing to list"):
        pm.provider_endpoint()


# --- listing ------------------------------------------------------------------------------------


def test_lists_the_model_ids_sorted_and_without_duplicates(provider):
    provider.body = {"data": [{"id": "b"}, {"id": "a"}, {"id": "a"}, {"object": "x"}]}

    assert pm.fetch_model_ids(f"{_base(provider)}/v1/models") == ["a", "b"]


def test_bearer_token_is_sent_only_when_a_key_is_given(provider):
    pm.fetch_model_ids(f"{_base(provider)}/v1/models", api_key="sk-test")
    pm.fetch_model_ids(f"{_base(provider)}/v1/models")

    assert provider.seen[0].get("Authorization") == "Bearer sk-test"
    assert "Authorization" not in provider.seen[1]


def test_list_provider_models_reports_the_active_model(provider, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", _base(provider))
    monkeypatch.setenv("AIDF_MODEL", "llama3:8b")

    listing = pm.list_provider_models()

    assert listing.provider == "ollama"
    assert listing.active_model == "llama3:8b"
    assert listing.models == ["llama3:8b", "olmo2:7b"]


@pytest.mark.parametrize(
    ("status", "text"),
    [(401, "refused the request"), (403, "HTTP 403"), (500, "HTTP 500")],
)
def test_http_errors_become_a_plain_message(provider, status: int, text: str):
    provider.status = status

    with pytest.raises(pm.ModelsUnavailableError, match=text):
        pm.fetch_model_ids(f"{_base(provider)}/v1/models")


def test_a_non_json_answer_is_reported(provider):
    provider.body = b"<html>proxy</html>"

    with pytest.raises(pm.ModelsUnavailableError, match="did not return JSON"):
        pm.fetch_model_ids(f"{_base(provider)}/v1/models")


def test_a_json_answer_without_a_model_list_is_reported(provider):
    provider.body = {"error": "nope"}

    with pytest.raises(pm.ModelsUnavailableError, match="did not return a model list"):
        pm.fetch_model_ids(f"{_base(provider)}/v1/models")


def test_a_slow_provider_times_out_quickly(provider):
    provider.delay = 1.0

    with pytest.raises(pm.ModelsUnavailableError, match="did not answer within 0.2s"):
        pm.fetch_model_ids(f"{_base(provider)}/v1/models", timeout=0.2)


def test_an_unreachable_provider_is_one_plain_message(provider):
    with pytest.raises(pm.ModelsUnavailableError, match="not reachable"):
        pm.fetch_model_ids(_refused_url(), timeout=2)


# --- the CLI ------------------------------------------------------------------------------------


def test_kob_models_marks_the_active_model(provider, monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_HOST", _base(provider))
    monkeypatch.setenv("AIDF_MODEL", "olmo2:7b")

    assert cli_main._run_cli(["models"]) == 0

    out = capsys.readouterr().out
    assert "ollama" in out
    assert "olmo2:7b" in out and "llama3:8b" in out
    active_line = next(line for line in out.splitlines() if "olmo2:7b" in line)
    assert "(active)" in active_line
    assert "(active)" not in next(line for line in out.splitlines() if "llama3:8b" in line)


def test_kob_models_json_is_machine_readable(provider, monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_HOST", _base(provider))
    monkeypatch.setenv("AIDF_MODEL", "olmo2:7b")

    assert cli_main._run_cli(["models", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "provider": "ollama",
        "base_url": _base(provider),
        "active_model": "olmo2:7b",
        "models": ["llama3:8b", "olmo2:7b"],
    }


def test_kob_models_warns_when_the_active_model_is_missing(provider, monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_HOST", _base(provider))
    monkeypatch.setenv("AIDF_MODEL", "not-pulled:1b")

    assert cli_main._run_cli(["models"]) == 0

    assert "not-pulled:1b is not on this provider" in capsys.readouterr().out


def test_kob_models_offline_is_one_line_and_exit_one(monkeypatch, capsys):
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", _refused_url().rsplit("/v1/models", 1)[0])

    assert cli_main._run_cli(["models"]) == 1

    captured = capsys.readouterr()
    assert captured.err.startswith("error: The provider is not reachable")
    assert "Traceback" not in captured.err + captured.out


def test_kob_models_json_offline_reports_the_error_in_json(monkeypatch, capsys):
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "none")

    assert cli_main._run_cli(["models", "--json"]) == 1

    assert "nothing to list" in json.loads(capsys.readouterr().out)["error"]
