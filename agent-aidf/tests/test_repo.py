from __future__ import annotations

import json
from pathlib import Path

from agent_aidf.repo import _parse_front_matter, load_documents

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


def test_parse_front_matter_accepts_crlf_line_endings() -> None:
    text = (
        "---\r\n"
        "id: docs/20-ethical-model/principles/transparencia.md\r\n"
        "title: Maturidade Ética\r\n"
        "phase: 20-ethical-model\r\n"
        "---\r\n"
        "\r\n"
        "# Corpo\r\n"
    )

    front_matter, body = _parse_front_matter(text)

    assert front_matter == {
        "id": "docs/20-ethical-model/principles/transparencia.md",
        "title": "Maturidade Ética",
        "phase": "20-ethical-model",
    }
    assert body == "\n# Corpo\n"


def test_parse_front_matter_keeps_portuguese_titles_from_utf8_file(tmp_path: Path) -> None:
    doc = tmp_path / "automacao.md"
    doc.write_bytes(
        "---\r\ntitle: Automação e Maturidade Ética\r\n---\r\n\r\n# Corpo\r\n".encode("utf-8")
    )

    front_matter, _ = _parse_front_matter(doc.read_text(encoding="utf-8"))

    assert front_matter["title"] == "Automação e Maturidade Ética"


def test_parse_front_matter_without_block_returns_empty_metadata_and_body() -> None:
    front_matter, body = _parse_front_matter("# Sem front matter\r\n")

    assert front_matter == {}
    assert body == "# Sem front matter\n"


def test_index_matches_shared_contract() -> None:
    expected = json.loads((CONTRACT_ROOT / "expected.json").read_text(encoding="utf-8"))

    documents = sorted(load_documents(CONTRACT_ROOT / "corpus"), key=lambda doc: doc.path)

    assert [
        {field: getattr(doc, field) for field in CONTRACT_FIELDS} for doc in documents
    ] == expected
