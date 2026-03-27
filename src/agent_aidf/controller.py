from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Protocol
from urllib import error, request

from .instant_apps import list_instant_apps, load_instant_app_runtime
from .mentor import load_mentor_state
from .repo import Document, list_packs, load_documents, resolve_repo_root

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
        "You are the AI controller for a terminal-first K-AIDF mentor agent. "
        "Act as a pragmatic architect for creators working inside a project with a local .kaidf repository. "
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
            "You are the AI controller for a terminal-first K-AIDF mentor agent. "
            "Act as a pragmatic architect for creators working inside a project with a local .kaidf repository. "
            "Use the repository metadata and excerpts provided to answer pragmatically.",
        ),
    )


def _build_context_prompt(repo_root: Path, prompt: str) -> str:
    documents = load_documents(repo_root)
    packs = ", ".join(list_packs(documents)) or "none"
    instant_apps = list_instant_apps(repo_root)
    mentor_state = load_mentor_state(repo_root)
    current_runtime = load_instant_app_runtime(repo_root, mentor_state.current_app_id) if mentor_state.current_app_id else None
    matches = select_context_documents(documents, prompt, limit=5)
    lines = [
        f"Repository root: {repo_root}",
        f"Detected packs: {packs}",
        f"Document count: {len(documents)}",
        f"Persistent instant apps: {', '.join(app.app_id for app in instant_apps) or 'none'}",
        f"Mentor step count: {mentor_state.step_count}",
        f"Mentor pending category: {mentor_state.pending_category or 'none'}",
        f"Mentor current app: {mentor_state.current_app_id or 'none'}",
        (
            f"Mentor current app URL: http://127.0.0.1:{current_runtime.port}"
            if current_runtime and current_runtime.status == "running" and current_runtime.port
            else "Mentor current app URL: none"
        ),
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
            if doc.doctrine_category:
                lines.append(f"  doctrine_category={doc.doctrine_category}")
            if doc.ethical_domain:
                lines.append(f"  ethical_domain={doc.ethical_domain}")
            if doc.maturity_level:
                lines.append(f"  maturity_level={doc.maturity_level}")
            if doc.assessment_type:
                lines.append(f"  assessment_type={doc.assessment_type}")
            if doc.risk_type:
                lines.append(f"  risk_type={doc.risk_type}")
            excerpt = " ".join(doc.body.splitlines()[:3]).strip()
            if excerpt:
                lines.append(f"  excerpt={excerpt[:280]}")
    lines.extend(["", "User prompt:", prompt])
    return "\n".join(lines)


def select_context_documents(documents: list[Document], prompt: str, limit: int = 5) -> list[Document]:
    prompt_norm = prompt.strip().casefold()
    if not prompt_norm:
        return []
    terms = _prompt_terms(prompt_norm)
    scored: list[tuple[int, Document]] = []
    for doc in documents:
        score = _score_document(doc, prompt_norm, terms)
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda item: (-item[0], item[1].path))
    return [doc for _, doc in scored[:limit]]


def _prompt_terms(prompt_norm: str) -> list[str]:
    return [term for term in re.split(r"[^a-z0-9]+", prompt_norm.replace("-", " ")) if len(term) >= 3]


def _score_document(doc: Document, prompt_norm: str, terms: list[str]) -> int:
    haystack = "\n".join(
        [
            doc.id,
            doc.path,
            doc.title,
            doc.doctrine_category,
            doc.pack or "",
            doc.ethical_domain or "",
            doc.maturity_level or "",
            doc.assessment_type or "",
            doc.risk_type or "",
            doc.body,
        ]
    ).casefold()
    score = 0
    if prompt_norm in haystack:
        score += 80
    score += sum(20 for term in terms if term in haystack)
    if prompt_norm in doc.title.casefold():
        score += 80
    if prompt_norm in doc.path.casefold():
        score += 60
    if doc.pack and prompt_norm == doc.pack.casefold():
        score += 220
    if doc.ethical_domain and prompt_norm == doc.ethical_domain.casefold():
        score += 220
    if doc.maturity_level and prompt_norm == doc.maturity_level.casefold():
        score += 220
    if doc.assessment_type and prompt_norm == doc.assessment_type.casefold():
        score += 140
    if doc.risk_type and prompt_norm == doc.risk_type.casefold():
        score += 180
    if doc.canonical_doctrine:
        score += 40
    if doc.pack == "ethical-model":
        score += _ethical_pack_bias(doc, prompt_norm, terms)
    if doc.pack == "maturity-model":
        score += _maturity_pack_bias(doc, prompt_norm, terms)
    return score


def _ethical_pack_bias(doc: Document, prompt_norm: str, terms: list[str]) -> int:
    score = 0
    if "ethical" in terms or "ethics" in terms or prompt_norm == "ethical-model":
        score += 180 if doc.path == "docs/20-ethical-model/README.md" else 40
    if "transparency" in terms and doc.ethical_domain == "transparency":
        score += 220
    if "privacy" in terms and (doc.ethical_domain == "data-protection" or doc.control_type == "checklist"):
        score += 180
    if "validation" in terms and doc.ethical_domain == "human-validation":
        score += 180
    if "bias" in terms and doc.risk_type == "bias-and-harm":
        score += 200
    return score


def _maturity_pack_bias(doc: Document, prompt_norm: str, terms: list[str]) -> int:
    score = 0
    if "maturity" in terms:
        score += 100
    if "managed" in terms and doc.maturity_level == "managed":
        score += 220
    if "experimental" in terms and doc.maturity_level == "experimental":
        score += 220
    if "checklist" in terms and doc.assessment_type == "checklist":
        score += 160
    if prompt_norm == "maturity-model" and doc.path == "docs/10-maturity-model/README.md":
        score += 240
    return score
