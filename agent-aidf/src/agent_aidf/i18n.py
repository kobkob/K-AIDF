from __future__ import annotations

import gettext
from pathlib import Path

DOMAIN = "agent_aidf"
LOCALE_DIR = Path(__file__).resolve().parent / "locale"

_translation = gettext.translation(DOMAIN, localedir=LOCALE_DIR, fallback=True)


def gettext_(message: str) -> str:
    """Translate ``message`` for the active locale, defaulting to the English source text."""
    return _translation.gettext(message)


_ = gettext_
