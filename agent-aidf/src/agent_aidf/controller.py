from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
import re
from typing import Protocol
from urllib import error, request

from .instant_apps import list_instant_apps, load_instant_app_runtime
from .mentor import load_mentor_state
from .repo import Document, list_packs, load_documents, resolve_repo_root

# Every ChatController implementation must honor this contract: chat() always
# returns a human-readable string and never raises, even on network failure,
# timeout, or a malformed upstream response. Callers (mentor.py, the TUI, kob
# shell, the web UI) rely on this and do not wrap .chat() in try/except.
_DEFAULT_HTTP_TIMEOUT_SECONDS = 300
_PACKAGE_DISTRIBUTION = "agent-aidf"


def _resolve_timeout_seconds() -> int:
    # Local inference speed varies wildly by machine (CPU-only vs GPU, model size,
    # prompt length) - AIDF_CHAT_TIMEOUT_SECONDS lets slower machines raise the ceiling
    # instead of hitting "did not respond within Ns" on otherwise-healthy requests.
    raw = os.environ.get("AIDF_CHAT_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_HTTP_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_HTTP_TIMEOUT_SECONDS
    return value if value > 0 else _DEFAULT_HTTP_TIMEOUT_SECONDS


_HTTP_TIMEOUT_SECONDS = _resolve_timeout_seconds()

# Shared behavior contract for every controller: kob converses openly, but has no
# file/shell tool access of its own in this mode - mutating actions always go through
# the mentor workflow's deterministic action layer, never through raw chat output.
DEFAULT_CHAT_INSTRUCTIONS = (
    "You are having an open, helpful conversation and may discuss any topic freely. "
    "When asked about KAIDF (the Knowledge and AI Development Framework), explain its concepts "
    "and process by drawing on the K-AIDF manifesto excerpt provided in your context - its "
    "principles, operational best practices, and implementation phases - rather than speaking "
    "generically. You cannot read or write files or run shell commands yourself right now; if the "
    "user asks you to create files, scaffold something, or take an action, tell them to continue "
    "with the mentor workflow so the change can be applied safely."
)


def _package_version() -> str:
    try:
        return metadata.version(_PACKAGE_DISTRIBUTION)
    except metadata.PackageNotFoundError:
        return "unknown"


def _kob_identity_line(model: str) -> str:
    return (
        f"You are kob, version {_package_version()}, running the {model} model. "
        "You are an ethical and humanized agent made by Kobkob LLC. If asked who or what you "
        "are, state exactly that identity."
    )


class ChatController(Protocol):
    def chat(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class NullChatController:
    message: str = "AI chat controller is not configured yet."
    last_usage: dict[str, int] | None = None

    def chat(self, prompt: str, repo_root: str | Path | None = None) -> str:
        return f"{self.message} Prompt received: {prompt}"


@dataclass
class OpenAIResponsesController:
    api_key: str
    model: str = "gpt-5"
    base_url: str = "https://api.openai.com/v1"
    instructions: str = DEFAULT_CHAT_INSTRUCTIONS
    previous_response_id: str | None = None
    last_usage: dict[str, int] | None = None

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
            with request.urlopen(http_request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            self.last_usage = None
            return f"OpenAI API error {exc.code}: {details}"
        except error.URLError as exc:
            self.last_usage = None
            return f"OpenAI API request failed: {exc.reason}"
        except TimeoutError:
            self.last_usage = None
            return (
                f"OpenAI API request timed out after {_HTTP_TIMEOUT_SECONDS}s. "
                "The model may be slow to respond right now - try again."
            )
        except json.JSONDecodeError as exc:
            self.last_usage = None
            return f"OpenAI API returned an unreadable response: {exc}"
        except OSError as exc:
            self.last_usage = None
            return f"OpenAI API request failed: {exc}"

        self.previous_response_id = data.get("id")
        usage = data.get("usage")
        self.last_usage = usage if isinstance(usage, dict) else None
        text = self._extract_output_text(data)
        return text if text else "OpenAI API returned no text output."

    def _build_payload(self, prompt: str, repo_root: Path) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "input": [
                {"role": "developer", "content": f"{_kob_identity_line(self.model)}\n\n{self.instructions}"},
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


@dataclass
class OllamaChatController:
    model: str = "olmo2:7b-1124-instruct-q4_K_M"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.2
    instructions: str = DEFAULT_CHAT_INSTRUCTIONS
    last_usage: dict[str, int] | None = None

    def chat(self, prompt: str, repo_root: str | Path | None = None) -> str:
        repo = resolve_repo_root(repo_root)
        full_prompt = f"{_kob_identity_line(self.model)}\n\n{self.instructions}\n\n{_build_context_prompt(repo, prompt)}"
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "options": {"temperature": self.temperature},
            "stream": False,
        }
        http_request = request.Request(
            url=f"{self.base_url.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            self.last_usage = None
            return f"Ollama API error {exc.code} from {self.base_url}: {details}"
        except error.URLError as exc:
            self.last_usage = None
            return (
                f"Could not reach local Ollama at {self.base_url} ({exc.reason}). "
                "Run 'make workspace-up' to start the local OLMo/Ollama stack."
            )
        except TimeoutError:
            # response.read() times out on its own, separately from URLError, when the
            # connection succeeds but the model takes longer than _HTTP_TIMEOUT_SECONDS
            # to finish generating - this previously crashed the whole TUI/shell process.
            self.last_usage = None
            return (
                f"Local Ollama at {self.base_url} did not respond within {_HTTP_TIMEOUT_SECONDS}s. "
                f"The model ({self.model}) may still be loading, or the prompt may be too long - try again."
            )
        except json.JSONDecodeError as exc:
            self.last_usage = None
            return f"Ollama at {self.base_url} returned an unreadable response: {exc}"
        except OSError as exc:
            self.last_usage = None
            return f"Could not reach local Ollama at {self.base_url}: {exc}"

        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")
        if isinstance(prompt_tokens, int) or isinstance(completion_tokens, int):
            self.last_usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        else:
            self.last_usage = None
        text = data.get("response", "")
        return text.strip() if text else "Ollama returned no text output."


def build_controller() -> ChatController:
    provider = os.environ.get("AIDF_CHAT_PROVIDER", "").strip().lower()

    if provider == "none":
        return NullChatController()

    if provider == "openai":
        return OpenAIResponsesController(
            api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            model=os.environ.get("OPENAI_MODEL", "gpt-5"),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            instructions=os.environ.get("AIDF_CHAT_INSTRUCTIONS", DEFAULT_CHAT_INSTRUCTIONS),
        )

    # Default (including provider="ollama" or unset): route to the local
    # Ollama/OLMo stack (see docker-compose.local.yml, `make workspace-up`).
    # kob is local-first — merely having OPENAI_API_KEY set in the ambient
    # environment is NOT enough to switch to cloud; that requires explicitly
    # setting AIDF_CHAT_PROVIDER=openai.
    return OllamaChatController(
        model=os.environ.get("AIDF_MODEL", "olmo2:7b-1124-instruct-q4_K_M"),
        base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
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
            excerpt = _excerpt_for(doc)
            if excerpt:
                lines.append(f"  excerpt={excerpt}")
    lines.extend(["", "User prompt:", prompt])
    return "\n".join(lines)


_MANIFESTO_EXCERPT_CHARS = 6000


def _excerpt_for(doc: Document) -> str:
    # The manifesto is the one document kob must actually reason from, not skim, when
    # explaining KAIDF - a 3-line teaser isn't enough to cover its principles, best
    # practices, and implementation phases, so give it the full body (bounded).
    if doc.doctrine_category == "manifesto":
        return doc.body.strip()[:_MANIFESTO_EXCERPT_CHARS]
    return " ".join(doc.body.splitlines()[:3]).strip()[:280]


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
    if doc.doctrine_category == "manifesto" and ("kaidf" in terms or prompt_norm == "kaidf"):
        score += 200
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
