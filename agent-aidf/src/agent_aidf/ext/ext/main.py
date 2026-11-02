# Extension: Ext
# Description: Install extensions from a local or HTTPS .tgz archive with -x / --ext
# Version: 1.0.0
# Author: Kobkob LLC
# Entrypoints: cli
# Topics: extensions, packaging, cli
"""Core extension: `kob -x <path-or-https-url.tgz>` installs an extension for future runs.

A remote (https://) archive is installed only after the operator approves a summary of it, or
passes --yes. Without a terminal to ask on, a remote install fails unless --yes is given.
An optional --sha256 pins the archive's digest for any source.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace

from agent_aidf.extensions.extension_loader import user_extensions_dir
from agent_aidf.extensions.installer import (
    InstallError,
    InstallPreview,
    install_extension,
)

AFFIRMATIVE = frozenset({"y", "yes", "s", "sim"})


def register(hooks) -> None:
    hooks.add_cli_arguments(_add_flags)
    hooks.add_cli_handler(_handle)


def _add_flags(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-x",
        "--ext",
        metavar="SOURCE",
        default=None,
        help="Install an extension from a local .tgz path or an https:// .tgz URL.",
    )
    parser.add_argument(
        "--sha256",
        metavar="HASH",
        default=None,
        help="Refuse the archive unless its SHA-256 digest equals HASH.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        default=False,
        help="Approve a remote extension install without asking. Required without a terminal.",
    )


def _handle(args: Namespace) -> int | None:
    source = getattr(args, "ext", None)
    if not source:
        if getattr(args, "sha256", None) or getattr(args, "yes", False):
            print("kob: --sha256 and --yes apply only with -x / --ext", file=sys.stderr)
            return 2
        return None
    try:
        installed = install_extension(
            source,
            user_extensions_dir(),
            expected_sha256=getattr(args, "sha256", None),
            confirm=_consent(getattr(args, "yes", False)),
        )
    except InstallError as exc:
        print(f"kob: could not install extension: {exc}", file=sys.stderr)
        return 1
    print(
        f"Installed extension {installed.metadata.name} {installed.metadata.version} "
        f"at {installed.path}. It loads on the next kob start."
    )
    return 0


def _consent(assume_yes: bool):
    def confirm(preview: InstallPreview) -> bool:
        _print_preview(preview)
        if assume_yes:
            print("--yes given: approving without a prompt.")
            return True
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise InstallError(
                "no terminal to confirm the install; review the summary above and re-run "
                "with --yes to approve"
            )
        try:
            answer = input("Deseja prosseguir com a instalação desta extensão? [y/N] ")
        except EOFError:
            return False
        return answer.strip().lower() in AFFIRMATIVE

    return confirm


def _print_preview(preview: InstallPreview) -> None:
    print("Extensão remota a instalar:")
    print(f"  Nome:       {preview.name}")
    print(f"  Autor:      {preview.author}")
    print(f"  Versão:     {preview.version}")
    print(f"  Descrição:  {preview.description}")
    print(f"  Origem:     {preview.source}")
    print(f"  SHA-256:    {preview.sha256}")
    print(
        "Uma extensão executa código Python ao iniciar o kob. Instale apenas se confiar no autor."
    )
