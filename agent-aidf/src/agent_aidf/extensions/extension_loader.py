"""Boot-time loader for kob extensions.

An extension is a directory holding a `main.py` with the metadata header (see metadata.py) and a
`register(hooks)` function. At boot, the loader scans two roots:

- the built-in extensions shipped in the package (`agent_aidf/ext/`), and
- the user extensions directory (`$KOB_EXTENSIONS_DIR`, default `~/.kob/extensions`).

A broken extension is logged and skipped, so it never stops kob from starting. Its registrations
are kept only if its `register()` returns cleanly. Every candidate directory, including the failed,
disabled and shadowed ones, is recorded as an `ExtensionStatus` so `kob ext list` can report it.

Set `KOB_DISABLE_EXTENSIONS=words,ext` to skip extensions by directory name.

Extensions cannot preempt built-in commands. A subcommand whose name is in `BUILTIN_COMMANDS`, or
one already claimed by an earlier extension, is refused with a warning. Top-level handlers
(`add_cli_handler`) run only when no subcommand was given, and built-in commands never reach
extension handlers at all.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from argparse import ArgumentParser, Namespace, _SubParsersAction
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ..prompt_hooks import clear_prompt_interceptors, register_prompt_interceptor
from .integrity import verify_install
from .metadata import ExtensionMetadata, read_metadata

logger = logging.getLogger(__name__)

BUILTIN_EXTENSIONS_DIR = Path(__file__).resolve().parent.parent / "ext"
EXTENSIONS_DIR_ENV = "KOB_EXTENSIONS_DIR"
DISABLED_ENV = "KOB_DISABLE_EXTENSIONS"

ORIGIN_BUILTIN = "built-in"
ORIGIN_USER = "user"

STATE_LOADED = "loaded"
STATE_FAILED = "failed"
STATE_DISABLED = "disabled"
STATE_SHADOWED = "shadowed"

# Every subcommand the CLI defines itself (see cli/main.py). Extensions may not add or handle these.
# tests/test_extension_loader.py checks this set against the real parser, so keep them in sync.
BUILTIN_COMMANDS: frozenset[str] = frozenset(
    {
        "init",
        "status",
        "mentor",
        "shell",
        "audit",
        "ui",
        "serve",
        "compile",
        "gen",
        "ext",
        "appliance",
    }
)

ArgumentConfigurer = Callable[[ArgumentParser], None]
CliHandler = Callable[[Namespace], "int | None"]


def user_extensions_dir() -> Path:
    raw = os.environ.get(EXTENSIONS_DIR_ENV, "").strip()
    return Path(raw).expanduser() if raw else Path.home() / ".kob" / "extensions"


@dataclass
class _Subcommand:
    name: str
    help: str
    configure: ArgumentConfigurer
    handler: CliHandler


@dataclass
class _Contributions:
    """What one extension registered. Merged into the registry only after register() succeeds."""

    arguments: list[tuple[str, ArgumentConfigurer]] = field(default_factory=list)
    handlers: list[tuple[str, CliHandler]] = field(default_factory=list)
    subcommands: list[tuple[str, _Subcommand]] = field(default_factory=list)
    interceptors: list[tuple[str, Callable[[str], "str | None"]]] = field(default_factory=list)


class ExtensionHooks:
    """The object an extension's `register()` receives."""

    def __init__(self, owner: str) -> None:
        self._owner = owner
        self.contributions = _Contributions()

    def add_cli_arguments(self, configure: ArgumentConfigurer) -> None:
        """Add top-level flags, e.g. `lambda p: p.add_argument("-x", "--ext")`."""
        self.contributions.arguments.append((self._owner, configure))

    def add_cli_handler(self, handler: CliHandler) -> None:
        """Top-level flag handler, e.g. `kob -x`. Runs only when no subcommand was given.
        Return an int to stop dispatch with that exit code."""
        self.contributions.handlers.append((self._owner, handler))

    def add_subcommand(
        self, name: str, help: str, configure: ArgumentConfigurer, handler: CliHandler
    ) -> None:
        """Add `kob <name>`. `handler` receives the parsed args and returns an exit code."""
        self.contributions.subcommands.append(
            (self._owner, _Subcommand(name, help, configure, handler))
        )

    def add_prompt_interceptor(self, interceptor: Callable[[str], "str | None"]) -> None:
        """Answer a prompt before the LLM sees it by returning a reply; return None to pass."""
        self.contributions.interceptors.append((self._owner, interceptor))


@dataclass(frozen=True)
class LoadedExtension:
    id: str
    path: Path
    metadata: ExtensionMetadata


@dataclass(frozen=True)
class Registration:
    """What an extension contributed once its registrations were accepted."""

    arguments: int = 0
    cli_handlers: int = 0
    subcommands: tuple[str, ...] = ()
    prompt_interceptors: int = 0


