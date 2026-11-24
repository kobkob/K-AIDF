"""`kob menu`: a numbered keyboard menu for the everyday commands.

The menu only dispatches. Each action is a callable supplied by the caller (cli/main.py), so this
module imports nothing that would create a cycle. Without a terminal on both stdin and stdout the
menu does not prompt: it lists the choices and says how to run them directly, and exits 0.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

MENU_ITEMS: tuple[tuple[str, str], ...] = (
    ("status", "Project and .kaidf status"),
    ("mentor", "The mentor's pending question, and an answer if you give one"),
    ("models", "The models the active provider serves"),
    ("scan", "Bootstrap docs, RAG corpus and QLoRA dataset (asks before writing)"),
    ("audit", "Score the repository against the KAIDF-AMM audit matrix"),
)

QUIT_WORDS = frozenset({"", "q", "quit", "exit"})


def render_menu(*, numbered: bool = True) -> list[str]:
    lines = []
    for index, (name, label) in enumerate(MENU_ITEMS, start=1):
        prefix = f"{index}. " if numbered else "  "
        lines.append(f"{prefix}{name:<8} {label}")
    return lines


def resolve_choice(answer: str) -> str | None:
    """The menu item named by a number or by its command name, or None when there is no match."""
    text = answer.strip().lower()
    for index, (name, _label) in enumerate(MENU_ITEMS, start=1):
        if text in {str(index), name}:
            return name
    return None


def run_menu(
    actions: Mapping[str, Callable[[], int]],
    *,
    interactive: bool,
    read: Callable[[str], str] = input,
    write: Callable[[str], object] = print,
) -> int:
    """Show the menu and run choices until the operator quits. Returns the exit code."""
    if not interactive:
        for line in render_menu():
            write(line)
        write("The menu needs a terminal. Run one command directly, for example: kob status")
        return 0

    while True:
        write("K-AIDF menu")
        for line in render_menu():
            write(f"  {line}")
        write("  q        Quit")
        try:
            answer = read("Choose a number or name (q to quit): ")
        except (EOFError, KeyboardInterrupt):
            write("")
            return 0
        if answer.strip().lower() in QUIT_WORDS:
            return 0
        name = resolve_choice(answer)
        if name is None:
            write(
                f"Not a menu choice: {answer.strip()!r}. Enter 1-{len(MENU_ITEMS)}, a name, or q."
            )
            continue
        code = actions[name]()
        write("")
        if code:
            write(f"{name} finished with exit code {code}.")
