from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import unittest
import unittest.mock
from pathlib import Path

import werkzeug.serving

import app

TEST_BEARER_TOKEN = "test-bearer-token-0123456789abcdef"
LATEST_PROTOCOL_VERSION = "2025-06-18"
FULL_ACCESS = app.Principal(namespaces=None)
_token_patch = None


def setUpModule() -> None:
    # Every request in this module authenticates with the fixed test token.
    global _token_patch
    _token_patch = unittest.mock.patch.object(app, "ACTIVE_BEARER_TOKEN", TEST_BEARER_TOKEN)
    _token_patch.start()


def tearDownModule() -> None:
    _token_patch.stop()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class McpAidfIndexingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        self.previous_repo_root = os.environ.get("AIDF_REPO_ROOT")
        os.environ["AIDF_REPO_ROOT"] = str(self.repo_root)

        _write(
            self.repo_root / "README.md",
            "# Demo Repository\n",
        )
        _write(
            self.repo_root / "docs/00-overview/manifesto.md",
            "---\n"
            "id: docs/00-overview/manifesto.md\n"
            "title: KAIDF Manifesto\n"
            "document_class: core-doc\n"
            "phase: 00-overview\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "# KAIDF Manifesto\n\n"
            "Governance and responsibility.\n",
        )
        _write(
            self.repo_root / "docs/00-overview/governance.md",
            "---\n"
            "id: docs/00-overview/governance.md\n"
            "title: Governance\n"
            "document_class: core-doc\n"
            "phase: 00-overview\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "# Governance\n\n"
            "Governance rules and governance structure.\n",
        )
        _write(
            self.repo_root / "docs/00-overview/maturity.md",
            "---\n"
            "id: docs/00-overview/maturity.md\n"
            "title: Maturity\n"
            "document_class: core-doc\n"
            "phase: 00-overview\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "# Maturity\n\n"
            "Overview maturity guidance and maturity model introduction.\n",
        )
        _write(
            self.repo_root / "docs/00-overview/best-practices.md",
            "---\n"
            "id: docs/00-overview/best-practices.md\n"
            "title: Best Practices\n"
            "document_class: core-doc\n"
            "phase: 00-overview\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "# Best Practices\n\n"
            "General guidance for safe and effective AI-assisted work.\n",
        )
        _write(
            self.repo_root / "docs/00-overview/best-practices/seo.md",
            "---\n"
            "id: docs/00-overview/best-practices/seo.md\n"
            "title: SEO Best Practices\n"
            "document_class: core-doc\n"
            "phase: 00-overview\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "# SEO Best Practices\n\n"
            "SEO-focused optimization and search workflow guidance.\n",
        )
        _write(
            self.repo_root / "docs/00-overview/best-practices/research.md",
            "---\n"
            "id: docs/00-overview/best-practices/research.md\n"
            "title: Research Best Practices\n"
            "document_class: core-doc\n"
            "phase: 00-overview\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "# Research Best Practices\n\n"
            "Research workflow guidance and evidence handling.\n",
        )
        _write(
            self.repo_root / "docs/00-overview/decision-rights.md",
            "# Decision Rights\n\nWho decides what.\n",
        )
        _write(
            self.repo_root / "docs/01-intent-constraints/prompts/framing.prompt.md",
            "---\n"
            "id: docs/01-intent-constraints/prompts/framing.prompt.md\n"
            "title: Framing Prompt\n"
            "document_class: prompt-doc\n"
            "phase: 01-intent-constraints\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "# Prompt\n\n"
            "Analyze intent and constraints.\n",
        )
        _write(
            self.repo_root / "docs/10-maturity-model/levels/01-experimental.md",
            "---\n"
            "id: docs/10-maturity-model/levels/01-experimental.md\n"
            "title: Experimental\n"
            "document_class: core-doc\n"
            "phase: 10-maturity-model\n"
            "visibility: internal\n"
            "status: active\n"
            "pack: maturity-model\n"
            "maturity_level: experimental\n"
            "---\n\n"
            "# Experimental\n\n"
            "Early maturity level with strong supervision needs.\n",
        )
        _write(
            self.repo_root / "docs/10-maturity-model/levels/04-managed.md",
            "---\n"
            "id: docs/10-maturity-model/levels/04-managed.md\n"
            "title: Managed\n"
            "document_class: core-doc\n"
            "phase: 10-maturity-model\n"
            "visibility: internal\n"
            "status: active\n"
            "pack: maturity-model\n"
            "maturity_level: managed\n"
            "---\n\n"
            "# Managed\n\n"
            "Managed maturity level with cross-team governance.\n",
        )
        _write(
            self.repo_root / "docs/10-maturity-model/assessment/checklist.md",
            "---\n"
            "id: docs/10-maturity-model/assessment/checklist.md\n"
            "title: Maturity Assessment Checklist\n"
            "document_class: core-doc\n"
            "phase: 10-maturity-model\n"
            "visibility: internal\n"
            "status: active\n"
            "pack: maturity-model\n"
            "assessment_type: checklist\n"
            "---\n\n"
            "# Maturity Assessment Checklist\n\n"
            "Checklist for evidence and review controls.\n",
        )
        _write(
            self.repo_root / "docs/20-ethical-model/README.md",
            "---\n"
            "id: docs/20-ethical-model/README.md\n"
            "title: Ethical Model Pack\n"
            "document_class: core-doc\n"
            "phase: 20-ethical-model\n"
            "visibility: internal\n"
            "status: active\n"
            "pack: ethical-model\n"
            "---\n\n"
            "# Ethical Model Pack\n\n"
            "Ethics, responsibility, transparency, and control guidance.\n",
        )
        _write(
            self.repo_root / "docs/20-ethical-model/principles/transparency.md",
            "---\n"
            "id: docs/20-ethical-model/principles/transparency.md\n"
            "title: Transparency\n"
            "document_class: core-doc\n"
            "phase: 20-ethical-model\n"
            "visibility: internal\n"
            "status: active\n"
            "pack: ethical-model\n"
            "ethical_domain: transparency\n"
            "---\n\n"
            "# Transparency\n\n"
            "Explainable and communicable AI use.\n",
        )
        _write(
            self.repo_root / "docs/20-ethical-model/controls/privacy-checklist.md",
            "---\n"
            "id: docs/20-ethical-model/controls/privacy-checklist.md\n"
            "title: Privacy Checklist\n"
            "document_class: core-doc\n"
            "phase: 20-ethical-model\n"
            "visibility: internal\n"
            "status: active\n"
            "pack: ethical-model\n"
            "ethical_domain: data-protection\n"
            "control_type: checklist\n"
            "---\n\n"
            "# Privacy Checklist\n\n"
            "Checklist for privacy and minimization controls.\n",
        )
        _write(
            self.repo_root / "docs/20-ethical-model/risk/bias-and-harm.md",
            "---\n"
            "id: docs/20-ethical-model/risk/bias-and-harm.md\n"
            "title: Bias And Harm\n"
            "document_class: core-doc\n"
            "phase: 20-ethical-model\n"
            "visibility: internal\n"
            "status: active\n"
            "pack: ethical-model\n"
            "risk_type: bias-and-harm\n"
            "---\n\n"
            "# Bias And Harm\n\n"
            "Bias and harm risk identification.\n",
        )

    def tearDown(self) -> None:
        if self.previous_repo_root is None:
            os.environ.pop("AIDF_REPO_ROOT", None)
        else:
            os.environ["AIDF_REPO_ROOT"] = self.previous_repo_root
        self.tmpdir.cleanup()

    def test_load_index_includes_canonical_doctrine_metadata(self) -> None:
        docs = app._load_index()
        manifesto = next(doc for doc in docs if doc["path"] == "docs/00-overview/manifesto.md")

        self.assertEqual(manifesto["doctrine_category"], "manifesto")
        self.assertTrue(manifesto["canonical_doctrine"])
        self.assertEqual(manifesto["doctrine_priority"], 1000)

    def test_search_ranks_starter_variant_first_for_domain_query(self) -> None:
        results = app._search_documents("seo", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/00-overview/best-practices/seo.md")
        self.assertEqual(results[0]["variant_domain"], "seo")
        self.assertEqual(results[0]["ranking"]["variant_exact"], 450)

    def test_search_keeps_canonical_best_practices_first_for_generic_query(self) -> None:
        results = app._search_documents("best practices", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/best-practices.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertIsNone(results[0]["variant_domain"])
        self.assertEqual(results[1]["path"], "docs/00-overview/best-practices/research.md")

    def test_search_ranks_canonical_doctrine_file_first_for_exact_category_query(self) -> None:
        results = app._search_documents("governance", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/governance.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertEqual(results[0]["doctrine_category"], "governance")
        self.assertEqual(results[0]["ranking"]["doctrine_exact"], 500)
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_search_keeps_canonical_maturity_file_first_for_generic_maturity_query(self) -> None:
        results = app._search_documents("maturity", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/maturity.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertIsNone(results[0]["pack"])
        self.assertEqual(results[1]["pack"], "maturity-model")

    def test_search_ranks_maturity_level_doc_first_for_level_query(self) -> None:
        results = app._search_documents("managed", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/10-maturity-model/levels/04-managed.md")
        self.assertEqual(results[0]["pack"], "maturity-model")
        self.assertEqual(results[0]["maturity_level"], "managed")
        self.assertEqual(results[0]["ranking"]["maturity_level_exact"], 420)

    def test_search_ranks_assessment_doc_first_for_assessment_query(self) -> None:
        results = app._search_documents("checklist", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/10-maturity-model/assessment/checklist.md")
        self.assertEqual(results[0]["assessment_type"], "checklist")
        self.assertEqual(results[0]["ranking"]["assessment_exact"], 180)

    def test_search_ranks_ethical_pack_readme_first_for_ethics_query(self) -> None:
        results = app._search_documents("ethical-model", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/20-ethical-model/README.md")
        self.assertEqual(results[0]["pack"], "ethical-model")
        self.assertEqual(results[0]["ranking"]["pack_exact"], 250)

    def test_search_ranks_ethical_domain_doc_first_for_domain_query(self) -> None:
        results = app._search_documents("transparency", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/20-ethical-model/principles/transparency.md")
        self.assertEqual(results[0]["ethical_domain"], "transparency")
        self.assertEqual(results[0]["ranking"]["ethical_domain_exact"], 420)

    def test_search_ranks_ethical_control_doc_first_for_control_query(self) -> None:
        results = app._search_documents("privacy", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/20-ethical-model/controls/privacy-checklist.md")
        self.assertEqual(results[0]["ethical_domain"], "data-protection")

    def test_search_ranks_ethical_risk_doc_first_for_risk_query(self) -> None:
        results = app._search_documents("bias-and-harm", 10, principal=FULL_ACCESS)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/20-ethical-model/risk/bias-and-harm.md")
        self.assertEqual(results[0]["risk_type"], "bias-and-harm")
        self.assertEqual(results[0]["ranking"]["risk_exact"], 260)

    def test_fetch_supports_canonical_path_lookup(self) -> None:
        doc = app._fetch_document("docs/00-overview/governance.md", principal=FULL_ACCESS)

        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["title"], "Governance")
        self.assertTrue(doc["canonical_doctrine"])
        self.assertEqual(doc["doctrine_category"], "governance")
        self.assertIsNone(doc["variant_domain"])
        self.assertIsNone(doc["pack"])

    def test_fetch_returns_maturity_pack_metadata(self) -> None:
        doc = app._fetch_document(
            "docs/10-maturity-model/levels/01-experimental.md", principal=FULL_ACCESS
        )

        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["pack"], "maturity-model")
        self.assertEqual(doc["maturity_level"], "experimental")
        self.assertIsNone(doc["assessment_type"])

    def test_fetch_returns_ethical_pack_metadata(self) -> None:
        doc = app._fetch_document(
            "docs/20-ethical-model/principles/transparency.md", principal=FULL_ACCESS
        )

        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["pack"], "ethical-model")
        self.assertEqual(doc["ethical_domain"], "transparency")
        self.assertIsNone(doc["control_type"])
        self.assertIsNone(doc["risk_type"])

    def test_mcp_tools_call_returns_ranking_metadata(self) -> None:
        client = app.app.test_client()
        headers = {"Authorization": f"Bearer {TEST_BEARER_TOKEN}"}

        response = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "governance"}},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        text = payload["result"]["content"][0]["text"]
        data = json.loads(text)
        first = data["results"][0]
        self.assertEqual(first["path"], "docs/00-overview/governance.md")
        self.assertIn("ranking", first)
        self.assertIn("score", first)


class McpAidfFrontMatterTests(unittest.TestCase):
    def test_parse_front_matter_accepts_crlf_and_keeps_utf8_titles(self) -> None:
        text = (
            "---\r\n"
            "id: docs/20-ethical-model/principles/transparencia.md\r\n"
            "title: Automação e Maturidade Ética\r\n"
            "---\r\n"
            "\r\n"
            "# Corpo\r\n"
        )

        front_matter, body = app._parse_front_matter(text)

        self.assertEqual(front_matter["title"], "Automação e Maturidade Ética")
        self.assertEqual(front_matter["id"], "docs/20-ethical-model/principles/transparencia.md")
        self.assertEqual(body, "\n# Corpo\n")


class McpAidfProtocolAndErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.app.test_client()
        self.headers = {"Authorization": f"Bearer {TEST_BEARER_TOKEN}"}

    def _post(self, body: object = None, **kwargs):
        return self.client.post("/mcp", headers=self.headers, json=body, **kwargs)

    def test_supported_protocol_versions_are_the_three_published_revisions(self) -> None:
        self.assertEqual(
            app.SUPPORTED_PROTOCOL_VERSIONS, ("2024-11-05", "2025-03-26", "2025-06-18")
        )
        self.assertEqual(app.SUPPORTED_PROTOCOL_VERSIONS[-1], LATEST_PROTOCOL_VERSION)

    def test_initialize_echoes_each_supported_protocol_version(self) -> None:
        for version in app.SUPPORTED_PROTOCOL_VERSIONS:
            with self.subTest(version=version):
                response = self._post(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": version},
                    }
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["result"]["protocolVersion"], version)

    def test_initialize_negotiates_unknown_protocol_version_to_the_latest_one(self) -> None:
        for requested in ("1999-01-01", "2025-11-25"):
            with self.subTest(requested=requested):
                response = self._post(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "initialize",
                        "params": {"protocolVersion": requested},
                    }
                )

                self.assertEqual(
                    response.get_json()["result"]["protocolVersion"], LATEST_PROTOCOL_VERSION
                )

    def test_initialize_without_protocol_version_returns_the_latest_one(self) -> None:
        response = self._post({"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}})

        self.assertEqual(response.get_json()["result"]["protocolVersion"], LATEST_PROTOCOL_VERSION)

    def test_initialize_ignores_non_string_protocol_version(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "initialize",
                "params": {"protocolVersion": ["2024-11-05"]},
            }
        )

        self.assertEqual(response.get_json()["result"]["protocolVersion"], LATEST_PROTOCOL_VERSION)

    def test_unexpected_exception_returns_sanitized_json_rpc_error(self) -> None:
        secret = "/srv/secret/internal-path leaked-detail"
        with unittest.mock.patch.object(app, "_search_documents", side_effect=RuntimeError(secret)):
            response = self._post(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"query": "governance"}},
                }
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.mimetype, "application/json")
        payload = response.get_json()
        self.assertEqual(payload["id"], 5)
        self.assertEqual(payload["error"], {"code": -32603, "message": "Internal error."})
        body = response.get_data(as_text=True)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("leaked-detail", body)
        self.assertNotIn("/srv/secret", body)

    def test_configuration_error_does_not_expose_server_path(self) -> None:
        previous = os.environ.get("AIDF_REPO_ROOT")
        os.environ["AIDF_REPO_ROOT"] = "/nonexistent/private-kaidf-root"
        try:
            response = self._post(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"query": "governance"}},
                }
            )
        finally:
            if previous is None:
                os.environ.pop("AIDF_REPO_ROOT", None)
            else:
                os.environ["AIDF_REPO_ROOT"] = previous

        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], -32603)
        self.assertEqual(payload["error"]["message"], "Internal error.")
        self.assertNotIn("private-kaidf-root", response.get_data(as_text=True))

    def test_invalid_limit_is_a_client_error(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "x", "limit": "many"}},
            }
        )

        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertEqual(payload["error"]["message"], "Invalid params: limit must be an integer.")

    def test_invalid_json_body_returns_parse_error(self) -> None:
        response = self.client.post(
            "/mcp",
            headers={**self.headers, "Content-Type": "application/json"},
            data="{not json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(response.get_json()["error"]["code"], -32700)

    def test_non_object_body_returns_invalid_request(self) -> None:
        response = self._post([1, 2, 3])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], -32600)

    def test_non_object_params_returns_invalid_params(self) -> None:
        response = self._post(
            {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": ["search"]}
        )

        self.assertEqual(response.get_json()["error"]["code"], -32602)


class McpStreamableHttpTransportTests(unittest.TestCase):
    """Notifications, ping, the MCP-Protocol-Version header and GET on the HTTP transport."""

    def setUp(self) -> None:
        self.client = app.app.test_client()
        self.headers = {"Authorization": f"Bearer {TEST_BEARER_TOKEN}"}

    def _post(self, body: object, headers: dict[str, str] | None = None):
        return self.client.post("/mcp", headers={**self.headers, **(headers or {})}, json=body)

    def test_notification_is_accepted_with_202_and_an_empty_body(self) -> None:
        for method in (
            "notifications/initialized",
            "notifications/cancelled",
            "notifications/progress",
            "notifications/some-future-extension",
        ):
            with self.subTest(method=method):
                response = self._post({"jsonrpc": "2.0", "method": method, "params": {}})

                self.assertEqual(response.status_code, 202)
                self.assertEqual(response.get_data(), b"")
                self.assertNotIn("Content-Type", response.headers)

    def test_notification_with_invalid_params_is_still_not_answered(self) -> None:
        # JSON-RPC 2.0 forbids any reply to a notification, an error included.
        response = self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": ["bad"]}
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_data(), b"")

    def test_client_response_is_accepted_with_202_and_an_empty_body(self) -> None:
        # The Streamable HTTP transport treats a JSON-RPC response from the client like a
        # notification. This server never sends requests, so none is expected, but the answer
        # must not be a -32601 error.
        for body in (
            {"jsonrpc": "2.0", "id": 5, "result": {}},
            {"jsonrpc": "2.0", "id": 5, "error": {"code": -32000, "message": "declined"}},
        ):
            with self.subTest(body=body):
                response = self._post(body)

                self.assertEqual(response.status_code, 202)
                self.assertEqual(response.get_data(), b"")

    def test_notification_without_token_is_rejected_with_401(self) -> None:
        response = self.client.post(
            "/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("resource_metadata=", response.headers["WWW-Authenticate"])
        self.assertEqual(response.get_json()["error"]["message"], "authorization_required")

    def test_ping_returns_an_empty_result(self) -> None:
        response = self._post({"jsonrpc": "2.0", "id": "ping-1", "method": "ping"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"jsonrpc": "2.0", "id": "ping-1", "result": {}})

    def test_unknown_method_with_an_id_returns_method_not_found(self) -> None:
        response = self._post({"jsonrpc": "2.0", "id": 9, "method": "resources/list"})

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["id"], 9)
        self.assertEqual(payload["error"]["code"], -32601)
        self.assertEqual(payload["error"]["message"], "Method not found: resources/list")

    def test_supported_protocol_version_header_is_accepted(self) -> None:
        for version in app.SUPPORTED_PROTOCOL_VERSIONS:
            with self.subTest(version=version):
                response = self._post(
                    {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                    {"MCP-Protocol-Version": version},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["result"], {})

    def test_unsupported_protocol_version_header_is_rejected_with_400(self) -> None:
        response = self._post(
            {"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"MCP-Protocol-Version": "1999-01-01"}
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["id"], 1)
        self.assertEqual(payload["error"]["code"], -32600)
        for version in app.SUPPORTED_PROTOCOL_VERSIONS:
            self.assertIn(version, payload["error"]["message"])

    def test_unsupported_protocol_version_header_also_rejects_notifications(self) -> None:
        # The header check is transport-level, like the official SDK server does it, so the
        # 400 wins over the 202 a notification would otherwise get.
        response = self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"MCP-Protocol-Version": "1999-01-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], -32600)

    def test_missing_protocol_version_header_is_served(self) -> None:
        response = self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("tools", response.get_json()["result"])

    def test_initialize_negotiates_regardless_of_the_protocol_version_header(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26"},
            },
            {"MCP-Protocol-Version": "1999-01-01"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["result"]["protocolVersion"], "2025-03-26")

    def test_authentication_is_checked_before_the_protocol_version_header(self) -> None:
        response = self.client.post(
            "/mcp",
            headers={"MCP-Protocol-Version": "1999-01-01"},
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )

        self.assertEqual(response.status_code, 401)

    def test_get_mcp_is_not_allowed(self) -> None:
        # No server-to-client SSE stream and no session: the spec answer is 405.
        response = self.client.get("/mcp", headers=self.headers)

        self.assertEqual(response.status_code, 405)
        self.assertIn("POST", response.headers["Allow"])


CONTRACT_ROOT = Path(__file__).resolve().parents[2] / "contracts" / "index-contract"
CONTRACT_FIELDS = (
    "id",
    "path",
    "title",
    "document_class",
    "phase",
    "visibility",
    "status",
    "doctrine_category",
    "canonical_doctrine",
    "variant_domain",
    "pack",
    "maturity_level",
    "assessment_type",
    "ethical_domain",
    "control_type",
    "risk_type",
)


class McpAidfIndexContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_repo_root = os.environ.get("AIDF_REPO_ROOT")
        os.environ["AIDF_REPO_ROOT"] = str(CONTRACT_ROOT / "corpus")

    def tearDown(self) -> None:
        if self.previous_repo_root is None:
            os.environ.pop("AIDF_REPO_ROOT", None)
        else:
            os.environ["AIDF_REPO_ROOT"] = self.previous_repo_root

    def test_index_matches_shared_contract(self) -> None:
        expected = json.loads((CONTRACT_ROOT / "expected.json").read_text(encoding="utf-8"))

        actual = sorted(app._load_index(), key=lambda doc: doc["path"])

        self.assertEqual(
            [{field: doc[field] for field in CONTRACT_FIELDS} for doc in actual],
            expected,
        )


class McpAidfIndexCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        self.previous_repo_root = os.environ.get("AIDF_REPO_ROOT")
        os.environ["AIDF_REPO_ROOT"] = str(self.repo_root)
        _write(self.repo_root / "README.md", "# Demo\n")
        _write(self.repo_root / "docs/00-overview/governance.md", "# Governance\n\nBody.\n")
        _write(self.repo_root / "docs/01_intent_constraints/README.md", "# Intent\n")
        app._index_cache.update(root=None, signature=None, documents=[])

    def tearDown(self) -> None:
        if self.previous_repo_root is None:
            os.environ.pop("AIDF_REPO_ROOT", None)
        else:
            os.environ["AIDF_REPO_ROOT"] = self.previous_repo_root
        app._index_cache.update(root=None, signature=None, documents=[])
        self.tmpdir.cleanup()

    def _count_parses(self):
        return unittest.mock.patch.object(app, "_load_document", wraps=app._load_document)

    def test_consecutive_requests_do_not_reparse_unchanged_documents(self) -> None:
        with self._count_parses() as parses:
            first = app._load_index()
            parses_after_first = parses.call_count
            for _ in range(5):
                app._load_index()

        self.assertEqual(parses_after_first, 3)
        self.assertEqual(parses.call_count, parses_after_first)
        self.assertEqual(len(first), 3)

    def test_search_and_fetch_share_the_cache(self) -> None:
        with self._count_parses() as parses:
            app._search_documents("governance", principal=FULL_ACCESS)
            app._fetch_document("docs/00-overview/governance.md", principal=FULL_ACCESS)
            app._search_documents("intent", principal=FULL_ACCESS)

        self.assertEqual(parses.call_count, 3)

    def test_edited_file_is_reindexed_on_next_request(self) -> None:
        app._load_index()
        _write(
            self.repo_root / "docs/00-overview/governance.md", "# Governança Revisada\n\nNovo.\n"
        )

        titles = {doc["path"]: doc["title"] for doc in app._load_index()}

        self.assertEqual(titles["docs/00-overview/governance.md"], "Governança Revisada")

    def test_added_and_removed_files_invalidate_the_cache(self) -> None:
        app._load_index()
        _write(self.repo_root / "docs/02_discovery_mapping/README.md", "# Discovery\n")
        (self.repo_root / "docs/01_intent_constraints/README.md").unlink()

        paths = {doc["path"] for doc in app._load_index()}

        self.assertIn("docs/02_discovery_mapping/README.md", paths)
        self.assertNotIn("docs/01_intent_constraints/README.md", paths)

    def test_cache_is_scoped_to_the_configured_repository(self) -> None:
        other = tempfile.TemporaryDirectory()
        try:
            _write(Path(other.name) / "README.md", "# Other\n")
            os.environ["AIDF_REPO_ROOT"] = other.name

            paths = {doc["path"] for doc in app._load_index()}

            self.assertEqual(paths, {"README.md"})
        finally:
            other.cleanup()

    def test_callers_cannot_mutate_cached_records(self) -> None:
        first = app._load_index()
        first[0]["title"] = "tampered"

        second = app._load_index()

        self.assertNotEqual(second[0]["title"], "tampered")


class McpBearerAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.app.test_client()

    def _initialize(self, headers: dict[str, str] | None = None):
        return self.client.post(
            "/mcp",
            headers=headers or {},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )

    def test_request_without_token_is_rejected_with_401(self) -> None:
        response = self._initialize()

        self.assertEqual(response.status_code, 401)
        challenge = response.headers["WWW-Authenticate"]
        self.assertIn("resource_metadata=", challenge)
        self.assertNotIn("invalid_token", challenge)

    def test_wrong_token_is_rejected_with_401_and_invalid_token_challenge(self) -> None:
        response = self._initialize({"Authorization": "Bearer not-the-token"})

        self.assertEqual(response.status_code, 401)
        self.assertIn('error="invalid_token"', response.headers["WWW-Authenticate"])

    def test_correct_token_is_accepted(self) -> None:
        response = self._initialize({"Authorization": f"Bearer {TEST_BEARER_TOKEN}"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["result"]["protocolVersion"], LATEST_PROTOCOL_VERSION)

    def test_non_bearer_scheme_with_the_right_secret_is_rejected(self) -> None:
        response = self._initialize({"Authorization": f"Basic {TEST_BEARER_TOKEN}"})

        self.assertEqual(response.status_code, 401)

    def test_bearer_scheme_is_case_insensitive(self) -> None:
        response = self._initialize({"Authorization": f"bearer {TEST_BEARER_TOKEN}"})

        self.assertEqual(response.status_code, 200)

    def test_empty_active_token_rejects_everything(self) -> None:
        with unittest.mock.patch.object(app, "ACTIVE_BEARER_TOKEN", ""):
            response = self._initialize({"Authorization": "Bearer "})

        self.assertEqual(response.status_code, 401)

    def test_root_requires_the_bearer_token(self) -> None:
        self.assertEqual(self.client.get("/").status_code, 401)
        self.assertEqual(
            self.client.get("/", headers={"Authorization": "Bearer nope"}).status_code, 401
        )
        response = self.client.get("/", headers={"Authorization": f"Bearer {TEST_BEARER_TOKEN}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "MCP Server Running")

    def test_oauth_stub_endpoints_are_removed(self) -> None:
        self.assertEqual(
            self.client.get("/oauth/authorize?redirect_uri=x&state=y").status_code, 404
        )
        self.assertEqual(self.client.post("/oauth/register", json={}).status_code, 404)
        self.assertEqual(self.client.post("/oauth/token", json={}).status_code, 404)
        self.assertEqual(
            self.client.get("/.well-known/oauth-authorization-server").status_code, 404
        )

    def test_protected_resource_metadata_is_kept_without_an_authorization_server(self) -> None:
        with unittest.mock.patch.dict(os.environ):
            os.environ.pop("MCP_PUBLIC_URL", None)
            response = self.client.get("/.well-known/oauth-protected-resource")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["resource"], app.DEFAULT_PUBLIC_URL)
        self.assertNotIn("authorization_servers", payload)

    def test_resolve_bearer_token_uses_the_configured_value(self) -> None:
        self.assertEqual(app._resolve_bearer_token("  my-token  "), "my-token")

    def test_resolve_bearer_token_generates_a_fresh_random_token_when_unset(self) -> None:
        first = app._resolve_bearer_token("")
        second = app._resolve_bearer_token(None)

        self.assertGreaterEqual(len(first), 40)
        self.assertNotEqual(first, second)


class McpPublicUrlTests(unittest.TestCase):
    CUSTOM_URL = "https://mcp.example.test"

    def setUp(self) -> None:
        self.client = app.app.test_client()
        env_patch = unittest.mock.patch.dict(os.environ)
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def _unauthenticated_initialize(self, headers: dict[str, str] | None = None):
        return self.client.post(
            "/mcp",
            headers=headers or {},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )

    def test_401_points_at_the_configured_public_url(self) -> None:
        os.environ["MCP_PUBLIC_URL"] = self.CUSTOM_URL
        metadata = f"{self.CUSTOM_URL}/.well-known/oauth-protected-resource"

        response = self._unauthenticated_initialize()

        self.assertEqual(response.status_code, 401)
        self.assertIn(f'resource_metadata="{metadata}"', response.headers["WWW-Authenticate"])
        body_challenge = response.get_json()["error"]["data"]["_meta"]["mcp/www_authenticate"]
        self.assertIn(f'resource_metadata="{metadata}"', body_challenge)
        self.assertNotIn("kobkob.org", response.headers["WWW-Authenticate"] + body_challenge)

    def test_root_401_points_at_the_configured_public_url(self) -> None:
        os.environ["MCP_PUBLIC_URL"] = f"{self.CUSTOM_URL}/"

        response = self.client.get("/")

        self.assertEqual(response.status_code, 401)
        self.assertIn(
            f'resource_metadata="{self.CUSTOM_URL}/.well-known/oauth-protected-resource"',
            response.headers["WWW-Authenticate"],
        )

    def test_protected_resource_metadata_uses_the_configured_public_url(self) -> None:
        os.environ["MCP_PUBLIC_URL"] = f"{self.CUSTOM_URL}/"

        payload = self.client.get("/.well-known/oauth-protected-resource").get_json()

        self.assertEqual(payload["resource"], self.CUSTOM_URL)
        self.assertEqual(payload["resource_documentation"], f"{self.CUSTOM_URL}/docs")

    def test_falls_back_to_local_url_when_the_variable_is_unset(self) -> None:
        os.environ.pop("MCP_PUBLIC_URL", None)
        metadata = f"{app.DEFAULT_PUBLIC_URL}/.well-known/oauth-protected-resource"

        response = self._unauthenticated_initialize()
        payload = self.client.get("/.well-known/oauth-protected-resource").get_json()

        self.assertEqual(app.DEFAULT_PUBLIC_URL, "http://localhost:7777")
        self.assertIn(f'resource_metadata="{metadata}"', response.headers["WWW-Authenticate"])
        self.assertEqual(payload["resource"], app.DEFAULT_PUBLIC_URL)

    def test_falls_back_to_local_url_when_the_variable_is_blank(self) -> None:
        os.environ["MCP_PUBLIC_URL"] = "   "

        self.assertEqual(app._public_url(), app.DEFAULT_PUBLIC_URL)

    def test_request_host_header_is_never_reflected(self) -> None:
        os.environ.pop("MCP_PUBLIC_URL", None)

        response = self._unauthenticated_initialize({"Host": "attacker.example"})

        self.assertNotIn("attacker.example", response.headers["WWW-Authenticate"])
        self.assertNotIn("attacker.example", response.get_data(as_text=True))


def _visibility_doc(visibility: str | None, title: str) -> str:
    field = "" if visibility is None else f"visibility: {visibility}\n"
    return (
        f"---\nid: docs/acl/{title.lower().replace(' ', '-')}.md\ntitle: {title}\n"
        f"document_class: core-doc\nphase: 00-overview\nstatus: active\n{field}---\n\n"
        f"# {title}\n\nmarker-{title.lower().replace(' ', '-')}\n"
    )


class McpVisibilityAclTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        self.previous_repo_root = os.environ.get("AIDF_REPO_ROOT")
        os.environ["AIDF_REPO_ROOT"] = str(self.repo_root)
        _write(self.repo_root / "README.md", "# Demo\n")
        _write(self.repo_root / "docs/acl/public-note.md", _visibility_doc("public", "Public Note"))
        _write(
            self.repo_root / "docs/acl/internal-note.md",
            _visibility_doc("internal", "Internal Note"),
        )
        _write(
            self.repo_root / "docs/acl/private-note.md", _visibility_doc("private", "Private Note")
        )
        _write(self.repo_root / "docs/acl/typo-note.md", _visibility_doc("publc", "Typo Note"))
        _write(
            self.repo_root / "docs/acl/unlabelled-note.md", _visibility_doc(None, "Unlabelled Note")
        )
        app._index_cache.update(root=None, signature=None, documents=[])
        self.client = app.app.test_client()

    def tearDown(self) -> None:
        if self.previous_repo_root is None:
            os.environ.pop("AIDF_REPO_ROOT", None)
        else:
            os.environ["AIDF_REPO_ROOT"] = self.previous_repo_root
        app._index_cache.update(root=None, signature=None, documents=[])
        self.tmpdir.cleanup()

    def _search_paths(self, principal) -> set[str]:
        results = app._search_documents("marker", 50, principal=principal)
        return {doc["path"] for doc in results}

    def _call(self, name: str, arguments: dict) -> object:
        return self.client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {TEST_BEARER_TOKEN}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )

    def test_visibility_table(self) -> None:
        cases = [
            ("public", False, True),
            ("public", True, True),
            ("internal", False, False),
            ("internal", True, True),
            ("private", False, False),
            ("private", True, False),
            ("publc", False, False),
            ("publc", True, False),
        ]
        for visibility, authenticated, expected in cases:
            with self.subTest(visibility=visibility, authenticated=authenticated):
                self.assertIs(app._is_visible({"visibility": visibility}, authenticated), expected)

    def test_a_document_without_visibility_key_is_public(self) -> None:
        self.assertTrue(app._is_visible({}, False))

    def test_unauthenticated_search_returns_only_public_documents(self) -> None:
        # The index gives a document with no visibility field the contract default, "internal",
        # so it is hidden from unauthenticated callers (fail-closed).
        self.assertEqual(self._search_paths(None), {"docs/acl/public-note.md"})

    def test_authenticated_search_adds_internal_but_never_private(self) -> None:
        paths = self._search_paths(FULL_ACCESS)

        self.assertIn("docs/acl/internal-note.md", paths)
        self.assertIn("docs/acl/public-note.md", paths)
        self.assertNotIn("docs/acl/private-note.md", paths)
        self.assertNotIn("docs/acl/typo-note.md", paths)

    def test_fetch_hides_private_and_unknown_visibility_even_when_authenticated(self) -> None:
        for doc_id in ("docs/acl/private-note.md", "docs/acl/typo-note.md"):
            with self.subTest(doc_id=doc_id):
                self.assertIsNone(app._fetch_document(doc_id, principal=FULL_ACCESS))

    def test_fetch_hides_internal_from_unauthenticated_callers(self) -> None:
        self.assertIsNone(app._fetch_document("docs/acl/internal-note.md", principal=None))
        self.assertIsNotNone(
            app._fetch_document("docs/acl/internal-note.md", principal=FULL_ACCESS)
        )

    def test_route_search_never_returns_private_content(self) -> None:
        response = self._call("search", {"query": "marker", "limit": 50})

        self.assertEqual(response.status_code, 200)
        text = response.get_json()["result"]["content"][0]["text"]
        self.assertNotIn("marker-private-note", text)
        self.assertNotIn("marker-typo-note", text)
        self.assertIn("marker-internal-note", text)

    def test_route_fetch_of_private_document_looks_like_a_missing_one(self) -> None:
        private = self._call("fetch", {"id": "docs/acl/private-note.md"})
        missing = self._call("fetch", {"id": "docs/acl/does-not-exist.md"})

        self.assertEqual(private.status_code, missing.status_code)
        self.assertEqual(private.get_json()["error"]["code"], missing.get_json()["error"]["code"])
        self.assertEqual(
            private.get_json()["error"]["message"], "Document not found: docs/acl/private-note.md"
        )
        self.assertNotIn("marker-private-note", private.get_data(as_text=True))

    def test_route_rejects_unauthenticated_requests_before_any_document_is_read(self) -> None:
        response = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "marker"}},
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("marker", response.get_data(as_text=True))


TENANT_A_TOKEN = "tenant-a-token-0123456789abcdef"
TENANT_B_TOKEN = "tenant-b-token-0123456789abcdef"


class McpTenantScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        self.previous_repo_root = os.environ.get("AIDF_REPO_ROOT")
        os.environ["AIDF_REPO_ROOT"] = str(self.repo_root)
        _write(self.repo_root / "README.md", "# Demo\n")
        _write(
            self.repo_root / "docs/acme/a-internal.md",
            _namespaced_doc("acme", "internal", "Acme Internal"),
        )
        _write(
            self.repo_root / "docs/acme/a-private.md",
            _namespaced_doc("acme", "private", "Acme Private"),
        )
        _write(
            self.repo_root / "docs/beta/b-internal.md",
            _namespaced_doc("beta", "internal", "Beta Internal"),
        )
        _write(
            self.repo_root / "docs/shared/public.md",
            _namespaced_doc(None, "public", "Shared Public"),
        )
        _write(self.repo_root / "docs/shared/plain.md", _namespaced_doc(None, None, "Shared Plain"))
        _write(
            self.repo_root / "docs/shared/private.md",
            _namespaced_doc(None, "private", "Shared Private"),
        )
        app._index_cache.update(root=None, signature=None, documents=[])
        self.scopes = {
            TENANT_A_TOKEN: frozenset({"acme"}),
            TENANT_B_TOKEN: frozenset({"beta"}),
        }
        self._scope_patch = unittest.mock.patch.object(app, "TOKEN_SCOPES", self.scopes)
        self._scope_patch.start()
        self.client = app.app.test_client()

    def tearDown(self) -> None:
        self._scope_patch.stop()
        if self.previous_repo_root is None:
            os.environ.pop("AIDF_REPO_ROOT", None)
        else:
            os.environ["AIDF_REPO_ROOT"] = self.previous_repo_root
        app._index_cache.update(root=None, signature=None, documents=[])
        self.tmpdir.cleanup()

    def _search(self, token: str, query: str = "marker") -> set[str]:
        response = self.client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": query, "limit": 50}},
            },
        )
        results = json.loads(response.get_json()["result"]["content"][0]["text"])["results"]
        return {item["path"] for item in results}

    def _fetch(self, token: str, doc_id: str):
        return self.client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "fetch", "arguments": {"id": doc_id}},
            },
        )

    def test_scoped_token_searches_its_namespace_plus_shared_public_documents(self) -> None:
        self.assertEqual(
            self._search(TENANT_A_TOKEN), {"docs/acme/a-internal.md", "docs/shared/public.md"}
        )
        self.assertEqual(
            self._search(TENANT_B_TOKEN), {"docs/beta/b-internal.md", "docs/shared/public.md"}
        )

    def test_primary_token_is_unrestricted_but_still_hides_private(self) -> None:
        self.assertEqual(
            self._search(TEST_BEARER_TOKEN),
            {
                "docs/acme/a-internal.md",
                "docs/beta/b-internal.md",
                "docs/shared/public.md",
                "docs/shared/plain.md",
            },
        )

    def test_scoped_token_cannot_fetch_another_tenant_and_gets_the_missing_document_error(
        self,
    ) -> None:
        cross = self._fetch(TENANT_A_TOKEN, "docs/beta/b-internal.md")
        missing = self._fetch(TENANT_A_TOKEN, "docs/beta/does-not-exist.md")

        self.assertEqual(cross.status_code, 404)
        self.assertEqual(cross.get_json()["error"]["code"], missing.get_json()["error"]["code"])
        self.assertEqual(
            cross.get_json()["error"]["message"], "Document not found: docs/beta/b-internal.md"
        )
        self.assertNotIn("Beta Internal", cross.get_data(as_text=True))

    def test_scoped_token_fetches_its_own_internal_document(self) -> None:
        response = self._fetch(TENANT_A_TOKEN, "docs/acme/a-internal.md")

        self.assertEqual(response.status_code, 200)

    def test_shared_public_documents_are_readable_by_every_tenant(self) -> None:
        response = self._fetch(TENANT_B_TOKEN, "docs/shared/public.md")

        self.assertEqual(response.status_code, 200)

    def test_internal_and_private_documents_without_a_namespace_stay_with_the_primary_token(
        self,
    ) -> None:
        tenant = app.Principal(frozenset({"acme"}))
        self.assertIsNone(app._fetch_document("docs/shared/plain.md", principal=tenant))
        self.assertIsNone(app._fetch_document("docs/shared/private.md", principal=tenant))
        self.assertIsNotNone(app._fetch_document("docs/shared/plain.md", principal=FULL_ACCESS))
        self.assertNotIn("docs/shared/private.md", self._search(TENANT_A_TOKEN, "shared"))

    def test_helpers_treat_a_none_principal_as_unauthenticated(self) -> None:
        self.assertEqual(app._fetch_document("docs/acme/a-internal.md", principal=None), None)
        self.assertIsNotNone(app._fetch_document("docs/shared/public.md", principal=None))

    def test_resolve_principal_maps_each_token_to_its_scope(self) -> None:
        self.assertEqual(app._resolve_principal(f"Bearer {TEST_BEARER_TOKEN}"), app.Principal(None))
        self.assertEqual(
            app._resolve_principal(f"bearer {TENANT_A_TOKEN}"),
            app.Principal(frozenset({"acme"})),
        )
        self.assertIsNone(app._resolve_principal("Bearer unknown-token"))
        self.assertIsNone(app._resolve_principal(f"Basic {TENANT_A_TOKEN}"))
        self.assertIsNone(app._resolve_principal(None))

    def test_non_ascii_credentials_are_rejected_without_an_error(self) -> None:
        response = self.client.get("/", headers={"Authorization": "Bearer caf\u00e9-token"})

        self.assertEqual(response.status_code, 401)

    def test_parse_token_scopes(self) -> None:
        primary = "primary-token-0123456789abcdef"
        parsed = app._load_token_scopes(json.dumps({"  tok-1  ": [" acme ", "beta"]}), primary)
        self.assertEqual(parsed, {"tok-1": frozenset({"acme", "beta"})})
        self.assertEqual(app._load_token_scopes("   ", primary), {})

    def test_invalid_token_scope_configuration_stops_the_server(self) -> None:
        primary = "primary-token-0123456789abcdef"
        bad_values = [
            "{not json",
            "[]",
            json.dumps({"": ["acme"]}),
            json.dumps({"tok": []}),
            json.dumps({"tok": "acme"}),
            json.dumps({"tok": [""]}),
            json.dumps({primary: ["acme"]}),
        ]
        for raw in bad_values:
            with self.subTest(raw=raw):
                with self.assertRaises(RuntimeError):
                    app._load_token_scopes(raw, primary)