@dataclass(frozen=True)
class ExtensionStatus:
    """One candidate directory and what happened to it at boot."""

    id: str
    path: Path
    origin: str
    state: str
    metadata: ExtensionMetadata | None = None
    error: str | None = None
    registered: Registration = field(default_factory=Registration)


class ExtensionRegistry:
    def __init__(self) -> None:
        self.loaded: list[LoadedExtension] = []
        self.statuses: list[ExtensionStatus] = []
        self._arguments: list[tuple[str, ArgumentConfigurer]] = []
        self._handlers: list[tuple[str, CliHandler]] = []
        self._subcommands: list[_Subcommand] = []
        self._claimed_commands: set[str] = set(BUILTIN_COMMANDS)

    def merge(self, loaded: LoadedExtension, contributions: _Contributions) -> Registration:
        self.loaded.append(loaded)
        self._arguments.extend(contributions.arguments)
        for owner, handler in contributions.handlers:
            self._handlers.append((owner, _top_level_gate(handler)))
        accepted: list[str] = []
        for owner, sub in contributions.subcommands:
            if sub.name in self._claimed_commands:
                logger.warning(
                    "extension %r cannot add command %r: the name is built in or already taken",
                    owner,
                    sub.name,
                )
                continue
            self._claimed_commands.add(sub.name)
            self._subcommands.append(sub)
            accepted.append(sub.name)
            # Subcommand handlers only fire for their own command name.
            self._handlers.append((owner, _command_gate(sub.name, sub.handler)))
        for owner, interceptor in contributions.interceptors:
            register_prompt_interceptor(owner, interceptor)
        return Registration(
            arguments=len(contributions.arguments),
            cli_handlers=len(contributions.handlers),
            subcommands=tuple(accepted),
            prompt_interceptors=len(contributions.interceptors),
        )

    def configure_parser(self, parser: ArgumentParser, subparsers: _SubParsersAction) -> None:
        for owner, configure in self._arguments:
            _safely(owner, lambda: configure(parser))
        for sub in self._subcommands:

            def add(sub: _Subcommand = sub) -> None:
                sub.configure(subparsers.add_parser(sub.name, help=sub.help))

            _safely(sub.name, add)

    def dispatch(self, args: Namespace) -> int | None:
        # Built-in commands are never offered to extension handlers.
        if getattr(args, "command", None) in BUILTIN_COMMANDS:
            return None
        for owner, handler in self._handlers:
            try:
                result = handler(args)
            except Exception as exc:
                print(f"kob: extension {owner!r} failed: {exc}", file=sys.stderr)
                return 1
            if result is not None:
                return result
        return None


def _command_gate(name: str, handler: CliHandler) -> CliHandler:
    def gated(args: Namespace) -> int | None:
        return handler(args) if getattr(args, "command", None) == name else None

    return gated


def _top_level_gate(handler: CliHandler) -> CliHandler:
    def gated(args: Namespace) -> int | None:
        return handler(args) if getattr(args, "command", None) is None else None

    return gated


def _safely(owner: str, action: Callable[[], None]) -> None:
    # argparse raises on a duplicate flag or subcommand name; that must not break boot.
    try:
        action()
    except Exception as exc:
        logger.warning("extension %r could not add its CLI options: %s", owner, exc)


