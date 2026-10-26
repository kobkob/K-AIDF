# Extension: Words
# Description: Answer presentation questions (who are you, introduce yourself) without the LLM
# Version: 1.0.0
# Author: Kobkob LLC
# Entrypoints: prompt
# Topics: prompt, presentation, catalog, offline
"""Core extension: answers presentation questions from words.json, without calling the model.

A prompt matches an entry when one of its normalized patterns appears as whole words in the
normalized prompt, so accents, case and punctuation do not matter. "Quem é você?" matches the
pattern "quem e voce". Only general chat is intercepted; the mentor workflow is not.
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
            if re.search(rf"(?<!\w){re.escape(pattern)}(?!\w)", normalized):
                return entry.reply
    return None


def intercept(prompt: str) -> str | None:
    return match_reply(prompt, load_catalog())


def register(hooks) -> None:
    hooks.add_prompt_interceptor(intercept)
