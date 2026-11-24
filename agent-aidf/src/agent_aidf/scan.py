"""kob scan: bootstrap a K-AIDF project from the material it already has.

Four stages, each a function here:

1. Extract: walk the project's files (git's view when the project is a repository, so .gitignore
   applies), detect languages, manifests, Dockerfiles, CI workflows and apps. A credential in any
   file blocks the whole scan; only the kind of credential is reported.
2. Chunk: Markdown by its headings (model_setup.chunk_markdown), code by its top-level definitions
   (Python) or by fixed windows (other languages). Documents the visibility rules withhold stay out.
3. Bootstrap: deterministic drafts of the discovery and design documents, built from the inventory
   and the phase templates. Each draft must pass the same checks as the mentor's drafts before it
   is written. Drafts never overwrite an existing file.
4. Fork: a RAG corpus (Markdown files under .kaidf/rag/corpus) and a synthetic QLoRA dataset
   (.kaidf/datasets/qlora-corpus.jsonl, one auditable row per chunk, with the source path and its
   SHA-256). When .kaidf/model-setup.json exists, the scan points its rag and qlora layers at them,
   after the profile has passed the schema.

Nothing is written by extraction. `write_outputs` is the only function that touches the disk.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .artifacts import document_problems, phase_templates, template_sections
from .audit import find_credentials
from .model_setup import (
    Chunk,
    ModelSetupError,
    chunk_markdown,
    load_profile,
    load_rag_chunks,
    profile_file,
    refusal,
    validate_profile,
)

MAX_FILE_BYTES = 512 * 1024
CODE_WINDOW_LINES = 60
RAG_DIR = PurePosixPath("rag/corpus")
DATASET = PurePosixPath("datasets/qlora-corpus.jsonl")
INVENTORY = PurePosixPath("scan/inventory.json")
SKIP_DIRS = frozenset({".git", ".kaidf", ".venv", "venv", "node_modules", "__pycache__", "dist"})
TEXT_SUFFIXES = frozenset(
    {
        ".md",
        ".txt",
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".rb",
        ".sh",
        ".yml",
        ".yaml",
        ".json",
        ".toml",
        ".html",
        ".css",
        ".cfg",
        ".ini",
    }
)
LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".sh": "Shell",
    ".html": "HTML",
    ".css": "CSS",
}
MANIFEST_NAMES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "requirements.txt",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "Gemfile",
        "Makefile",
    }
)
_APP_MAIN = re.compile(r"^apps/([A-Za-z0-9][A-Za-z0-9._-]*)/main\.py$")
_DRAFT_SECTIONS: dict[str, tuple[str, str, str, list[str]]] = {
    # phase directory: (document id, title, document class, sections when no template exists)
    "02_discovery_mapping": (
        "system-map",
        "System map",
        "system-map",
        [
            "Languages",
            "Manifests and build",
            "Continuous integration",
            "Applications detected",
            "Withheld from the model",
        ],
    ),
    "03_design_simulation": (
        "blueprint",
        "Blueprint",
        "blueprint",
        ["Components", "Interfaces", "Runtime shape", "Open questions"],
    ),
}


class ScanError(RuntimeError):
    """The scan cannot run, or the outputs would not be valid. Nothing is written."""


@dataclass
class ScanPlan:
    project: str
    files_seen: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    manifests: list[str] = field(default_factory=list)
    dockerfiles: list[str] = field(default_factory=list)
    ci_workflows: list[str] = field(default_factory=list)
    apps: list[str] = field(default_factory=list)
    blocked: dict[str, list[str]] = field(default_factory=dict)
    withheld: dict[str, str] = field(default_factory=dict)
    chunks: list[Chunk] = field(default_factory=list)
    chunk_digests: dict[str, str] = field(default_factory=dict)
    drafts: dict[str, str] = field(default_factory=dict)
    skipped_drafts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocked)

    def to_dict(self) -> dict[str, Any]:
        """The machine-readable plan: counts and names, never file content."""
        return {
            "project": self.project,
            "blocked": self.is_blocked,
            "files_seen": self.files_seen,
            "languages": dict(sorted(self.languages.items())),
            "manifests": self.manifests,
            "dockerfiles": self.dockerfiles,
            "ci_workflows": self.ci_workflows,
            "apps": self.apps,
            "credentials": {path: kinds for path, kinds in sorted(self.blocked.items())},
            "withheld": dict(sorted(self.withheld.items())),
            "chunks": len(self.chunks),
            "drafts": sorted(self.drafts),
            "skipped_drafts": dict(sorted(self.skipped_drafts.items())),
            "notes": self.notes,
        }


# --- stage 1: extract ---------------------------------------------------------------------------


def _listed_files(root: Path) -> list[str]:
    """Project files as git sees them (tracked and untracked, minus .gitignore). Walks otherwise."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return _walk(root)
    return sorted(name for name in result.stdout.decode("utf-8", "replace").split("\0") if name)


