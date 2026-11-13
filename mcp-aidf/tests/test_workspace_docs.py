from __future__ import annotations

import os
import unittest
from pathlib import Path

import app

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_DOCS = WORKSPACE_ROOT / "docs"
SECTIONS = (
    "01-basics",
    "02-architecture",
    "03-commands",
    "04-interfaces",
    "05-models",
    "06-deploy",
)
FULL_ACCESS = app.Principal(namespaces=None)


class WorkspaceDocsLayoutTests(unittest.TestCase):
    """The workspace `docs/` tree, indexed by mcp-aidf with AIDF_REPO_ROOT pointing at the repo."""

    def setUp(self) -> None:
        self.previous_repo_root = os.environ.get("AIDF_REPO_ROOT")
        os.environ["AIDF_REPO_ROOT"] = str(WORKSPACE_ROOT)

    def tearDown(self) -> None:
        if self.previous_repo_root is None:
            os.environ.pop("AIDF_REPO_ROOT", None)
        else:
            os.environ["AIDF_REPO_ROOT"] = self.previous_repo_root

    def _docs_under_sections(self) -> list[dict]:
        return [
            doc
            for doc in app._load_index()
            if any(doc["path"].startswith(f"docs/{section}/") for section in SECTIONS)
        ]

    def test_every_section_directory_exists_with_markdown(self) -> None:
        for section in SECTIONS:
            markdown = list((WORKSPACE_DOCS / section).glob("*.md"))
            self.assertTrue(markdown, section)

    def test_each_section_is_indexed_with_its_name_as_phase(self) -> None:
        docs = self._docs_under_sections()

        for section in SECTIONS:
            in_section = [doc for doc in docs if doc["path"].startswith(f"docs/{section}/")]
            self.assertTrue(in_section, section)
            for doc in in_section:
                self.assertEqual(doc["phase"], section, doc["path"])

    def test_index_page_of_docs_is_a_root_document_not_a_phase(self) -> None:
        doc = next(doc for doc in app._load_index() if doc["path"] == "docs/README.md")

        self.assertEqual(doc["phase"], "root")

    def test_fetch_resolves_documents_at_their_new_paths(self) -> None:
        for doc in self._docs_under_sections():
            fetched = app._fetch_document(doc["path"], principal=FULL_ACCESS)

            self.assertIsNotNone(fetched, doc["path"])
            self.assertEqual(fetched["path"], doc["path"])
            self.assertTrue(fetched["content"].strip(), doc["path"])

    def test_fetch_by_id_resolves_the_same_document(self) -> None:
        doc = next(
            doc for doc in self._docs_under_sections() if doc["path"] == "docs/03-commands/audit.md"
        )

        fetched = app._fetch_document(doc["id"], principal=FULL_ACCESS)

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["path"], "docs/03-commands/audit.md")

    def test_old_overview_path_is_gone_from_the_workspace_tree(self) -> None:
        self.assertIsNone(
            app._fetch_document("docs/00-overview/inference-providers.md", principal=FULL_ACCESS)
        )
        self.assertIsNotNone(
            app._fetch_document("docs/05-models/inference-providers.md", principal=FULL_ACCESS)
        )

    def test_search_finds_commands_and_models_in_their_sections(self) -> None:
        results = app._search_documents("fail-under", limit=10, principal=FULL_ACCESS)
        paths = [result["path"] for result in results]
        self.assertIn("docs/03-commands/audit.md", paths)

        results = app._search_documents("on-premises", limit=10, principal=FULL_ACCESS)
        paths = [result["path"] for result in results]
        self.assertIn("docs/05-models/inference-providers.md", paths)

    def test_canonical_doctrine_contract_stays_under_overview(self) -> None:
        # The shared index contract (contracts/index-contract) and generated repositories keep
        # doctrine under docs/00-overview/. The workspace sections do not change that contract.
        self.assertIn("docs/00-overview/manifesto.md", app.CANONICAL_DOCTRINE_FILES)
        self.assertIn("docs/00-overview/governance.md", app.CANONICAL_DOCTRINE_FILES)
        for path in app.CANONICAL_DOCTRINE_FILES:
            self.assertTrue(path == "MANIFESTO.md" or path.startswith("docs/00-overview/"), path)


if __name__ == "__main__":
    unittest.main()
