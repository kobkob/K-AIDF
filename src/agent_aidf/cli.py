from __future__ import annotations

import argparse
import os
from pathlib import Path

from .controller import build_controller
from .repo import filter_documents, find_documents, get_document, list_packs, load_documents, resolve_repo_root
from .shell import run_shell


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-aidf")
    parser.add_argument(
        "--repo",
        default=os.environ.get("AIDF_REPO_ROOT"),
        help="Path to the generated K-AIDF repository. Defaults to AIDF_REPO_ROOT or cwd.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("packs", help="List doctrine packs discovered in the repository.")

    docs_parser = subparsers.add_parser("docs", help="List documents filtered by metadata.")
    docs_parser.add_argument("--pack")
    docs_parser.add_argument("--phase")
    docs_parser.add_argument("--ethical-domain")
    docs_parser.add_argument("--maturity-level")
    docs_parser.add_argument("--assessment-type")
    docs_parser.add_argument("--risk-type")

    find_parser = subparsers.add_parser("find", help="Find documents by simple text match.")
    find_parser.add_argument("query")

    open_parser = subparsers.add_parser("open", help="Open a document by id or path.")
    open_parser.add_argument("ref")

    chat_parser = subparsers.add_parser("chat", help="Send a prompt to the configured chat controller.")
    chat_parser.add_argument("prompt")

    subparsers.add_parser("shell", help="Start the interactive shell.")
    return parser


def _cmd_packs(repo_root: Path) -> int:
    for pack in list_packs(load_documents(repo_root)):
        print(pack)
    return 0


def _cmd_docs(repo_root: Path, args: argparse.Namespace) -> int:
    documents = filter_documents(
        load_documents(repo_root),
        pack=args.pack,
        phase=args.phase,
        ethical_domain=args.ethical_domain,
        maturity_level=args.maturity_level,
        assessment_type=args.assessment_type,
        risk_type=args.risk_type,
    )
    for doc in documents:
        print(f"{doc.path}\t{doc.title}")
    return 0


def _cmd_find(repo_root: Path, query: str) -> int:
    for doc in find_documents(load_documents(repo_root), query):
        print(f"{doc.path}\t{doc.title}")
    return 0


def _cmd_open(repo_root: Path, ref: str) -> int:
    doc = get_document(load_documents(repo_root), ref)
    if doc is None:
        print(f"Document not found: {ref}")
        return 1
    print(doc.content)
    return 0


def _cmd_chat(repo_root: Path, prompt: str) -> int:
    print(build_controller().chat(prompt, repo_root))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo_root = resolve_repo_root(args.repo)

    if args.command == "packs":
        return _cmd_packs(repo_root)
    if args.command == "docs":
        return _cmd_docs(repo_root, args)
    if args.command == "find":
        return _cmd_find(repo_root, args.query)
    if args.command == "open":
        return _cmd_open(repo_root, args.ref)
    if args.command == "chat":
        return _cmd_chat(repo_root, args.prompt)
    if args.command == "shell":
        return run_shell(repo_root)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
