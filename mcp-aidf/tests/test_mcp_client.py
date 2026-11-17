"""Tests for scripts/mcp_client.py: config reading, token resolution, and the HTTP exchange.

The exchange tests run against a real HTTP server on 127.0.0.1 in a background thread, so the
client's urllib code, headers, status handling and timeouts are exercised as they run in use.
"""

from __future__ import annotations

import contextlib
import io
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import mcp_client  # noqa: E402
from mcp_client import (  # noqa: E402
    ConfigError,
    McpClient,
    McpError,
    McpTimeoutError,
    load_config,
    parse_config,
    render_text,
    resolve_token,
)

TOKEN = "client-test-token-0123456789abcdef"
VALID_CONFIG: dict[str, Any] = {
    "url": "https://mcp.example.test/mcp",
    "token_env": "MCP_TEST_TOKEN",
    "protocol_version": "2025-06-18",
    "tool": "search",
    "arguments": {"query": "maturity", "limit": 3},
    "timeout": 5,
}


class ConfigReadingTests(unittest.TestCase):
    def _write(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "call.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_reads_every_key_from_a_json_file(self):
        config = load_config(self._write(json.dumps(VALID_CONFIG)))
        self.assertEqual(config.url, "https://mcp.example.test/mcp")
        self.assertEqual(config.tool, "search")
        self.assertEqual(config.arguments, {"query": "maturity", "limit": 3})
        self.assertEqual(config.token_env, "MCP_TEST_TOKEN")
        self.assertEqual(config.protocol_version, "2025-06-18")
        self.assertEqual(config.timeout, 5.0)

    def test_optional_keys_take_defaults(self):
        config = parse_config({"url": "http://127.0.0.1:7777/mcp", "tool": "fetch"})
        self.assertEqual(config.arguments, {})
        self.assertIsNone(config.token_env)
        self.assertEqual(config.protocol_version, mcp_client.DEFAULT_PROTOCOL_VERSION)
        self.assertEqual(config.timeout, mcp_client.DEFAULT_TIMEOUT)

    def test_literal_token_in_file_is_refused(self):
        raw = dict(VALID_CONFIG, token="a-secret-on-disk")
        with self.assertRaisesRegex(ConfigError, "token_env"):
            parse_config(raw)

    def test_unknown_key_is_refused(self):
        with self.assertRaisesRegex(ConfigError, "unknown config key.*tol"):
            parse_config(dict(VALID_CONFIG, tol="search"))

    def test_url_must_be_absolute_http_or_https(self):
        for url in ("ftp://host/mcp", "mcp.example.test/mcp", "https://", ""):
            with self.subTest(url=url), self.assertRaises(ConfigError):
                parse_config(dict(VALID_CONFIG, url=url))

    def test_arguments_must_be_an_object(self):
        with self.assertRaisesRegex(ConfigError, "arguments"):
            parse_config(dict(VALID_CONFIG, arguments=["query"]))

    def test_timeout_must_be_a_positive_number(self):
        for timeout in (0, -1, "5", True, None):
            with self.subTest(timeout=timeout), self.assertRaises(ConfigError):
                parse_config(dict(VALID_CONFIG, timeout=timeout))

    def test_tool_is_required(self):
        raw = {k: v for k, v in VALID_CONFIG.items() if k != "tool"}
        with self.assertRaisesRegex(ConfigError, '"tool"'):
            parse_config(raw)

    def test_invalid_json_reports_the_line(self):
        with self.assertRaisesRegex(ConfigError, "line 2"):
            load_config(self._write('{\n "url": ,\n}'))

    def test_missing_file_is_a_config_error(self):
        with self.assertRaisesRegex(ConfigError, "not found"):
            load_config(Path("/nonexistent/mcp-call.json"))


class TokenResolutionTests(unittest.TestCase):
    def test_reads_the_named_environment_variable(self):
        self.assertEqual(resolve_token("MCP_TEST_TOKEN", {"MCP_TEST_TOKEN": TOKEN}), TOKEN)

    def test_no_token_env_means_anonymous(self):
        self.assertIsNone(resolve_token(None, {}))

    def test_missing_or_blank_variable_is_an_error_that_names_only_the_variable(self):
        for environ in ({}, {"MCP_TEST_TOKEN": "   "}):
            with self.subTest(environ=environ), self.assertRaises(ConfigError) as ctx:
                resolve_token("MCP_TEST_TOKEN", environ)
            self.assertIn("MCP_TEST_TOKEN", str(ctx.exception))


class FakeMcpHandler(BaseHTTPRequestHandler):
    """Serves POST /mcp with the responder installed on the server; records each request."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        # urllib capitalises header names on the wire; compare them case-insensitively.
        headers = {name.lower(): value for name, value in self.headers.items()}
        self.server.seen.append({"headers": headers, "payload": payload})
        status, body = self.server.responder(payload, self.headers)
        if body is None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _ok_responder(payload, headers):
    method = payload.get("method")
    if method == "initialize":
        version = payload["params"]["protocolVersion"]
        return 200, {
            "jsonrpc": "2.0",
            "id": payload["id"],
            "result": {"protocolVersion": version, "capabilities": {"tools": {}}},
        }
    if method == "notifications/initialized":
        return 202, None
    if method == "tools/call":
        text = json.dumps({"results": [{"id": "doc-1"}], "query": payload["params"]["arguments"]})
        return 200, {
            "jsonrpc": "2.0",
            "id": payload["id"],
            "result": {"content": [{"type": "text", "text": text}]},
        }
    return 200, {
        "jsonrpc": "2.0",
        "id": payload.get("id"),
        "error": {"code": -32601, "message": "nope"},
    }


class McpHttpTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMcpHandler)
        self.server.daemon_threads = True
        self.server.seen = []
        self.server.responder = _ok_responder
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        host, port = self.server.server_address[:2]
        self.url = f"http://{host}:{port}/mcp"

    def client(self, token: str | None = TOKEN, timeout: float = 5.0) -> McpClient:
        return McpClient(self.url, token=token, timeout=timeout)


class HandshakeAndCallTests(McpHttpTestCase):
    def test_initialize_then_initialized_then_tools_call(self):
        result = self.client().call_tool("search", {"query": "maturity"})

        self.assertEqual(result["content"][0]["type"], "text")
        methods = [req["payload"].get("method") for req in self.server.seen]
        self.assertEqual(methods, ["initialize", "notifications/initialized", "tools/call"])

    def test_notification_has_no_id_and_call_carries_arguments(self):
        self.client().call_tool("search", {"query": "maturity", "limit": 3})
        init, notify, call = (req["payload"] for req in self.server.seen)
        self.assertIn("id", init)
        self.assertNotIn("id", notify)
        self.assertEqual(
            call["params"], {"name": "search", "arguments": {"query": "maturity", "limit": 3}}
        )
        self.assertEqual(init["params"]["protocolVersion"], "2025-06-18")

    def test_bearer_token_is_sent_on_every_request(self):
        self.client().call_tool("search", {})
        for req in self.server.seen:
            self.assertEqual(req["headers"]["authorization"], f"Bearer {TOKEN}")

    def test_protocol_header_is_sent_only_after_initialize(self):
        self.client().call_tool("search", {})
        init, notify, call = self.server.seen
        self.assertIsNone(init["headers"].get("mcp-protocol-version"))
        self.assertEqual(notify["headers"]["mcp-protocol-version"], "2025-06-18")
        self.assertEqual(call["headers"]["mcp-protocol-version"], "2025-06-18")

    def test_anonymous_call_sends_no_authorization_header(self):
        self.client(token=None).call_tool("search", {})
        for req in self.server.seen:
            self.assertNotIn("authorization", req["headers"])

    def test_negotiated_version_mismatch_is_an_error(self):
        def downgrade(payload, headers):
            if payload.get("method") == "initialize":
                return 200, {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"protocolVersion": "2024-11-05"},
                }
            return 202, None

        self.server.responder = downgrade
        with self.assertRaisesRegex(McpError, "negotiated protocol '2024-11-05'"):
            self.client().call_tool("search", {})

    def test_jsonrpc_error_surfaces_message_and_code(self):
        self.server.responder = lambda payload, headers: (
            200,
            {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {"code": -32602, "message": "Unknown tool: x"},
            },
        )
        with self.assertRaisesRegex(McpError, r"Unknown tool: x \(code -32602\)"):
            self.client().call_tool("x", {})


class HttpErrorTests(McpHttpTestCase):
    def test_401_names_the_rejection_without_echoing_the_token(self):
        self.server.responder = lambda payload, headers: (
            401,
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": 401, "message": "authorization_required"},
            },
        )
        with self.assertRaises(McpError) as ctx:
            self.client().call_tool("search", {})
        self.assertIn("401", str(ctx.exception))
        self.assertIn("token_env", str(ctx.exception))
        self.assertNotIn(TOKEN, str(ctx.exception))

    def test_server_error_includes_the_status_and_message(self):
        self.server.responder = lambda payload, headers: (
            500,
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Internal error."}},
        )
        with self.assertRaisesRegex(McpError, r"HTTP 500: Internal error\."):
            self.client().call_tool("search", {})

    def test_error_with_empty_body_still_reports_the_status(self):
        self.server.responder = lambda payload, headers: (502, None)
        with self.assertRaisesRegex(McpError, "HTTP 502"):
            self.client().call_tool("search", {})

    def test_success_body_that_is_not_json_is_an_error(self):
        class Garbage(FakeMcpHandler):
            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                raw = b"<html>proxy page</html>"
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server.RequestHandlerClass = Garbage
        with self.assertRaisesRegex(McpError, "not JSON"):
            self.client().call_tool("search", {})


class TransportErrorTests(McpHttpTestCase):
    def test_slow_server_raises_a_timeout(self):
        def slow(payload, headers):
            time.sleep(1.0)
            return _ok_responder(payload, headers)

        self.server.responder = slow
        with self.assertRaisesRegex(McpTimeoutError, "within 0.2s"):
            self.client(timeout=0.2).call_tool("search", {})

    def test_refused_connection_is_an_error_but_not_a_timeout(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        client = McpClient(f"http://127.0.0.1:{port}/mcp", token=TOKEN, timeout=2)
        with self.assertRaises(McpError) as ctx:
            client.call_tool("search", {})
        self.assertNotIsInstance(ctx.exception, McpTimeoutError)
        self.assertIn("cannot reach", str(ctx.exception))


class RenderingAndMainTests(McpHttpTestCase):
    def _run(self, config: dict[str, Any], *, argv_extra: list[str] = (), environ=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "call.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = mcp_client.main(
                ["call", "--config", str(path), *argv_extra],
                environ=environ if environ is not None else {"MCP_TEST_TOKEN": TOKEN},
            )
        return code, out.getvalue(), err.getvalue()

    def test_render_text_pretty_prints_json_text_items(self):
        rendered = render_text({"content": [{"type": "text", "text": '{"a": 1}'}]})
        self.assertEqual(rendered, '{\n  "a": 1\n}')

    def test_render_text_keeps_plain_text_and_non_text_items(self):
        rendered = render_text({"content": [{"type": "text", "text": "hello"}, {"type": "image"}]})
        self.assertIn("hello", rendered)
        self.assertIn('"type": "image"', rendered)

    def test_main_prints_readable_output_and_exits_zero(self):
        code, out, err = self._run(
            {"url": self.url, "tool": "search", "token_env": "MCP_TEST_TOKEN"}
        )
        self.assertEqual(code, 0, err)
        self.assertIn('"id": "doc-1"', out)
        self.assertNotIn(TOKEN, out + err)

    def test_main_json_flag_prints_the_raw_result(self):
        code, out, _ = self._run(
            {"url": self.url, "tool": "search", "token_env": "MCP_TEST_TOKEN"},
            argv_extra=["--json"],
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["content"][0]["type"], "text")

    def test_main_exits_one_on_server_failure(self):
        self.server.responder = lambda payload, headers: (401, {"error": {"message": "x"}})
        code, _, err = self._run({"url": self.url, "tool": "search", "token_env": "MCP_TEST_TOKEN"})
        self.assertEqual(code, 1)
        self.assertIn("401", err)

    def test_main_exits_two_when_the_token_variable_is_missing(self):
        code, _, err = self._run(
            {"url": self.url, "tool": "search", "token_env": "MCP_TEST_TOKEN"}, environ={}
        )
        self.assertEqual(code, 2)
        self.assertIn("MCP_TEST_TOKEN", err)

    def test_main_exits_two_on_a_bad_config(self):
        code, _, err = self._run({"url": self.url, "tool": "search", "token": "inline"})
        self.assertEqual(code, 2)
        self.assertIn("token_env", err)

    def test_main_marks_tool_errors_flagged_by_the_server(self):
        self.server.responder = lambda payload, headers: (
            _ok_responder(payload, headers)
            if payload.get("method") != "tools/call"
            else (
                200,
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"content": [{"type": "text", "text": "bad"}], "isError": True},
                },
            )
        )
        code, out, _ = self._run({"url": self.url, "tool": "search", "token_env": "MCP_TEST_TOKEN"})
        self.assertEqual(code, 1)
        self.assertIn("bad", out)


if __name__ == "__main__":
    unittest.main()
