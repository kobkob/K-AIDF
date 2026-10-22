from __future__ import annotations

import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import app

TEST_BEARER_TOKEN = "test-bearer-token-0123456789abcdef"
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
        results = app._search_documents("seo", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/00-overview/best-practices/seo.md")
        self.assertEqual(results[0]["variant_domain"], "seo")
        self.assertEqual(results[0]["ranking"]["variant_exact"], 450)

    def test_search_keeps_canonical_best_practices_first_for_generic_query(self) -> None:
        results = app._search_documents("best practices", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/best-practices.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertIsNone(results[0]["variant_domain"])
        self.assertEqual(results[1]["path"], "docs/00-overview/best-practices/research.md")

    def test_search_ranks_canonical_doctrine_file_first_for_exact_category_query(self) -> None:
        results = app._search_documents("governance", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/governance.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertEqual(results[0]["doctrine_category"], "governance")
        self.assertEqual(results[0]["ranking"]["doctrine_exact"], 500)
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_search_keeps_canonical_maturity_file_first_for_generic_maturity_query(self) -> None:
        results = app._search_documents("maturity", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/maturity.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertIsNone(results[0]["pack"])
        self.assertEqual(results[1]["pack"], "maturity-model")

    def test_search_ranks_maturity_level_doc_first_for_level_query(self) -> None:
        results = app._search_documents("managed", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/10-maturity-model/levels/04-managed.md")
        self.assertEqual(results[0]["pack"], "maturity-model")
        self.assertEqual(results[0]["maturity_level"], "managed")
        self.assertEqual(results[0]["ranking"]["maturity_level_exact"], 420)

    def test_search_ranks_assessment_doc_first_for_assessment_query(self) -> None:
        results = app._search_documents("checklist", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/10-maturity-model/assessment/checklist.md")
        self.assertEqual(results[0]["assessment_type"], "checklist")
        self.assertEqual(results[0]["ranking"]["assessment_exact"], 180)

    def test_search_ranks_ethical_pack_readme_first_for_ethics_query(self) -> None:
        results = app._search_documents("ethical-model", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/20-ethical-model/README.md")
        self.assertEqual(results[0]["pack"], "ethical-model")
        self.assertEqual(results[0]["ranking"]["pack_exact"], 250)

    def test_search_ranks_ethical_domain_doc_first_for_domain_query(self) -> None:
        results = app._search_documents("transparency", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/20-ethical-model/principles/transparency.md")
        self.assertEqual(results[0]["ethical_domain"], "transparency")
        self.assertEqual(results[0]["ranking"]["ethical_domain_exact"], 420)

    def test_search_ranks_ethical_control_doc_first_for_control_query(self) -> None:
        results = app._search_documents("privacy", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/20-ethical-model/controls/privacy-checklist.md")
        self.assertEqual(results[0]["ethical_domain"], "data-protection")

    def test_search_ranks_ethical_risk_doc_first_for_risk_query(self) -> None:
        results = app._search_documents("bias-and-harm", 10, is_authenticated=True)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/20-ethical-model/risk/bias-and-harm.md")
        self.assertEqual(results[0]["risk_type"], "bias-and-harm")
        self.assertEqual(results[0]["ranking"]["risk_exact"], 260)

    def test_fetch_supports_canonical_path_lookup(self) -> None:
        doc = app._fetch_document("docs/00-overview/governance.md", is_authenticated=True)

        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["title"], "Governance")
        self.assertTrue(doc["canonical_doctrine"])
        self.assertEqual(doc["doctrine_category"], "governance")
        self.assertIsNone(doc["variant_domain"])
        self.assertIsNone(doc["pack"])

    def test_fetch_returns_maturity_pack_metadata(self) -> None:
        doc = app._fetch_document(
            "docs/10-maturity-model/levels/01-experimental.md", is_authenticated=True
        )

        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["pack"], "maturity-model")
        self.assertEqual(doc["maturity_level"], "experimental")
        self.assertIsNone(doc["assessment_type"])

    def test_fetch_returns_ethical_pack_metadata(self) -> None:
        doc = app._fetch_document(
            "docs/20-ethical-model/principles/transparency.md", is_authenticated=True
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

    def test_initialize_echoes_supported_protocol_version(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )

        self.assertEqual(response.get_json()["result"]["protocolVersion"], "2024-11-05")

    def test_initialize_negotiates_unknown_protocol_version_to_supported_one(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {"protocolVersion": "1999-01-01"},
            }
        )

        self.assertEqual(response.get_json()["result"]["protocolVersion"], "2024-11-05")

    def test_initialize_without_protocol_version_returns_supported_one(self) -> None:
        response = self._post({"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}})

        self.assertEqual(response.get_json()["result"]["protocolVersion"], "2024-11-05")

    def test_initialize_ignores_non_string_protocol_version(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "initialize",
                "params": {"protocolVersion": ["2024-11-05"]},
            }
        )

        self.assertEqual(response.get_json()["result"]["protocolVersion"], "2024-11-05")

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
            app._search_documents("governance", is_authenticated=True)
            app._fetch_document("docs/00-overview/governance.md", is_authenticated=True)
            app._search_documents("intent", is_authenticated=True)

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
        self.assertEqual(response.get_json()["result"]["protocolVersion"], "2024-11-05")

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
        response = self.client.get("/.well-known/oauth-protected-resource")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["resource"], app.DEFAULT_RESOURCE)
        self.assertNotIn("authorization_servers", payload)

    def test_resolve_bearer_token_uses_the_configured_value(self) -> None:
        self.assertEqual(app._resolve_bearer_token("  my-token  "), "my-token")

    def test_resolve_bearer_token_generates_a_fresh_random_token_when_unset(self) -> None:
        first = app._resolve_bearer_token("")
        second = app._resolve_bearer_token(None)

        self.assertGreaterEqual(len(first), 40)
        self.assertNotEqual(first, second)


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

    def _search_paths(self, is_authenticated: bool) -> set[str]:
        results = app._search_documents("marker", 50, is_authenticated=is_authenticated)
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
        self.assertEqual(self._search_paths(False), {"docs/acl/public-note.md"})

    def test_authenticated_search_adds_internal_but_never_private(self) -> None:
        paths = self._search_paths(True)

        self.assertIn("docs/acl/internal-note.md", paths)
        self.assertIn("docs/acl/public-note.md", paths)
        self.assertNotIn("docs/acl/private-note.md", paths)
        self.assertNotIn("docs/acl/typo-note.md", paths)

    def test_fetch_hides_private_and_unknown_visibility_even_when_authenticated(self) -> None:
        for doc_id in ("docs/acl/private-note.md", "docs/acl/typo-note.md"):
            with self.subTest(doc_id=doc_id):
                self.assertIsNone(app._fetch_document(doc_id, is_authenticated=True))

    def test_fetch_hides_internal_from_unauthenticated_callers(self) -> None:
        self.assertIsNone(app._fetch_document("docs/acl/internal-note.md", is_authenticated=False))
        self.assertIsNotNone(
            app._fetch_document("docs/acl/internal-note.md", is_authenticated=True)
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


if __name__ == "__main__":
    unittest.main()
