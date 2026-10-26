"""Prompt interceptors: callables that may answer a user prompt before it reaches the LLM.

Extensions register interceptors through their `register(hooks)` entrypoint. Controllers call
`intercept_prompt()` at the top of `chat()`; a non-None return value is the reply, and the model
is never called. Interceptors run in registration order, and the first reply wins.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

PromptInterceptor = Callable[[str], "str | None"]

logger = logging.getLogger(__name__)

_interceptors: list[tuple[str, PromptInterceptor]] = []


def register_prompt_interceptor(owner: str, interceptor: PromptInterceptor) -> None:
    _interceptors.append((owner, interceptor))


def clear_prompt_interceptors() -> None:
    _interceptors.clear()


def intercept_prompt(prompt: str) -> str | None:
    for owner, interceptor in list(_interceptors):
        try:
            reply = interceptor(prompt)
        except Exception as exc:  # an extension must not break chat for everyone else
            logger.warning("prompt interceptor from extension %r failed: %s", owner, exc)
            continue
        if reply is not None:
            return reply
    return None
