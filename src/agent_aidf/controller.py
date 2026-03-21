from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ChatController(Protocol):
    def chat(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class NullChatController:
    message: str = "AI chat controller is not configured yet."

    def chat(self, prompt: str) -> str:
        return f"{self.message} Prompt received: {prompt}"
