"""Boot-time loader for kob extensions.

An extension is a directory holding a `main.py` with the metadata header (see metadata.py) and a
`register(hooks)` function. At boot, the loader scans two roots:

- the built-in extensions shipped in the package (`agent_aidf/ext/`), and
- the user extensions directory (`$KOB_EXTENSIONS_DIR`, default `~/.kob/extensions`).

A broken extension is logged and skipped, so it never stops kob from starting. Its registrations
are kept only if its `register()` returns cleanly.

Set `KOB_DISABLE_EXTENSIONS=words,ext` to skip extensions by directory name.
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
from .metadata import ExtensionMetadata, read_metadata

logger = logging.getLogger(__name__)

BUILTIN_EXTENSIONS_DIR = Path(__file__).resolve().parent.parent / "ext"
EXTENSIONS_DIR_ENV = "KOB_EXTENSIONS_DIR"
DISABLED_ENV = "KOB_DISABLE_EXTENSIONS"

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
        """Run before built-in commands. Return an int to stop dispatch with that exit code."""
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


class ExtensionRegistry:
    def __init__(self) -> None:
        self.loaded: list[LoadedExtension] = []
        self._arguments: list[tuple[str, ArgumentConfigurer]] = []
        self._handlers: list[tuple[str, CliHandler]] = []
        self._subcommands: list[_Subcommand] = []

    def merge(self, loaded: LoadedExtension, contributions: _Contributions) -> None:
        self.loaded.append(loaded)
        self._arguments.extend(contributions.arguments)
        self._handlers.extend(contributions.handlers)
        for _owner, sub in contributions.subcommands:
            self._subcommands.append(sub)
            # Subcommand handlers only fire for their own command name.
            self._handlers.append((_owner, _command_gate(sub.name, sub.handler)))
        for owner, interceptor in contributions.interceptors:
            register_prompt_interceptor(owner, interceptor)

    def configure_parser(self, parser: ArgumentParser, subparsers: _SubParsersAction) -> None:
        for owner, configure in self._arguments:
            _safely(owner, lambda: configure(parser))
        for sub in self._subcommands:

            def add(sub: _Subcommand = sub) -> None:
                sub.configure(subparsers.add_parser(sub.name, help=sub.help))

            _safely(sub.name, add)

    def dispatch(self, args: Namespace) -> int | None:
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
        if ext_id.lower() in skip:
            continue
        if ext_id in seen:
            logger.warning("extension %r at %s shadows an earlier one; skipped", ext_id, directory)
            continue
        main = directory / "main.py"
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
            continue
        seen.add(ext_id)
        registry.merge(LoadedExtension(ext_id, directory, metadata), hooks.contributions)
    return registry


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
