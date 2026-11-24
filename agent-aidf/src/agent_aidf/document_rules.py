"""The rules a K-AIDF document must meet, in one place.

The audit scorecard, the mentor's grounding context and the mentor's validation gate all read
these constants, so the criteria the model is asked to meet are the criteria the audit applies.
This module imports nothing from the package, so any of them can import it without a cycle.
"""

from __future__ import annotations

# Front Matter v2: every generated Markdown document carries these fields.
REQUIRED_FRONT_MATTER = ("id", "title", "document_class", "phase", "visibility", "status")

# Levels a document may declare. Operator context only ever uses public and internal (repo.py);
# private documents are kept out of the model's context but are still valid documents.
VISIBILITY_LEVELS = frozenset({"public", "internal", "private"})

# Plain-language statements of the same rules, for the model. Keep them in step with the checks.
CRITERIA_SUMMARY: tuple[str, ...] = (
    "Start the document with Front Matter v2 between --- lines, with every required field: "
    + ", ".join(REQUIRED_FRONT_MATTER)
    + ".",
    "visibility is one of " + ", ".join(sorted(VISIBILITY_LEVELS)) + ".",
    "Keep every `##` section of the canonical template, in its order, with real content.",
    "Do not repeat the template unchanged; fill in the project's own facts.",
    "Never write a credential, token or private key into a document.",
)
