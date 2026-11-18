"""List the models the active inference provider serves, through its OpenAI-compatible /v1/models.

The provider is resolved the way build_controller() resolves it, so `kob models` shows what the
next command would talk to: Ollama (or LocalAI, or any OpenAI-compatible server behind OLLAMA_HOST)
by default, and OpenAI when AIDF_CHAT_PROVIDER=openai. Nothing here changes the configuration.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .controller import resolve_local_model

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
# Short on purpose: `kob models` is a quick look, and a provider that does not answer in a few
# seconds is reported as unreachable rather than waited for.
MODELS_TIMEOUT_SECONDS = 5.0


class ModelsUnavailableError(RuntimeError):
    """The provider could not list its models. The message is safe to print as is."""


@dataclass(frozen=True)
class ProviderEndpoint:
    provider: str
    base_url: str
    api_key: str | None
    active_model: str


@dataclass(frozen=True)
class ProviderModels:
    provider: str
    base_url: str
    active_model: str
    models: list[str] = field(default_factory=list)


def provider_endpoint() -> ProviderEndpoint:
    env = os.environ
    provider = env.get("AIDF_CHAT_PROVIDER", "").strip().lower() or "ollama"
    if provider == "none":
        raise ModelsUnavailableError(
            "No inference provider is configured (AIDF_CHAT_PROVIDER=none), so there is nothing "
            "to list."
        )
    if provider == "openai":
        return ProviderEndpoint(
            provider="openai",
            base_url=env.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).strip()
            or DEFAULT_OPENAI_BASE_URL,
            api_key=env.get("OPENAI_API_KEY", "").strip() or None,
            active_model=env.get("OPENAI_MODEL", "gpt-5").strip() or "gpt-5",
        )
    return ProviderEndpoint(
        provider="ollama",
        base_url=env.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST).strip() or DEFAULT_OLLAMA_HOST,
        api_key=None,
        active_model=resolve_local_model(),
    )


def models_url(base_url: str) -> str:
    """`<base>/v1/models`, whether or not the base already ends with `/v1`."""
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


def fetch_model_ids(
    url: str, api_key: str | None = None, timeout: float = MODELS_TIMEOUT_SECONDS
) -> list[str]:
    request = urllib.request.Request(url, method="GET")
    request.add_header("Accept", "application/json")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ModelsUnavailableError(
                f"The provider refused the request (HTTP {exc.code}). Check its API key."
            ) from exc
        raise ModelsUnavailableError(f"The provider answered HTTP {exc.code} for {url}.") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ModelsUnavailableError(
            f"The provider did not answer within {timeout:g}s: {url}"
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ModelsUnavailableError(
                f"The provider did not answer within {timeout:g}s: {url}"
            ) from exc
        raise ModelsUnavailableError(
            f"The provider is not reachable at {url}: {exc.reason}"
        ) from exc
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise ModelsUnavailableError(f"{url} did not return JSON.") from exc
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise ModelsUnavailableError(f"{url} did not return a model list.")
    ids = [
        entry["id"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    return sorted(set(ids))


def list_provider_models(timeout: float = MODELS_TIMEOUT_SECONDS) -> ProviderModels:
    endpoint = provider_endpoint()
    ids = fetch_model_ids(models_url(endpoint.base_url), endpoint.api_key, timeout)
    return ProviderModels(
        provider=endpoint.provider,
        base_url=endpoint.base_url,
        active_model=endpoint.active_model,
        models=ids,
    )
