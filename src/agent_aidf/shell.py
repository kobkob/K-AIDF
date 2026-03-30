from __future__ import annotations

import shlex
from argparse import Namespace
from pathlib import Path

from .contracts import create_basic_contract, get_contract, list_contracts
from .controller import build_controller
from .instant_apps import (
    create_instant_app,
    get_instant_app,
    list_instant_apps,
    load_instant_app_runtime,
    run_instant_app,
    stop_instant_app,
)
from .mentor import continue_mentor_workflow, mentor_status_text, reset_mentor_state
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


def _print_apps(repo_root: Path) -> int:
    apps = list_instant_apps(repo_root)
    if not apps:
        print("No persistent instant apps found.")
        return 0
    for app in apps:
        suffix = f" url={app.url}" if app.url else ""
        print(f"{app.app_id} :: kind={app.kind} mode={app.mode} root={app.root}{suffix}")
    return 0


def _print_contracts(repo_root: Path) -> int:
    contracts = list_contracts(repo_root)
    if not contracts:
        print("No generated contracts found.")
        return 0
    for contract in contracts:
        print(f"{contract.contract_id} :: title={contract.title} root={contract.root}")
    return 0


def _print_contract_open(repo_root: Path, ref: str) -> int:
    contract = get_contract(repo_root, ref)
    if contract is None:
        print(f"Contract not found: {ref}")
        return 1
    print(f"contract_id: {contract.contract_id}")
    print(f"title: {contract.title}")
    print(f"root: {contract.root}")
    print(f"brief: {contract.brief}")
    print(f"source_summary: {contract.source_summary}")
    print(f"current_app_id: {contract.current_app_id or 'none'}")
    print(f"current_app_url: {contract.current_app_url or 'none'}")
    print(f"phase_count: {len(contract.phases)}")
    if contract.ai_guidance:
        print(f"ai_guidance: {contract.ai_guidance}")
    return 0


def _print_app_open(repo_root: Path, ref: str) -> int:
    app = get_instant_app(repo_root, ref)
    if app is None:
        print(f"Instant app not found: {ref}")
        return 1
    print(f"app_id: {app.app_id}")
    print(f"title: {app.title}")
    print(f"mode: {app.mode}")
    print(f"kind: {app.kind}")
    print(f"root: {app.root}")
    print(f"entrypoint: {app.entrypoint}")
    print(f"description: {app.description}")
    if app.url:
        print(f"url: {app.url}")
    runtime = load_instant_app_runtime(repo_root, app.app_id)
    if runtime is not None:
        print(f"runtime_status: {runtime.status}")
        print(f"runtime_pid: {runtime.pid or 'none'}")
        print(f"runtime_port: {runtime.port or 'none'}")
    return 0


def _print_app_runtime(repo_root: Path, ref: str) -> int:
    runtime = load_instant_app_runtime(repo_root, ref)
    if runtime is None:
        print(f"No runtime state found for: {ref}")
        return 1
    print(f"app_id: {runtime.app_id}")
    print(f"status: {runtime.status}")
    print(f"pid: {runtime.pid or 'none'}")
    print(f"port: {runtime.port or 'none'}")
    print(f"log_path: {runtime.log_path}")
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
            print(
                "commands: packs | contracts | contract-create [id] [--brief ...] [--force] | contract-open <id-or-path> | "
                "apps | app-create <id> [--mode ...] [--kind ...] | "
                "app-open <id-or-path> | app-run <id> [--port ...] | app-runtime <id> | app-stop <id> | "
                "mentor [answer] | mentor-status | mentor-reset | "
                "docs [filters] | find <query> | open <id-or-path> | chat <prompt> | quit"
            )
            continue
        parts = shlex.split(raw)
        command = parts[0]
        if command == "packs":
            _print_packs(repo_root)
            continue
        if command == "contracts":
            _print_contracts(repo_root)
            continue
        if command == "apps":
            _print_apps(repo_root)
            continue
        if command == "find" and len(parts) >= 2:
            _print_find(repo_root, " ".join(parts[1:]))
            continue
        if command == "open" and len(parts) == 2:
            _print_open(repo_root, parts[1])
            continue
        if command == "contract-open" and len(parts) == 2:
            _print_contract_open(repo_root, parts[1])
            continue
        if command == "app-open" and len(parts) == 2:
            _print_app_open(repo_root, parts[1])
            continue
        if command == "app-runtime" and len(parts) == 2:
            _print_app_runtime(repo_root, parts[1])
            continue
        if command == "app-stop" and len(parts) == 2:
            runtime = stop_instant_app(repo_root, parts[1])
            print(f"Stopped {runtime.app_id} with status {runtime.status}")
            continue
        if command == "chat" and len(parts) >= 2:
            print(controller.chat(" ".join(parts[1:]), repo_root))
            continue
        if command == "mentor":
            answer = " ".join(parts[1:]) if len(parts) >= 2 else None
            print(continue_mentor_workflow(repo_root, answer=answer).message)
            continue
        if command == "mentor-status":
            print(mentor_status_text(repo_root))
            continue
        if command == "mentor-reset":
            path = reset_mentor_state(repo_root)
            print(f"Reset mentor workflow state at {path}")
            continue
        if command == "app-run" and len(parts) >= 2:
            ref = parts[1]
            port = None
            index = 2
            while index < len(parts):
                if parts[index] == "--port" and index + 1 < len(parts):
                    port = int(parts[index + 1])
                    index += 2
                    continue
                print(f"Unknown app-run argument: {parts[index]}")
                break
            else:
                runtime = run_instant_app(repo_root, ref, port=port)
                print(f"Started {runtime.app_id} on port {runtime.port}")
                continue
        if command == "app-create" and len(parts) >= 2:
            app_id = parts[1]
            mode = "persistent"
            kind = "shell"
            index = 2
            while index < len(parts):
                if parts[index] == "--mode" and index + 1 < len(parts):
                    mode = parts[index + 1]
                    index += 2
                    continue
                if parts[index] == "--kind" and index + 1 < len(parts):
                    kind = parts[index + 1]
                    index += 2
                    continue
                print(f"Unknown app-create argument: {parts[index]}")
                break
            else:
                app = create_instant_app(repo_root, app_id=app_id, mode=mode, kind=kind)
                print(f"Created {app.mode} {app.kind} instant app at {app.root}")
                continue
        if command == "contract-create":
            contract_id = None
            brief = None
            force = False
            index = 1
            if index < len(parts) and not parts[index].startswith("--"):
                contract_id = parts[index]
                index += 1
            while index < len(parts):
                if parts[index] == "--brief" and index + 1 < len(parts):
                    brief = parts[index + 1]
                    index += 2
                    continue
                if parts[index] == "--force":
                    force = True
                    index += 1
                    continue
                print(f"Unknown contract-create argument: {parts[index]}")
                break
            else:
                contract = create_basic_contract(repo_root, contract_id=contract_id, brief=brief, force=force)
                print(f"Created contract {contract.contract_id} at {contract.root}")
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
