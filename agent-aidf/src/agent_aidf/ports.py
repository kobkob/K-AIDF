from __future__ import annotations

import argparse

MIN_TCP_PORT = 1
MAX_TCP_PORT = 65535


def parse_tcp_port(value: object) -> int:
    """Return ``value`` as a TCP port number, or raise ``ValueError`` with a readable message."""
    if isinstance(value, bool):
        raise ValueError(f"Port must be a whole number between {MIN_TCP_PORT} and {MAX_TCP_PORT}.")
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(
            f"Port must be a whole number between {MIN_TCP_PORT} and {MAX_TCP_PORT}, got {value!r}."
        ) from None
    if not MIN_TCP_PORT <= port <= MAX_TCP_PORT:
        raise ValueError(f"Port must be between {MIN_TCP_PORT} and {MAX_TCP_PORT}, got {port}.")
    return port


def tcp_port_argument(value: str) -> int:
    """argparse ``type=`` hook: reports a bad port as a usage error (exit code 2)."""
    try:
        return parse_tcp_port(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
