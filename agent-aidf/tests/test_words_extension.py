from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

import agent_aidf.controller as controller_module
from agent_aidf.controller import MENTOR_CHAT_INSTRUCTIONS, OllamaChatController
from agent_aidf.extensions.extension_loader import (
    BUILTIN_EXTENSIONS_DIR,
    load_extensions,
    reset_active_registry,
)
from agent_aidf.prompt_hooks import intercept_prompt

words = importlib.import_module("agent_aidf.ext.words.main")


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def read(self) -> bytes:
        return self._body


@pytest.fixture
def words_loaded():
    registry = load_extensions(roots=[BUILTIN_EXTENSIONS_DIR], disabled=[])
    assert "words" in {ext.id for ext in registry.loaded}
    yield
    reset_active_registry()


def test_normalize_drops_accents_case_and_punctuation() -> None:
    assert words.normalize("Quem é você?") == "quem e voce"
    assert words.normalize("  Apresente-se!  ") == "apresente se"


@pytest.mark.parametrize(
    "prompt",
    [
        "Quem é você?",
        "quem e voce",
        "Oi, quem é você mesmo?",
        "How are you?",
        "Introduce yourself",
        "who are you",
        "Como você está?",
        "O que é o kob?",
    ],
)
def test_matches_presentation_phrases(prompt: str, words_loaded) -> None:
    reply = intercept_prompt(prompt)

    assert reply is not None
    assert "kob" in reply


def test_portuguese_prompt_gets_portuguese_reply(words_loaded) -> None:
    assert "Eu sou o kob" in intercept_prompt("Quem é você?")


def test_english_prompt_gets_english_reply(words_loaded) -> None:
    assert intercept_prompt("Introduce yourself").startswith("I am kob")


@pytest.mark.parametrize(
    "prompt",
    [
        "quem e voceee",  # whole-word match only
        "explique a doutrina do K-AIDF",
        "gere um contrato para a fase 2",
        "",
        "   ",
    ],
)
def test_unrelated_prompts_pass_through(prompt: str, words_loaded) -> None:
    assert intercept_prompt(prompt) is None


def test_catalog_entries_are_well_formed() -> None:
    data = json.loads((BUILTIN_EXTENSIONS_DIR / "words" / "words.json").read_text("utf-8"))
    catalog = words.parse_catalog(data)

    assert len(catalog) >= 4
    assert all(entry.patterns and entry.reply for entry in catalog)


def test_catalog_rejects_entry_without_reply() -> None:
    with pytest.raises(ValueError, match="needs patterns and a reply"):
        words.parse_catalog({"entries": [{"id": "x", "patterns": ["oi"], "reply": ""}]})


def test_catalog_rejects_empty_catalog() -> None:
    with pytest.raises(ValueError, match="no entries"):
        words.parse_catalog({"entries": []})


def test_intercepted_prompt_never_reaches_the_model(tmp_path: Path, monkeypatch, words_loaded):
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    calls: list[object] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return _FakeResponse(json.dumps({"response": "model said hi"}).encode("utf-8"))

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OllamaChatController(model="olmo2:7b-1124-instruct-q4_K_M", last_usage={"a": 1})

    reply = controller.chat("Quem é você?", tmp_path)

    assert reply.startswith("Eu sou o kob")
    assert calls == []
    assert controller.last_usage is None


def test_ordinary_prompt_still_reaches_the_model(tmp_path: Path, monkeypatch, words_loaded):
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    calls: list[object] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return _FakeResponse(json.dumps({"response": "a real answer"}).encode("utf-8"))

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OllamaChatController(model="olmo2:7b-1124-instruct-q4_K_M")

    assert controller.chat("explique a doutrina", tmp_path).startswith("a real answer")
    assert len(calls) == 1


def test_mentor_answers_are_not_intercepted(tmp_path: Path, monkeypatch, words_loaded):
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    calls: list[object] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return _FakeResponse(json.dumps({"response": "mentor reply"}).encode("utf-8"))

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OllamaChatController(model="olmo2:7b-1124-instruct-q4_K_M")

    reply = controller.chat("Quem é você?", tmp_path, instructions=MENTOR_CHAT_INSTRUCTIONS)

    assert reply.startswith("mentor reply")
    assert len(calls) == 1
