"""kob scan ingests the allowlisted URL sources of model-setup.json. No test touches the network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_aidf.scan import extract


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text('def greet():\n    return "hi"\n', encoding="utf-8")
    (root / ".kaidf").mkdir()
    return root


def _write_profile(root: Path, hosts: list[str], urls: list[str]) -> None:
    profile = {
        "name": "demo",
        "mood": "pragmatic-auditor",
        "rag": {
            "enabled": True,
            "allowed_url_hosts": hosts,
            "sources": [{"url": url} for url in urls],
        },
    }
    (root / ".kaidf" / "model-setup.json").write_text(json.dumps(profile), encoding="utf-8")


def test_an_allowlisted_url_is_fetched_and_chunked_into_the_corpus(
    project: Path, monkeypatch
) -> None:
    requested: list[str] = []

    def fake_urlopen(url, timeout=None):
        requested.append(url)
        return _FakeResponse("# Guia\n\n## Governança\n\nO time revisa cada fase.\n".encode())

    monkeypatch.setattr("agent_aidf.model_setup.urllib.request.urlopen", fake_urlopen)
    _write_profile(project, ["docs.example.org"], ["https://docs.example.org/guia.md"])

    plan = extract(project, project / ".kaidf")

    assert requested == ["https://docs.example.org/guia.md"]
    url_chunks = [chunk for chunk in plan.chunks if chunk.source.startswith("https://")]
    assert any("revisa cada fase" in chunk.text for chunk in url_chunks)
    assert plan.chunk_digests["https://docs.example.org/guia.md"]


def test_a_url_outside_the_allowlist_is_never_requested(project: Path, monkeypatch) -> None:
    def fail_urlopen(url, timeout=None):
        raise AssertionError(f"requested {url}")

    monkeypatch.setattr("agent_aidf.model_setup.urllib.request.urlopen", fail_urlopen)
    _write_profile(project, ["docs.example.org"], ["https://evil.example.net/x.md"])

    plan = extract(project, project / ".kaidf")

    assert not any(chunk.source.startswith("https://") for chunk in plan.chunks)
    assert any("not in allowed_url_hosts" in note for note in plan.notes)


def test_without_a_profile_no_url_is_requested_and_nothing_is_noted(project: Path) -> None:
    plan = extract(project, project / ".kaidf")

    assert not any("URL sources" in note for note in plan.notes)
    assert not any(chunk.source.startswith("https://") for chunk in plan.chunks)


def test_an_invalid_profile_is_noted_and_does_not_stop_the_scan(project: Path) -> None:
    (project / ".kaidf" / "model-setup.json").write_text("{not json", encoding="utf-8")

    plan = extract(project, project / ".kaidf")

    assert any("URL sources skipped" in note for note in plan.notes)
    assert plan.files_seen > 0
