# Extension: Ext
# Description: Install extensions from a local or HTTPS .tgz archive with -x / --ext
# Version: 1.0.0
# Author: Kobkob LLC
# Entrypoints: cli
# Topics: extensions, packaging, cli
"""Core extension: `kob -x <path-or-https-url.tgz>` installs an extension for future runs."""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace

from agent_aidf.extensions.extension_loader import user_extensions_dir
from agent_aidf.extensions.installer import InstallError, install_extension


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


def _handle(args: Namespace) -> int | None:
    source = getattr(args, "ext", None)
    if not source:
        return None
    try:
        installed = install_extension(source, user_extensions_dir())
    except InstallError as exc:
        print(f"kob: could not install extension: {exc}", file=sys.stderr)
        return 1
    print(
        f"Installed extension {installed.metadata.name} {installed.metadata.version} "
        f"at {installed.path}. It loads on the next kob start."
    )
    return 0
