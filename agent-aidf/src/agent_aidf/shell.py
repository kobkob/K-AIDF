from __future__ import annotations

import shlex
from pathlib import Path

from .i18n import _

# Commands the shell used to spell differently. They map onto the root CLI's flags.
_SHELL_ALIASES: dict[str, list[str]] = {
    "mentor-status": ["mentor", "--status"],
    "mentor-reset": ["mentor", "--reset"],
}

# Commands whose argument is free text. When a line has an unclosed quote (usually an apostrophe,
# as in `chat what's next`), the text after the command is passed on verbatim.
_FREE_TEXT_COMMANDS = frozenset({"chat", "find"})

SHELL_DEPRECATION = (
    "kob shell is deprecated and scheduled for removal in v0.8.0. Run the same commands "
    "directly, for example `kob apps`, `kob docs` or `kob mentor`."
)


def _split_line(raw: str) -> list[str]:
    """Split one shell line into arguments. Raises ValueError for an unclosed quote, unless the
    line is a free-text command, in which case its text is returned whole."""
    try:
        return shlex.split(raw)
    except ValueError:
        words = raw.split(maxsplit=1)
        if len(words) == 2 and words[0] in _FREE_TEXT_COMMANDS:
            return [words[0], words[1].strip()]
        raise


def run_shell(repo_root: Path, project_root: Path | None = None) -> int:
    """Read-eval loop over the root CLI. Each line runs as `kob <line>` in this project.

    Deprecated: the commands are root subcommands now. The shell keeps working through the 0.6.x
    series, so existing habits do not break, and every line is handled by the same parser.
    """
    # Imported here: cli.main imports this module, so a top-level import would be circular.
    from .cli.main import _run_cli

    print(_(SHELL_DEPRECATION))
    print("kob shell")
    print("type 'help' for commands, 'quit' to exit")
    # Pin the project and repository the shell was started with, whatever the working directory.
    scope: list[str] = []
    if project_root is not None:
        scope += ["--project", str(project_root)]
    scope += ["--repo", str(repo_root)]
    while True:
        try:
            raw = input("kob> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            # Ctrl+C drops the line being typed, as in most shells. Ctrl+D or `quit` leaves.
            print()
            continue
        if not raw:
            continue
        if raw in {"quit", "exit"}:
            return 0
        if raw == "help":
            print("type any kob command without the `kob` prefix; `kob help` lists them")
            continue
        try:
            parts = _split_line(raw)
        except ValueError:
            print(
                "error: a quote is not closed. Close it, or write an apostrophe as \\' "
                "(chat and find take the rest of the line as text)."
            )
            continue
        parts = _SHELL_ALIASES.get(parts[0], parts)
        if parts[0] == "shell":
            print("already inside kob shell")
            continue
        try:
            _run_cli([*scope, *parts])
        except SystemExit:
            # argparse has already printed its usage message for the bad line.
            continue
        except KeyboardInterrupt:
            print("\ninterrupted")  # Ctrl+C stops the command, not the session.
            continue
        except Exception as exc:  # one bad command must not end the session
            print(f"error: {exc}")
