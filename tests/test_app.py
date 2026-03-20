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

    def test_search_ranks_canonical_doctrine_file_first_for_exact_category_query(self) -> None:
        results = app._search_documents("governance", 10)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]["path"], "docs/00-overview/governance.md")
        self.assertTrue(results[0]["canonical_doctrine"])
        self.assertEqual(results[0]["doctrine_category"], "governance")
        self.assertEqual(results[0]["ranking"]["doctrine_exact"], 500)
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_fetch_supports_canonical_path_lookup(self) -> None:
        doc = app._fetch_document("docs/00-overview/governance.md")

        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["title"], "Governance")
        self.assertTrue(doc["canonical_doctrine"])
        self.assertEqual(doc["doctrine_category"], "governance")

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