def _import_main(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _disabled_names() -> set[str]:
    raw = os.environ.get(DISABLED_ENV, "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _candidate_dirs(roots: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            # Skips hidden staging directories left by an interrupted install.
            if child.name.startswith(".") or not (child / "main.py").is_file():
                continue
            found.append(child)
    return found


def _origin(directory: Path) -> str:
    builtin = directory.parent.resolve() == BUILTIN_EXTENSIONS_DIR.resolve()
    return ORIGIN_BUILTIN if builtin else ORIGIN_USER


def _header_or_none(main: Path) -> ExtensionMetadata | None:
    try:
        return read_metadata(main)
    except Exception:
        return None


def _error_text(exc: BaseException) -> str:
    return str(exc) or type(exc).__name__


def load_extensions(
    roots: Iterable[Path] | None = None, disabled: Iterable[str] | None = None
) -> ExtensionRegistry:
    if roots is None:
        roots = [BUILTIN_EXTENSIONS_DIR, user_extensions_dir()]
    skip = {name.lower() for name in disabled} if disabled is not None else _disabled_names()

    registry = ExtensionRegistry()
    seen: set[str] = set()
    for directory in _candidate_dirs(roots):
        ext_id = directory.name
        origin = _origin(directory)
        main = directory / "main.py"
        if ext_id.lower() in skip:
            registry.statuses.append(
                ExtensionStatus(
                    ext_id,
                    directory,
                    origin,
                    STATE_DISABLED,
                    metadata=_header_or_none(main),
                )
            )
            continue
        if ext_id in seen:
            logger.warning("extension %r at %s shadows an earlier one; skipped", ext_id, directory)
            registry.statuses.append(
                ExtensionStatus(
                    ext_id,
                    directory,
                    origin,
                    STATE_SHADOWED,
                    metadata=_header_or_none(main),
                    error="an earlier extension with the same directory name is loaded",
                )
            )
            continue
        try:
            metadata = read_metadata(main)
            module = _import_main(main, f"agent_aidf_extension_{ext_id}")
            register = getattr(module, "register", None)
            if not callable(register):
                raise ValueError(f"{main}: no register(hooks) function")
            hooks = ExtensionHooks(owner=ext_id)
            register(hooks)
        except Exception as exc:
            logger.warning("skipping extension %r: %s", ext_id, exc)
            registry.statuses.append(
                ExtensionStatus(
                    ext_id,
                    directory,
                    origin,
                    STATE_FAILED,
                    metadata=_header_or_none(main),
                    error=_error_text(exc),
                )
            )
            continue
        seen.add(ext_id)
        registered = registry.merge(
            LoadedExtension(ext_id, directory, metadata), hooks.contributions
        )
        registry.statuses.append(
            ExtensionStatus(
                ext_id,
                directory,
                origin,
                STATE_LOADED,
                metadata=metadata,
                registered=registered,
            )
        )
    return registry


def inventory(registry: ExtensionRegistry | None = None) -> dict:
    """JSON-ready inventory of every extension found at boot, with install integrity.

    Built-in extensions ship inside the package, so they have no install record to check.
    """
    registry = registry or active_registry()
    rows = []
    for status in registry.statuses:
        meta = status.metadata
        if status.origin == ORIGIN_USER:
            integrity = verify_install(status.path).as_dict()
        else:
            integrity = {"status": "not-applicable", "archive_sha256": None, "changes": []}
        rows.append(
            {
                "id": status.id,
                "origin": status.origin,
                "state": status.state,
                "error": status.error,
                "path": str(status.path),
                "name": meta.name if meta else None,
                "version": meta.version if meta else None,
                "author": meta.author if meta else None,
                "description": meta.description if meta else None,
                "entrypoints": list(meta.entrypoints) if meta else [],
                "topics": list(meta.topics) if meta else [],
                "registered": {
                    "arguments": status.registered.arguments,
                    "cli_handlers": status.registered.cli_handlers,
                    "subcommands": list(status.registered.subcommands),
                    "prompt_interceptors": status.registered.prompt_interceptors,
                },
                "integrity": integrity,
            }
        )
    return {
        "schema_version": 1,
        "builtin_dir": str(BUILTIN_EXTENSIONS_DIR),
        "user_dir": str(user_extensions_dir()),
        "extensions": rows,
    }


def _integrity_text(integrity: dict) -> str:
    status = integrity["status"]
    if status == "verified":
        return f"verified (archive sha256:{integrity['archive_sha256'][:12]}…)"
    if status == "modified":
        return "MODIFIED since install: " + "; ".join(integrity["changes"])
    if status == "no-record":
        return "no install record (installed before integrity records existed)"
    if status == "unreadable":
        return "install record is unreadable"
    return "not applicable (built-in)"


def render_inventory_text(data: dict) -> str:
    lines = [
        f"Built-in extensions: {data['builtin_dir']}",
        f"User extensions:     {data['user_dir']}",
    ]
    if not data["extensions"]:
        lines.append("")
        lines.append("No extensions found.")
        return "\n".join(lines)
    for row in data["extensions"]:
        version = row["version"] or "-"
        author = row["author"] or "-"
        lines.append("")
        lines.append(f"{row['id']}  {version}  {author}  [{row['origin']}, {row['state']}]")
        if row["name"]:
            lines.append(f"    name:        {row['name']}")
        if row["description"]:
            lines.append(f"    description: {row['description']}")
        lines.append(f"    integrity:   {_integrity_text(row['integrity'])}")
        reg = row["registered"]
        subs = ", ".join(reg["subcommands"]) or "none"
        lines.append(
            f"    registered:  {reg['arguments']} CLI argument(s), "
            f"{reg['cli_handlers']} top-level handler(s), subcommands: {subs}, "
            f"{reg['prompt_interceptors']} prompt interceptor(s)"
        )
        if row["error"]:
            lines.append(f"    error:       {row['error']}")
    return "\n".join(lines)


_active: ExtensionRegistry | None = None


def active_registry() -> ExtensionRegistry:
    """The registry for this process, loaded on first use so boot runs the scan once."""
    global _active
    if _active is None:
        _active = load_extensions()
    return _active


def reset_active_registry() -> None:
    """Forget loaded extensions and their prompt interceptors (used by tests)."""
    global _active
    _active = None
    clear_prompt_interceptors()
