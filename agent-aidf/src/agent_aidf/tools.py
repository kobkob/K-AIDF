from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Set by `kob --yolo` (see cli/main.py) for the lifetime of the process - checked by mentor.py
# (skip the write_file/run_shell confirmation), and surfaced to the TUI/CLI/web UI so each can
# show its own warning banner. Deliberately does NOT affect phase-acceptance confirmation,
# which is a methodology quality gate (did the user actually sign off on this deliverable),
# not a tool-execution safety guardrail.
_YOLO_ENV_VAR = "KOB_YOLO"


def is_yolo_enabled() -> bool:
    return os.environ.get(_YOLO_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}

# Local Ollama has no native tool-calling (only the plain text-completion endpoint is wired
# up in controller.py), so this is a prompt-engineered action protocol: the model proposes an
# action as a strictly-formatted block, kob parses it defensively (anything malformed or
# unrecognized is just dropped), shows the user exactly what was proposed, and only applies it
# after explicit confirmation (unless --yolo is active - see mentor.py). The model never
# touches the filesystem or a shell directly.

ACTION_MARKER_START = "<<<KOB_ACTION"
ACTION_MARKER_END = "KOB_ACTION>>>"

_ACTION_BLOCK_RE = re.compile(
    re.escape(ACTION_MARKER_START) + r"\s*(.*?)\s*" + re.escape(ACTION_MARKER_END),
    re.DOTALL,
)

_SUPPORTED_ACTIONS = {"write_file", "run_shell"}

_DEFAULT_SHELL_TIMEOUT_SECONDS = 30

ACTION_PROTOCOL_INSTRUCTIONS = (
    "If (and only if) it would clearly help right now, you may propose ONE action as exactly "
    "one block in this exact form, with valid JSON inside and nothing else on those lines:\n"
    f"{ACTION_MARKER_START}\n"
    '{"action": "write_file", "path": "relative/path/to/file", "content": "full file content"}\n'
    "or\n"
    f"{ACTION_MARKER_START}\n"
    '{"action": "run_shell", "command": "the shell command to run"}\n'
    f"{ACTION_MARKER_END}\n"
    "For write_file, path must be relative to the project root - never absolute, never "
    "containing '..'. For run_shell, command runs from the project root (this covers things "
    "like `kob compile`/`kob gen`, git, or any other CLI tool). The user will see the exact "
    "proposal and must explicitly approve it before anything happens - you cannot touch files "
    "or run commands yourself. Most turns should have no action block at all."
)


class UnsafeActionPathError(ValueError):
    pass


@dataclass(frozen=True)
class ProposedAction:
    kind: str
    path: str = ""
    content: str = ""
    command: str = ""


def extract_proposed_action(text: str) -> tuple[str, ProposedAction | None]:
    """Strip a proposed action block out of model output.

    Returns the cleaned display text and the parsed action, if one was present and valid.
    Never raises - a malformed or unrecognized block is just dropped (with the surrounding
    text left intact), since a small local model can't be trusted to always format this
    perfectly.
    """
    match = _ACTION_BLOCK_RE.search(text)
    if not match:
        return text.strip(), None
    cleaned = (text[: match.start()] + text[match.end() :]).strip()
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return cleaned, None
    if not isinstance(payload, dict):
        return cleaned, None
    kind = payload.get("action")
    if kind not in _SUPPORTED_ACTIONS:
        return cleaned, None
    if kind == "write_file":
        path = payload.get("path")
        content = payload.get("content")
        if not isinstance(path, str) or not path.strip() or not isinstance(content, str):
            return cleaned, None
        return cleaned, ProposedAction(kind=kind, path=path.strip(), content=content)
    if kind == "run_shell":
        command = payload.get("command")
        if not isinstance(command, str) or not command.strip():
            return cleaned, None
        return cleaned, ProposedAction(kind=kind, command=command.strip())
    return cleaned, None


def resolve_safe_path(project_root: Path, relative_path: str) -> Path:
    """Resolve relative_path within project_root, rejecting any attempt to escape it."""
    candidate = (project_root / relative_path).resolve()
    root_resolved = project_root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafeActionPathError(f"Path escapes the project directory: {relative_path}") from exc
    return candidate


_PREVIEW_CHARS = 800


