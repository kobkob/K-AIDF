from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import app


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
            "# Decision Rights\n\n"
            "Who decides what.\n",
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
        results = app._search_documents("seo", 10)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/00-overview/best-practices/seo.md")
        self.assertEqual(results[0]["variant_domain"], "seo")
        self.assertEqual(results[0]["ranking"]["variant_exact"], 450)

    def test_search_keeps_canonical_best_practices_first_for_generic_query(self) -> None:
        results = app._search_documents("best practices", 10)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/best-practices.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertIsNone(results[0]["variant_domain"])
        self.assertEqual(results[1]["path"], "docs/00-overview/best-practices/research.md")

    def test_search_ranks_canonical_doctrine_file_first_for_exact_category_query(self) -> None:
        results = app._search_documents("governance", 10)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/governance.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertEqual(results[0]["doctrine_category"], "governance")
        self.assertEqual(results[0]["ranking"]["doctrine_exact"], 500)
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_search_keeps_canonical_maturity_file_first_for_generic_maturity_query(self) -> None:
        results = app._search_documents("maturity", 10)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/maturity.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertIsNone(results[0]["pack"])
        self.assertEqual(results[1]["pack"], "maturity-model")

    def test_search_ranks_maturity_level_doc_first_for_level_query(self) -> None:
        results = app._search_documents("managed", 10)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/10-maturity-model/levels/04-managed.md")
        self.assertEqual(results[0]["pack"], "maturity-model")
        self.assertEqual(results[0]["maturity_level"], "managed")
        self.assertEqual(results[0]["ranking"]["maturity_level_exact"], 420)

    def test_search_ranks_assessment_doc_first_for_assessment_query(self) -> None:
        results = app._search_documents("checklist", 10)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "docs/10-maturity-model/assessment/checklist.md")
        self.assertEqual(results[0]["assessment_type"], "checklist")
        self.assertEqual(results[0]["ranking"]["assessment_exact"], 180)

    def test_fetch_supports_canonical_path_lookup(self) -> None:
        doc = app._fetch_document("docs/00-overview/governance.md")

        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["title"], "Governance")
        self.assertTrue(doc["canonical_doctrine"])
        self.assertEqual(doc["doctrine_category"], "governance")
        self.assertIsNone(doc["variant_domain"])
        self.assertIsNone(doc["pack"])

    def test_fetch_returns_maturity_pack_metadata(self) -> None:
        doc = app._fetch_document("docs/10-maturity-model/levels/01-experimental.md")

        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["pack"], "maturity-model")
        self.assertEqual(doc["maturity_level"], "experimental")
        self.assertIsNone(doc["assessment_type"])

    def test_mcp_tools_call_returns_ranking_metadata(self) -> None:
        client = app.app.test_client()
        headers = {"Authorization": "Bearer test"}

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


if __name__ == "__main__":
    unittest.main()
