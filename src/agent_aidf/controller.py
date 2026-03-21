from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib import error, request

from .repo import Document, find_documents, list_packs, load_documents, resolve_repo_root

class ChatController(Protocol):
    def chat(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class NullChatController:
    message: str = "AI chat controller is not configured yet."

    def chat(self, prompt: str, repo_root: str | Path | None = None) -> str:
        return f"{self.message} Prompt received: {prompt}"


@dataclass
class OpenAIResponsesController:
    api_key: str
    model: str = "gpt-5"
    base_url: str = "https://api.openai.com/v1"
    instructions: str = (
        "You are the AI controller for a terminal-first K-AIDF agent. "
        "Use the provided repository metadata and document excerpts to answer pragmatically."
    )
    previous_response_id: str | None = None

    def chat(self, prompt: str, repo_root: str | Path | None = None) -> str:
        repo = resolve_repo_root(repo_root)
        payload = self._build_payload(prompt, repo)
        http_request = request.Request(
            url=f"{self.base_url.rstrip('/')}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI API request failed: {exc.reason}") from exc

        self.previous_response_id = data.get("id")
        text = self._extract_output_text(data)
        if not text:
            raise RuntimeError("OpenAI API returned no text output.")
        return text

    def _build_payload(self, prompt: str, repo_root: Path) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "input": [
                {"role": "developer", "content": self.instructions},
                {"role": "user", "content": _build_context_prompt(repo_root, prompt)},
            ],
        }
        if self.previous_response_id:
            payload["previous_response_id"] = self.previous_response_id
        return payload

    @staticmethod
    def _extract_output_text(data: dict[str, object]) -> str:
        output = data.get("output")
        if not isinstance(output, list):
            return ""
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                if content_item.get("type") == "output_text":
                    text = content_item.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
        return "\n".join(chunk for chunk in chunks if chunk).strip()


def build_controller() -> ChatController:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return NullChatController()
    return OpenAIResponsesController(
        api_key=api_key,
        model=os.environ.get("OPENAI_MODEL", "gpt-5"),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        instructions=os.environ.get(
            "AIDF_CHAT_INSTRUCTIONS",
            "You are the AI controller for a terminal-first K-AIDF agent. "
            "Use the repository metadata and excerpts provided to answer pragmatically.",
        ),
    )


def _build_context_prompt(repo_root: Path, prompt: str) -> str:
    documents = load_documents(repo_root)
    packs = ", ".join(list_packs(documents)) or "none"
    matches = find_documents(documents, prompt)[:5]
    lines = [
        f"Repository root: {repo_root}",
        f"Detected packs: {packs}",
        f"Document count: {len(documents)}",
        "",
        "Relevant documents:",
    ]
    if not matches:
        lines.append("- none")
    else:
        for doc in matches:
            lines.append(f"- {doc.path} :: {doc.title}")
            if doc.pack:
                lines.append(f"  pack={doc.pack}")
            excerpt = " ".join(doc.body.splitlines()[:3]).strip()
            if excerpt:
                lines.append(f"  excerpt={excerpt[:280]}")
    lines.extend(["", "User prompt:", prompt])
    return "\n".join(lines)
