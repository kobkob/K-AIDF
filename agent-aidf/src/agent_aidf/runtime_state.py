"""Safe reads and writes for the runtime state files under `.kaidf/`.

The mentor workflow, instant apps and contracts keep their state in JSON files that the CLI,
the TUI and the web UI all read. Two things must not happen to them:

- a save that is interrupted, or a second writer, leaves a truncated file: every write goes to a
  temporary file in the same directory, is flushed, and then replaces the target atomically;
- one damaged file makes every reader fail: a file that does not parse is moved aside, with a
  warning, and the reader continues from a clean state, so the damaged copy is kept for inspection.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    """Replace `path` with `text` in one step: readers see the old or the new file, never half.

    The temporary file is created next to `path`, so the final rename stays on one filesystem.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


def read_state_object(path: Path) -> dict[str, Any] | None:
    """The JSON object stored in `path`, or None when there is no usable object there.

    A missing file, or one that holds JSON that is not an object, gives None without a warning.
    A file that does not parse is moved to `<name>.corrupt-<timestamp>` and a warning is printed.
    A file that cannot be read gives None and a warning, and is left where it is.
    """
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"kob: cannot read {path}: {exc}; using a clean state.", file=sys.stderr)
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        quarantine = path.with_name(
            f"{path.name}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
        )
        try:
            path.rename(quarantine)
            kept = f"kept as {quarantine}"
        except OSError:
            kept = "left in place"
        print(
            f"kob: {path} is not valid JSON ({exc.msg} at line {exc.lineno}); {kept}. "
            "Continuing from a clean state.",
            file=sys.stderr,
        )
        return None
    return data if isinstance(data, dict) else None


def as_int(value: Any, default: int) -> int:
    """`value` as an int for a state field: numbers and numeric strings convert, anything else
    (including booleans, NaN and infinities) gives `default`."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default
