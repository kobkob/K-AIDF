# Extension: Words
# Description: Answer presentation questions (who are you, introduce yourself) without the LLM
# Version: 1.0.0
# Author: Kobkob LLC
# Entrypoints: prompt
# Topics: prompt, presentation, catalog, offline
"""Core extension: answers presentation questions from words.json, without calling the model.

A prompt matches an entry when, after normalization (accents, case and punctuation do not matter),
the whole prompt is one of the entry's patterns. A short greeting may come before the pattern
("oi") and a short closing word after it ("mesmo", "por favor"). A pattern found in the middle of a
longer request does not match, so "traduza 'how are you'" still reaches the model. "Quem é você?"
matches the pattern "quem e voce". Only general chat is intercepted; the mentor workflow is not.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("words.json")
_NON_WORD = re.compile(r"[^a-z0-9]+")
# Normalized forms (see normalize) of the greetings that may precede a pattern, and of the closing
# words that may follow it. Anything else around the pattern means a real request, not a greeting.
_GREETING = r"(?:oi|ola|ei|hey|hi|hello|bom dia|boa tarde|boa noite|good morning|good evening)"
_CLOSING = r"(?:mesmo|por favor|please)"
_OPTIONAL_GREETING = rf"(?:{_GREETING} )?"
_OPTIONAL_CLOSING = rf"(?: {_CLOSING})?"


@dataclass(frozen=True)
class WordEntry:
    id: str
    patterns: tuple[str, ...]
    reply: str


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(_NON_WORD.sub(" ", ascii_only.casefold()).split())


def parse_catalog(data: dict) -> tuple[WordEntry, ...]:
    entries: list[WordEntry] = []
    for raw in data.get("entries", []):
        patterns = tuple(normalize(p) for p in raw.get("patterns", []) if normalize(p))
        reply = str(raw.get("reply", "")).strip()
        if not patterns or not reply:
            raise ValueError(f"entry {raw.get('id', '?')!r} needs patterns and a reply")
        entries.append(WordEntry(id=str(raw.get("id", "")), patterns=patterns, reply=reply))
    if not entries:
        raise ValueError("words.json has no entries")
    return tuple(entries)


@lru_cache(maxsize=1)
def load_catalog() -> tuple[WordEntry, ...]:
    return parse_catalog(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def match_reply(prompt: str, catalog: tuple[WordEntry, ...]) -> str | None:
    normalized = normalize(prompt)
    if not normalized:
        return None
    for entry in catalog:
        for pattern in entry.patterns:
            anchored = rf"{_OPTIONAL_GREETING}{re.escape(pattern)}{_OPTIONAL_CLOSING}"
            if re.fullmatch(anchored, normalized):
                return entry.reply
    return None


def intercept(prompt: str) -> str | None:
    return match_reply(prompt, load_catalog())


def register(hooks) -> None:
    hooks.add_prompt_interceptor(intercept)
