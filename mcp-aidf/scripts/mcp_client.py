#!/usr/bin/env python3
"""Call one MCP tool on a Streamable HTTP server, described by a declarative JSON file.

The JSON file names the server, the tool and its arguments. It never holds the bearer token:
``token_env`` names the environment variable that does, so the secret stays out of the disk.

    python scripts/mcp_client.py call --config deploy/easypanel/mcp-call.example.json
    python scripts/mcp_client.py call --config mcp-call.json --json

Config keys: ``url`` (required), ``tool`` (required), ``arguments`` (object, default ``{}``),
``token_env`` (optional), ``protocol_version`` (default ``2025-06-18``), ``timeout`` in seconds
(default 30, applied to each HTTP request).

Standard library only, so it runs wherever the server's Python runs.

Exit codes: 0 success, 1 the server or the transport failed, 2 the config is unusable.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_TIMEOUT = 30.0
CLIENT_INFO = {"name": "mcp-aidf-client", "version": "1"}
CONFIG_KEYS = frozenset({"url", "token_env", "protocol_version", "tool", "arguments", "timeout"})
PROTOCOL_VERSION_HEADER = "MCP-Protocol-Version"

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CONFIG = 2


class ConfigError(ValueError):
    """The JSON file or the environment does not describe a usable call."""


class McpError(RuntimeError):
    """The server or the transport failed. Messages never contain the token."""


class McpTimeoutError(McpError):
    """The server did not answer within the configured timeout."""


@dataclass(frozen=True)
class CallConfig:
    url: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    token_env: str | None = None
    protocol_version: str = DEFAULT_PROTOCOL_VERSION
    timeout: float = DEFAULT_TIMEOUT


def load_config(path: Path) -> CallConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}") from exc
    return parse_config(raw)


def parse_config(raw: Any) -> CallConfig:
    if not isinstance(raw, dict):
        raise ConfigError("config must be a JSON object")
    if "token" in raw:
        raise ConfigError(
            '"token" is not allowed in the config file; set "token_env" to the name of an '
            "environment variable that holds the token"
        )
    unknown = sorted(set(raw) - CONFIG_KEYS)
    if unknown:
        raise ConfigError("unknown config key(s): " + ", ".join(unknown))

    url = _required_str(raw, "url")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ConfigError('"url" must be an absolute http or https URL')

    tool = _required_str(raw, "tool")

    arguments = raw.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ConfigError('"arguments" must be a JSON object')

    token_env = raw.get("token_env")
    if token_env is not None:
        if not isinstance(token_env, str) or not token_env.strip():
            raise ConfigError('"token_env" must be the name of an environment variable')
        token_env = token_env.strip()

    protocol_version = raw.get("protocol_version", DEFAULT_PROTOCOL_VERSION)
    if not isinstance(protocol_version, str) or not protocol_version.strip():
        raise ConfigError('"protocol_version" must be a non-empty string')

    timeout = raw.get("timeout", DEFAULT_TIMEOUT)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ConfigError('"timeout" must be a positive number of seconds')

    return CallConfig(
        url=url,
        tool=tool,
        arguments=arguments,
        token_env=token_env,
        protocol_version=protocol_version.strip(),
        timeout=float(timeout),
    )


def resolve_token(token_env: str | None, environ: Mapping[str, str]) -> str | None:
    """Read the bearer token from the environment; ``None`` means an anonymous call."""
    if token_env is None:
        return None
    token = environ.get(token_env, "").strip()
    if not token:
        raise ConfigError(f"environment variable {token_env} is not set or empty")
    return token


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f'"{key}" is required and must be a non-empty string')
    return value.strip()


class McpClient:
    """Minimal Streamable HTTP client: initialize, the initialized notification, tools/call."""

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.url = url
        self.protocol_version = protocol_version
        self.timeout = timeout
        self._token = token
        self._negotiated: str | None = None
        self._next_id = 0

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        init = self._rpc(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        negotiated = init.get("protocolVersion")
        if negotiated != self.protocol_version:
            raise McpError(
                f"server negotiated protocol {negotiated!r}, not the requested "
                f"{self.protocol_version!r}"
            )
        self._negotiated = negotiated
        self._notify("notifications/initialized")
        return self._rpc("tools/call", {"name": name, "arguments": arguments})

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        reply = self._post(
            {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        )
        if reply is None:
            raise McpError(f"{method}: the server sent no JSON-RPC reply")
        error = reply.get("error")
        if error is not None:
            if not isinstance(error, dict):
                raise McpError(f"{method} failed: malformed error object")
            raise McpError(
                f"{method} failed: {error.get('message', 'unknown error')} "
                f"(code {error.get('code', 'unknown')})"
            )
        result = reply.get("result")
        if not isinstance(result, dict):
            raise McpError(f"{method}: the reply has no result object")
        return result

    def _notify(self, method: str) -> None:
        # A notification has no id, so the server answers 202 with no body.
        self._post({"jsonrpc": "2.0", "method": method})

    def _post(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if self._negotiated:
            headers[PROTOCOL_VERSION_HEADER] = self._negotiated
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.status
                body = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read()
        except (TimeoutError, socket.timeout) as exc:
            raise McpTimeoutError(f"no answer from {self.url} within {self.timeout:g}s") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise McpTimeoutError(
                    f"no answer from {self.url} within {self.timeout:g}s"
                ) from exc
            raise McpError(f"cannot reach {self.url}: {exc.reason}") from exc

        if status >= 400:
            raise McpError(_http_error_message(status, body))
        if not body.strip():
            return None
        try:
            decoded = json.loads(body)
        except ValueError as exc:
            raise McpError(
                f"HTTP {status}: the server answered with a body that is not JSON"
            ) from exc
        if not isinstance(decoded, dict):
            raise McpError(
                f"HTTP {status}: the server answered with a JSON value that is not an object"
            )
        return decoded


def _http_error_message(status: int, body: bytes) -> str:
    if status == 401:
        return (
            "HTTP 401: the server rejected the bearer token (check the variable named by token_env)"
        )
    detail = ""
    try:
        decoded = json.loads(body)
    except ValueError:
        decoded = None
    if isinstance(decoded, dict) and isinstance(decoded.get("error"), dict):
        message = decoded["error"].get("message")
        if isinstance(message, str):
            detail = f": {message}"
    return f"HTTP {status}{detail}"


def render_text(result: dict[str, Any]) -> str:
    """Readable view of a tools/call result; text items holding JSON are pretty-printed."""
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return json.dumps(result, ensure_ascii=False, indent=2)
    blocks: list[str] = []
    for item in content:
        if (
            isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
        ):
            blocks.append(_pretty_if_json(item["text"]))
        else:
            blocks.append(json.dumps(item, ensure_ascii=False, indent=2))
    return "\n".join(blocks)


def _pretty_if_json(text: str) -> str:
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except ValueError:
        return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp_client.py",
        description="Call an MCP tool described by a declarative JSON file.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    call = subparsers.add_parser("call", help="Call the tool named in a JSON config file.")
    call.add_argument("--config", required=True, type=Path, help="Path to the JSON call file.")
    call.add_argument(
        "--json", action="store_true", help="Print the raw tools/call result as JSON."
    )
    return parser


def main(argv: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env: Mapping[str, str] = os.environ if environ is None else environ
    try:
        config = load_config(args.config)
        token = resolve_token(config.token_env, env)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    client = McpClient(
        config.url,
        token=token,
        protocol_version=config.protocol_version,
        timeout=config.timeout,
    )
    try:
        result = client.call_tool(config.tool, config.arguments)
    except McpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILURE

    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_text(result))
    return EXIT_FAILURE if result.get("isError") else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