def _walk(root: Path) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for name in filenames:
            found.append((Path(dirpath) / name).relative_to(root).as_posix())
    return sorted(found)


def _read_text(path: Path) -> str | None:
    """The file's text, or None for a binary, oversized or unreadable file."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw[:4096]:
        return None
    return raw.decode("utf-8", errors="replace")


def extract(root: Path, scaffold: Path) -> ScanPlan:
    """Stage 1 and 2 over the project. Reads only; nothing is written."""
    plan = ScanPlan(project=root.name)
    for rel in _listed_files(root):
        parts = PurePosixPath(rel).parts
        if not parts or parts[0] in SKIP_DIRS or ".git" in parts:
            continue
        path = root / rel
        text = _read_text(path)
        if text is None:
            continue
        plan.files_seen += 1
        name = PurePosixPath(rel).name
        suffix = PurePosixPath(rel).suffix.lower()
        if suffix in LANGUAGE_BY_SUFFIX:
            language = LANGUAGE_BY_SUFFIX[suffix]
            plan.languages[language] = plan.languages.get(language, 0) + 1
        if name in MANIFEST_NAMES:
            plan.manifests.append(rel)
        if name.startswith("Dockerfile") or name.startswith("docker-compose"):
            plan.dockerfiles.append(rel)
        if rel.startswith(".github/workflows/") and suffix in {".yml", ".yaml"}:
            plan.ci_workflows.append(rel)
        app = _APP_MAIN.match(rel)
        if app:
            plan.apps.append(app.group(1))

        kinds = find_credentials(text)
        if kinds:
            plan.blocked[rel] = kinds
            continue  # a credential-bearing file contributes nothing else
        if suffix not in TEXT_SUFFIXES and suffix != "":
            continue
        if suffix == ".md":
            reason = refusal(text, rel)
            if reason:
                plan.withheld[rel] = reason
                continue
        for chunk in chunks_for(rel, text):
            plan.chunks.append(chunk)
        plan.chunk_digests[rel] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    plan.apps = sorted(set(plan.apps))
    _ingest_allowlisted_urls(root, scaffold, plan)
    return plan


def _ingest_allowlisted_urls(root: Path, scaffold: Path, plan: ScanPlan) -> None:
    """Fetch the URL sources of model-setup.json whose host is allowlisted, into the chunks.

    Only `url` sources are read here; local `path` sources are already covered by the walk above.
    Hosts outside `allowed_url_hosts` are never requested, and what was withheld is noted.
    """
    try:
        profile = load_profile(scaffold)
    except ModelSetupError as exc:
        plan.notes.append(f"URL sources skipped: {exc}")
        return
    if not profile:
        return
    rag = profile.get("rag", {})
    url_sources = [
        source for source in rag.get("sources", []) if isinstance(source, dict) and "url" in source
    ]
    if not url_sources:
        return
    scoped = {
        "rag": {"sources": url_sources, "allowed_url_hosts": rag.get("allowed_url_hosts", [])}
    }
    chunks, notices = load_rag_chunks(scoped, root)
    plan.notes.extend(notices)
    plan.chunks.extend(chunks)
    for source in sorted({chunk.source for chunk in chunks}):
        texts = "\n".join(chunk.text for chunk in chunks if chunk.source == source)
        plan.chunk_digests[source] = hashlib.sha256(texts.encode("utf-8")).hexdigest()


# --- stage 2: chunk -----------------------------------------------------------------------------


def chunks_for(rel: str, text: str) -> list[Chunk]:
    """Markdown by headings; Python by top-level definitions; other code in fixed windows."""
    if rel.endswith(".md"):
        return chunk_markdown(text, rel)
    if rel.endswith(".py"):
        spans = _python_spans(text)
        if spans is not None:
            return _code_chunks(rel, text, spans)
    return _code_chunks(rel, text, _windows(text))


def _python_spans(text: str) -> list[tuple[int, int, str]] | None:
    """(start, end, name) line spans of top-level definitions, with preamble and gaps merged in."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    lines = text.splitlines()
    starts = [
        (node.lineno, node.name)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if not starts:
        return None
    spans: list[tuple[int, int, str]] = []
    bounds = [1] + [line for line, _ in starts[1:]] + [len(lines) + 1]
    preamble_end = starts[0][0] - 1
    if preamble_end >= 1:
        spans.append((1, preamble_end, "module preamble"))
    for index, (line, name) in enumerate(starts):
        spans.append((line, bounds[index + 1] - 1, f"def {name}"))
    return spans


def _windows(text: str) -> list[tuple[int, int, str]]:
    count = len(text.splitlines())
    return [
        (start, min(start + CODE_WINDOW_LINES - 1, count), "lines")
        for start in range(1, count + 1, CODE_WINDOW_LINES)
    ]


def _code_chunks(rel: str, text: str, spans: list[tuple[int, int, str]]) -> list[Chunk]:
    lines = text.splitlines()
    chunks: list[Chunk] = []
    for index, (start, end, name) in enumerate(spans):
        body = "\n".join(lines[start - 1 : end]).strip("\n")
        if not body.strip():
            continue
        heading = f"{rel} L{start}-{end} {name}".strip()
        chunks.append(Chunk(source=rel, heading=heading, text=body, index=index))
    return chunks


# --- stage 3: bootstrap drafts ------------------------------------------------------------------


def _facts(plan: ScanPlan) -> dict[str, str]:
    languages = ", ".join(
        f"{name} ({count} files)" for name, count in sorted(plan.languages.items())
    )
    return {
        "languages": languages or "none detected",
        "manifests and build": "; ".join(plan.manifests) or "none detected",
        "continuous integration": "; ".join(plan.ci_workflows) or "none detected",
        "applications detected": ", ".join(plan.apps) or "none detected",
        "withheld from the model": (
            f"{len(plan.withheld)} document(s) withheld by visibility or credential rules"
            if plan.withheld
            else "none"
        ),
    }


def _draft_text(
    doc_id: str,
    title: str,
    document_class: str,
    phase_dir: str,
    sections: list[str],
    facts: dict[str, str],
) -> str:
    lines = [
        "---",
        f"id: {doc_id}",
        f"title: {title}",
        f"document_class: {document_class}",
        f"phase: {phase_dir}",
        "visibility: internal",
        "status: draft",
        "---",
        f"# {title}",
        "",
        "Drafted by kob scan from the project's own files. The project team completes it.",
        "",
    ]
    for section in sections:
        lines.append(f"## {section}")
        lines.append(facts.get(section.lower(), "To be completed by the project team."))
        lines.append("")
    return "\n".join(lines)


def build_drafts(plan: ScanPlan, scaffold: Path) -> None:
    """Stage 3: draft the discovery and design documents. Keep only drafts that pass the checks."""
    facts = _facts(plan)
    for phase_dir, (doc_id, title, document_class, default_sections) in _DRAFT_SECTIONS.items():
        templates = phase_templates(scaffold, phase_dir)
        template = next(
            (text for path, text in templates if path.stem.lower() == document_class), None
        )
        sections = template_sections(template) if template else default_sections
        rel = f"docs/{phase_dir}/{doc_id}.md"
        if (scaffold / rel).exists():
            plan.skipped_drafts[rel] = "exists; kept as it is"
            continue
        text = _draft_text(doc_id, title, document_class, phase_dir, sections, facts)
        problems = document_problems(rel, text, scaffold, phase_dir)
        if problems:
            plan.skipped_drafts[rel] = "; ".join(problems)
            continue
        plan.drafts[rel] = text


# --- stage 4: fork into RAG and QLoRA -----------------------------------------------------------


def rag_files(plan: ScanPlan) -> dict[str, str]:
    """One Markdown file per source, holding its admissible chunks, for the RAG layer."""
    by_source: dict[str, list[Chunk]] = {}
    for chunk in plan.chunks:
        by_source.setdefault(chunk.source, []).append(chunk)
    files: dict[str, str] = {}
    for source, chunks in sorted(by_source.items()):
        slug = re.sub(r"[^A-Za-z0-9]+", "-", source).strip("-").lower() or "source"
        rel = f"{RAG_DIR}/{slug}.md"
        sections = []
        for chunk in chunks:
            fenced = chunk.text if source.endswith(".md") else f"```\n{chunk.text}\n```"
            sections.append(f"## {chunk.heading}\n\n{fenced}\n")
        digest = plan.chunk_digests.get(source, "")
        files[rel] = (
            "---\n"
            f"id: rag-{slug}\n"
            f"title: {source}\n"
            "document_class: rag-source\n"
            "phase: rag\n"
            "visibility: internal\n"
            "status: draft\n"
            f"source_sha256: {digest}\n"
            "---\n" + "\n".join(sections)
        )
    return files


def qlora_rows(plan: ScanPlan) -> list[dict[str, str | bool]]:
    """Synthetic instruction rows, one per admissible chunk, each traceable to its source."""
    rows: list[dict[str, str | bool]] = []
    for chunk in plan.chunks:
        rows.append(
            {
                "instruction": f"Explain the section '{chunk.heading}' from {chunk.source}.",
                "input": "",
                "output": chunk.text,
                "source": chunk.source,
                "source_sha256": plan.chunk_digests.get(chunk.source, ""),
                "synthetic": True,
            }
        )
    return rows


def updated_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """The profile with its rag and qlora layers pointing at the scan's outputs."""
    updated = json.loads(json.dumps(profile))
    rag = updated.setdefault("rag", {})
    sources = rag.setdefault("sources", [])
    if {"path": str(RAG_DIR)} not in sources:
        sources.append({"path": str(RAG_DIR)})
    updated.setdefault("qlora", {})["dataset_manifest"] = str(DATASET)
    return updated


def compute(plan: ScanPlan, scaffold: Path) -> None:
    """Fill the plan's stage-3 and stage-4 outputs. Pure with respect to the disk."""
    build_drafts(plan, scaffold)
    plan.notes.append("RAG corpus and QLoRA dataset are built from the admissible chunks.")


# --- writing ------------------------------------------------------------------------------------


def write_outputs(plan: ScanPlan, scaffold: Path) -> list[str]:
    """Write the drafts, the RAG corpus, the dataset and the inventory. Returns the paths written.

    Refuses to run on a blocked plan. The profile is validated before anything is written, so a
    profile that cannot take the new layers stops the whole scan.
    """
    if plan.is_blocked:
        raise ScanError("the scan found credentials; nothing was written")
    profile_path = profile_file(scaffold)
    profile_text: str | None = None
    if profile_path.is_file():
        current = json.loads(profile_path.read_text(encoding="utf-8"))
        candidate = updated_profile(current)
        errors = validate_profile(candidate)
        if errors:
            raise ScanError("model-setup.json would not validate: " + "; ".join(errors))
        profile_text = json.dumps(candidate, indent=2, ensure_ascii=False) + "\n"

    written: list[str] = []
    for rel, text in plan.drafts.items():
        target = scaffold / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(rel)
    for rel, text in rag_files(plan).items():
        target = scaffold / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(rel)
    dataset = scaffold / DATASET
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in qlora_rows(plan)
        ),
        encoding="utf-8",
    )
    written.append(str(DATASET))
    if profile_text is not None:
        profile_path.write_text(profile_text, encoding="utf-8")
        written.append("model-setup.json")
    inventory = scaffold / INVENTORY
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    written.append(str(INVENTORY))
    return written