def describe_action(action: ProposedAction) -> str:
    """A human-readable confirmation prompt for a proposed action - shown to the user
    verbatim before anything is applied."""
    if action.kind == "run_shell":
        return (
            f"Proposed action: run this shell command from the project root:\n"
            "---\n"
            f"{action.command}\n"
            "---\n"
            'Reply "yes" to run it, or reply with what to change instead.'
        )
    preview = action.content
    if len(preview) > _PREVIEW_CHARS:
        preview = preview[:_PREVIEW_CHARS] + "\n... (truncated)"
    return (
        f"Proposed action: write {len(action.content)} characters to `{action.path}`.\n"
        "---\n"
        f"{preview}\n"
        "---\n"
        'Reply "yes" to save this file, or reply with what to change instead.'
    )


def apply_write_action(project_root: str | Path, action: ProposedAction) -> str:
    """Write action.content to action.path within project_root.

    The caller MUST have already obtained explicit user confirmation - this function
    does not ask, it only enforces the path stays inside project_root.
    """
    if action.kind != "write_file":
        raise ValueError(f"Unsupported action kind: {action.kind}")
    root = Path(project_root).expanduser().resolve()
    target = resolve_safe_path(root, action.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(action.content, encoding="utf-8")
    return f"Wrote {len(action.content)} characters to {action.path}."


def apply_run_shell_action(
    project_root: str | Path,
    action: ProposedAction,
    *,
    timeout: int = _DEFAULT_SHELL_TIMEOUT_SECONDS,
) -> str:
    """Run action.command in a shell, cwd'd to project_root.

    The caller MUST have already obtained explicit user confirmation - this function does
    not ask. Unlike write_file, this has no path-escape protection: an arbitrary shell command
    can affect anything the OS user running kob can touch. The confirmation step (or, in
    --yolo mode, the user's own decision to run without confirmation) is the whole safety
    boundary here, by design - matching what was asked for.
    """
    if action.kind != "run_shell":
        raise ValueError(f"Unsupported action kind: {action.kind}")
    root = Path(project_root).expanduser().resolve()
    try:
        result = subprocess.run(
            action.command,
            shell=True,  # noqa: S602 - intentional: this tool's entire purpose is running a
            # user-confirmed, model-proposed shell command; the command IS the trusted payload.
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s: {action.command}"
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if len(output) > _PREVIEW_CHARS:
        output = output[:_PREVIEW_CHARS] + "\n... (truncated)"
    summary = f"Ran `{action.command}` (exit code {result.returncode})."
    return f"{summary}\n{output}" if output else summary


def apply_action(project_root: str | Path, action: ProposedAction) -> str:
    """Dispatch a confirmed action to the right apply_* function by kind."""
    if action.kind == "write_file":
        try:
            return apply_write_action(project_root, action)
        except UnsafeActionPathError as exc:
            return f"Could not write that file: {exc}"
    if action.kind == "run_shell":
        return apply_run_shell_action(project_root, action)
    return f"Unsupported action kind: {action.kind}"


_AFFIRMATIVE_TOKENS = {
    "yes",
    "y",
    "yeah",
    "yea",
    "yep",
    "sure",
    "ok",
    "okay",
    "confirm",
    "confirmed",
    "accept",
    "accepted",
    "approve",
    "approved",
    "agree",
    "agreed",
    "done",
    "go",
    "correct",
    "affirmative",
}
_NEGATIVE_PREFIXES = ("no,", "no ", "not ", "don't", "do not", "n,", "n ")


def is_affirmative(answer: str) -> bool:
    """A conservative yes/no check for confirmation gates (file writes, phase acceptance).

    Defaults to False for anything ambiguous - silence or uncertainty should never be read
    as approval.
    """
    normalized = answer.strip().casefold().rstrip(".!")
    if not normalized:
        return False
    if normalized in {"no", "nope", "n", "nah"}:
        return False
    if normalized.startswith(_NEGATIVE_PREFIXES):
        return False
    if normalized in _AFFIRMATIVE_TOKENS:
        return True
    first_word = normalized.split(" ", 1)[0].strip(",")
    return first_word in _AFFIRMATIVE_TOKENS


class SafeActionTool:
    """The tool kob's mentor workflow uses to touch the outside world: parse a proposed
    action (write a file, or run a shell command), describe it for user confirmation, and
    apply it only after that confirmation (or immediately in --yolo mode - see mentor.py).

    Read access to project files is handled separately and deterministically, via the
    existing document context injection mentor already builds into its prompt.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def extract_action(self, text: str) -> tuple[str, ProposedAction | None]:
        return extract_proposed_action(text)

    def describe(self, action: ProposedAction) -> str:
        return describe_action(action)

    def apply(self, action: ProposedAction) -> str:
        return apply_action(self.project_root, action)