def _namespaced_doc(namespace: str | None, visibility: str | None, title: str) -> str:
    lines = ["---", f"id: docs/{title.lower().replace(' ', '-')}.md", f"title: {title}"]
    if namespace is not None:
        lines.append(f"namespace: {namespace}")
    if visibility is not None:
        lines.append(f"visibility: {visibility}")
    body = f"marker-{title.lower().replace(' ', '-')}"
    return "\n".join(lines) + f"\n---\n\n# {title}\n\n{body}\n"


class _QuietRequestHandler(werkzeug.serving.WSGIRequestHandler):
    def log_request(self, *args: object, **kwargs: object) -> None:
        pass


class McpSdkClientIntegrationTests(unittest.TestCase):
    """The official MCP Python SDK client, over real HTTP, against this server.

    The SDK sends ``initialize``, then the ``notifications/initialized`` notification (it fails
    on a non-2xx answer), then stamps every request with ``MCP-Protocol-Version``. werkzeug
    serves the Flask app on a loopback port in a background thread for the duration.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = tempfile.TemporaryDirectory()
        repo_root = Path(cls.tmpdir.name)
        _write(repo_root / "README.md", "# Demo\n")
        _write(
            repo_root / "docs/00-overview/governance.md",
            "---\n"
            "id: docs/00-overview/governance.md\n"
            "title: Governance\n"
            "visibility: internal\n"
            "---\n\n"
            "# Governance\n\n"
            "Governance rules.\n",
        )
        cls.previous_repo_root = os.environ.get("AIDF_REPO_ROOT")
        os.environ["AIDF_REPO_ROOT"] = str(repo_root)
        cls.server = werkzeug.serving.make_server(
            "127.0.0.1", 0, app.app, threaded=True, request_handler=_QuietRequestHandler
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/mcp"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        if cls.previous_repo_root is None:
            os.environ.pop("AIDF_REPO_ROOT", None)
        else:
            os.environ["AIDF_REPO_ROOT"] = cls.previous_repo_root
        cls.tmpdir.cleanup()

    def test_sdk_client_initializes_lists_tools_and_searches(self) -> None:
        # `mcp` is a dev extra (pyproject.toml). Imported here so a missing package fails
        # this test alone instead of the whole module.
        from mcp import ClientSession
        from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

        async def scenario():
            headers = {"Authorization": f"Bearer {TEST_BEARER_TOKEN}"}
            async with create_mcp_http_client(headers=headers) as http_client:
                async with streamable_http_client(self.url, http_client=http_client) as streams:
                    read_stream, write_stream = streams
                    async with ClientSession(read_stream, write_stream) as session:
                        initialized = await session.initialize()
                        tools = await session.list_tools()
                        search = await session.call_tool("search", {"query": "governance"})
                        return initialized, tools, search

        initialized, tools, search = asyncio.run(scenario())

        self.assertEqual(initialized.protocol_version, LATEST_PROTOCOL_VERSION)
        self.assertEqual(initialized.server_info.name, "mcp-aidf")
        self.assertEqual(initialized.server_info.version, app.SERVER_VERSION)
        self.assertEqual(
            {tool.name for tool in tools.tools},
            {"search", "fetch", "get_maturity_scorecard", "evaluate_repository_maturity"},
        )
        self.assertFalse(search.is_error)
        payload = json.loads(search.content[0].text)
        self.assertEqual(payload["results"][0]["path"], "docs/00-overview/governance.md")

    def test_sdk_client_without_the_bearer_token_is_rejected(self) -> None:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        from mcp.shared.exceptions import MCPError

        async def scenario():
            async with streamable_http_client(self.url) as streams:
                read_stream, write_stream = streams
                async with ClientSession(read_stream, write_stream) as session:
                    return await session.initialize()

        # The SDK runs the transport in anyio task groups, so the server's JSON-RPC error
        # surfaces as an MCPError nested in ExceptionGroups, possibly next to other
        # exceptions from the same task group. Only the server's contract is asserted here
        # (the 401 code); the exact error message and the shape of the SDK's exception tree
        # are the SDK's business and are pinned by the plain HTTP tests instead.
        with self.assertRaises(Exception) as caught:
            asyncio.run(scenario())

        leaves = _leaf_exceptions(caught.exception)
        mcp_errors = [leaf for leaf in leaves if isinstance(leaf, MCPError)]
        self.assertTrue(mcp_errors, leaves)
        self.assertIn(401, {error.code for error in mcp_errors})


def _leaf_exceptions(exc: BaseException) -> list[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        return [leaf for sub in exc.exceptions for leaf in _leaf_exceptions(sub)]
    return [exc]


if __name__ == "__main__":
    unittest.main()
