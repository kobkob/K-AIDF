from __future__ import annotations

import shlex
from argparse import Namespace
from pathlib import Path

from .controller import build_controller
from .repo import filter_documents, find_documents, get_document, list_packs, load_documents


def _print_docs(repo_root: Path, args: Namespace) -> int:
    documents = load_documents(repo_root)
    filtered = filter_documents(
        documents,
        pack=args.pack,
        phase=args.phase,
        ethical_domain=args.ethical_domain,
        maturity_level=args.maturity_level,
        assessment_type=args.assessment_type,
        risk_type=args.risk_type,
    )
    for doc in filtered:
        extras = []
        if doc.pack:
            extras.append(f"pack={doc.pack}")
        if doc.ethical_domain:
            extras.append(f"ethical_domain={doc.ethical_domain}")
        if doc.maturity_level:
            extras.append(f"maturity_level={doc.maturity_level}")
        if doc.assessment_type:
            extras.append(f"assessment_type={doc.assessment_type}")
        if doc.risk_type:
            extras.append(f"risk_type={doc.risk_type}")
        suffix = f" [{' '.join(extras)}]" if extras else ""
        print(f"{doc.path} :: {doc.title}{suffix}")
    return 0


def _print_packs(repo_root: Path) -> int:
    for pack in list_packs(load_documents(repo_root)):
        print(pack)
    return 0


def _print_find(repo_root: Path, query: str) -> int:
    for doc in find_documents(load_documents(repo_root), query):
        print(f"{doc.path} :: {doc.title}")
    return 0


def _print_open(repo_root: Path, ref: str) -> int:
    doc = get_document(load_documents(repo_root), ref)
    if doc is None:
        print(f"Document not found: {ref}")
        return 1
    print(f"# {doc.title}")
    print(f"path: {doc.path}")
    print(f"id: {doc.id}")
    print(f"phase: {doc.phase}")
    if doc.pack:
        print(f"pack: {doc.pack}")
    if doc.ethical_domain:
        print(f"ethical_domain: {doc.ethical_domain}")
    if doc.maturity_level:
        print(f"maturity_level: {doc.maturity_level}")
    if doc.assessment_type:
        print(f"assessment_type: {doc.assessment_type}")
    if doc.risk_type:
        print(f"risk_type: {doc.risk_type}")
    print()
    print(doc.content)
    return 0


def run_shell(repo_root: Path) -> int:
    controller = build_controller()
    print("agent-aidf shell")
    print("type 'help' for commands, 'quit' to exit")
    while True:
        try:
            raw = input("agent-aidf> ").strip()
        except EOFError:
            print()
            return 0
        if not raw:
            continue
        if raw in {"quit", "exit"}:
            return 0
        if raw == "help":
            print("commands: packs | docs [filters] | find <query> | open <id-or-path> | chat <prompt> | quit")
            continue
        parts = shlex.split(raw)
        command = parts[0]
        if command == "packs":
            _print_packs(repo_root)
            continue
        if command == "find" and len(parts) >= 2:
            _print_find(repo_root, " ".join(parts[1:]))
            continue
        if command == "open" and len(parts) == 2:
            _print_open(repo_root, parts[1])
            continue
        if command == "chat" and len(parts) >= 2:
            print(controller.chat(" ".join(parts[1:]), repo_root))
            continue
        if command == "docs":
            namespace = Namespace(
                pack=None,
                phase=None,
                ethical_domain=None,
                maturity_level=None,
                assessment_type=None,
                risk_type=None,
            )
            index = 1
            while index < len(parts):
                if parts[index] == "--pack" and index + 1 < len(parts):
                    namespace.pack = parts[index + 1]
                    index += 2
                    continue
                if parts[index] == "--phase" and index + 1 < len(parts):
                    namespace.phase = parts[index + 1]
                    index += 2
                    continue
                if parts[index] == "--ethical-domain" and index + 1 < len(parts):
                    namespace.ethical_domain = parts[index + 1]
                    index += 2
                    continue
                if parts[index] == "--maturity-level" and index + 1 < len(parts):
                    namespace.maturity_level = parts[index + 1]
                    index += 2
                    continue
                if parts[index] == "--assessment-type" and index + 1 < len(parts):
                    namespace.assessment_type = parts[index + 1]
                    index += 2
                    continue
                if parts[index] == "--risk-type" and index + 1 < len(parts):
                    namespace.risk_type = parts[index + 1]
                    index += 2
                    continue
                print(f"Unknown docs argument: {parts[index]}")
                break
            else:
                _print_docs(repo_root, namespace)
                continue
        print(f"Unknown command: {raw}")
