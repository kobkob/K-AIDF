from __future__ import annotations

import argparse
import os
from pathlib import Path

from .contracts import create_basic_contract, get_contract, list_contracts
from .controller import build_controller, select_context_documents
from .instant_apps import (
    create_instant_app,
    get_instant_app,
    list_instant_apps,
    load_instant_app_runtime,
    run_instant_app,
    stop_instant_app,
)
from .mentor import continue_mentor_workflow, mentor_status_text, reset_mentor_state
from .project import (
    init_project_repo,
    project_repo_root,
    read_project_status,
    resolve_project_root,
    resolve_runtime_repo_root,
)
from .repo import filter_documents, find_documents, get_document, list_packs, load_documents
from .shell import run_shell


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-aidf")
    parser.add_argument(
        "--project",
        default=os.environ.get("AIDF_PROJECT_ROOT"),
        help="Path to the creator project. Defaults to the current directory.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Path to a K-AIDF repository override. Defaults to .kaidf in the project, then AIDF_REPO_ROOT.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create .kaidf in the current project.")
    init_parser.add_argument("--force", action="store_true", help="Replace an existing .kaidf directory.")

    subparsers.add_parser("status", help="Show current project and .kaidf runtime status.")

    context_parser = subparsers.add_parser(
        "context",
        help="Inspect the current project runtime context, optionally for a prompt.",
    )
    context_parser.add_argument("prompt", nargs="?", help="Optional prompt to score relevant documents.")

    mentor_parser = subparsers.add_parser(
        "mentor",
        help="Continue the persisted mentor workflow against the project runtime.",
    )
    mentor_parser.add_argument("answer", nargs="?", help="Optional answer for the current mentor question.")
    mentor_parser.add_argument("--status", action="store_true", help="Show persisted mentor workflow state.")
    mentor_parser.add_argument("--reset", action="store_true", help="Reset the persisted mentor workflow state.")
    subparsers.add_parser("packs", help="List doctrine packs discovered in the repository.")
    subparsers.add_parser("apps", help="List persistent instant apps in .kaidf/apps.")
    subparsers.add_parser("contracts", help="List generated basic contracts in .kaidf/contracts.")

    contract_create_parser = subparsers.add_parser(
        "contract-create",
        help="Create a mentor-aware basic contract scaffold under .kaidf/contracts.",
    )
    contract_create_parser.add_argument("contract_id", nargs="?")
    contract_create_parser.add_argument("--brief", help="Optional project brief to seed the contract.")
    contract_create_parser.add_argument("--force", action="store_true", help="Replace an existing contract directory.")

    contract_open_parser = subparsers.add_parser("contract-open", help="Print contract metadata by id or path.")
    contract_open_parser.add_argument("ref")

    app_create_parser = subparsers.add_parser("app-create", help="Create an instant app scaffold.")
    app_create_parser.add_argument("app_id", help="App id used as the persistent folder name or ephemeral label.")
    app_create_parser.add_argument(
        "--mode",
        choices=["persistent", "ephemeral"],
        default="persistent",
        help="Whether the app should live in .kaidf/apps or be created as a temporary scaffold.",
    )
    app_create_parser.add_argument(
        "--kind",
        choices=["shell", "web"],
        default="shell",
        help="Initial app scaffold kind.",
    )

    app_open_parser = subparsers.add_parser("app-open", help="Print instant app metadata by id or path.")
    app_open_parser.add_argument("ref")
    app_run_parser = subparsers.add_parser("app-run", help="Start a background runtime for a web instant app.")
    app_run_parser.add_argument("ref")
    app_run_parser.add_argument("--port", type=int)
    app_runtime_parser = subparsers.add_parser("app-runtime", help="Show stored runtime state for an instant app.")
    app_runtime_parser.add_argument("ref")
    app_stop_parser = subparsers.add_parser("app-stop", help="Stop a background runtime for an instant app.")
    app_stop_parser.add_argument("ref")

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


def _cmd_mentor(repo_root: Path, args: argparse.Namespace) -> int:
    if args.reset:
        path = reset_mentor_state(repo_root)
        print(f"Reset mentor workflow state at {path}")
        return 0
    if args.status:
        print(mentor_status_text(repo_root))
        return 0
    turn = continue_mentor_workflow(repo_root, answer=args.answer)
    print(turn.message)
    return 0


def _cmd_apps(repo_root: Path) -> int:
    apps = list_instant_apps(repo_root)
    if not apps:
        print("No persistent instant apps found.")
        return 0
    for app in apps:
        suffix = f"\t{app.url}" if app.url else ""
        print(f"{app.app_id}\t{app.kind}\t{app.mode}\t{app.root}{suffix}")
    return 0


def _cmd_contracts(repo_root: Path) -> int:
    contracts = list_contracts(repo_root)
    if not contracts:
        print("No generated contracts found.")
        return 0
    for contract in contracts:
        print(f"{contract.contract_id}\t{contract.title}\t{contract.root}")
    return 0


def _cmd_contract_create(repo_root: Path, contract_id: str | None, brief: str | None, force: bool) -> int:
    contract = create_basic_contract(repo_root, contract_id=contract_id, brief=brief, force=force)
    print(f"contract_id: {contract.contract_id}")
    print(f"title: {contract.title}")
    print(f"root: {contract.root}")
    print(f"brief: {contract.brief}")
    print(f"current_app_id: {contract.current_app_id or 'none'}")
    print(f"current_app_url: {contract.current_app_url or 'none'}")
    print(f"phase_count: {len(contract.phases)}")
    return 0


def _cmd_contract_open(repo_root: Path, ref: str) -> int:
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


def _cmd_app_create(repo_root: Path, app_id: str, mode: str, kind: str) -> int:
    app = create_instant_app(repo_root, app_id=app_id, mode=mode, kind=kind)
    print(f"app_id: {app.app_id}")
    print(f"mode: {app.mode}")
    print(f"kind: {app.kind}")
    print(f"root: {app.root}")
    print(f"entrypoint: {app.entrypoint}")
    if app.url:
        print(f"url: {app.url}")
    return 0


def _cmd_app_open(repo_root: Path, ref: str) -> int:
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


def _cmd_app_run(repo_root: Path, ref: str, port: int | None) -> int:
    runtime = run_instant_app(repo_root, ref, port=port)
    print(f"app_id: {runtime.app_id}")
    print(f"status: {runtime.status}")
    print(f"pid: {runtime.pid}")
    print(f"port: {runtime.port or 'none'}")
    print(f"log_path: {runtime.log_path}")
    return 0


def _cmd_app_runtime(repo_root: Path, ref: str) -> int:
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


def _cmd_app_stop(repo_root: Path, ref: str) -> int:
    runtime = stop_instant_app(repo_root, ref)
    print(f"app_id: {runtime.app_id}")
    print(f"status: {runtime.status}")
    print(f"pid: {runtime.pid or 'none'}")
    print(f"port: {runtime.port or 'none'}")
    print(f"log_path: {runtime.log_path}")
    return 0


def _cmd_init(project_root: Path, force: bool) -> int:
    repo_root = init_project_repo(project_root, force=force)
    print(f"Initialized {project_repo_root(project_root).name} at {repo_root}")
    return 0


def _cmd_status(project_root: Path, repo_root: Path) -> int:
    status = read_project_status(project_root, repo_root)
    print(f"project_root: {status.project_root}")
    print(f"repo_root: {status.repo_root}")
    print(f"has_kaidf: {'yes' if status.has_kaidf else 'no'}")
    print(f"document_count: {status.document_count}")
    print(f"pack_count: {status.pack_count}")
    print(f"packs: {', '.join(status.packs) if status.packs else 'none'}")
    print(f"instant_app_count: {status.instant_app_count}")
    print(f"instant_apps: {', '.join(status.instant_apps) if status.instant_apps else 'none'}")
    print(f"mentor_step_count: {status.mentor_step_count}")
    print(f"mentor_pending_category: {status.mentor_pending_category or 'none'}")
    print(f"mentor_current_app_id: {status.mentor_current_app_id or 'none'}")
    print(f"mentor_current_app_url: {status.mentor_current_app_url or 'none'}")
    return 0


def _cmd_context(project_root: Path, repo_root: Path, prompt: str | None) -> int:
    status = read_project_status(project_root, repo_root)
    documents = load_documents(repo_root)
    print(f"project_root: {status.project_root}")
    print(f"repo_root: {status.repo_root}")
    print(f"controller: {build_controller().__class__.__name__}")
    print(f"packs: {', '.join(status.packs) if status.packs else 'none'}")
    print(f"document_count: {status.document_count}")
    print(f"instant_apps: {', '.join(status.instant_apps) if status.instant_apps else 'none'}")
    print(f"mentor_step_count: {status.mentor_step_count}")
    print(f"mentor_pending_category: {status.mentor_pending_category or 'none'}")
    print(f"mentor_current_app_id: {status.mentor_current_app_id or 'none'}")
    print(f"mentor_current_app_url: {status.mentor_current_app_url or 'none'}")
    if not prompt:
        return 0
    print(f"prompt: {prompt}")
    print("selected_documents:")
    matches = select_context_documents(documents, prompt, limit=5)
    if not matches:
        print("- none")
        return 0
    for doc in matches:
        metadata = []
        if doc.pack:
            metadata.append(f"pack={doc.pack}")
        if doc.ethical_domain:
            metadata.append(f"ethical_domain={doc.ethical_domain}")
        if doc.maturity_level:
            metadata.append(f"maturity_level={doc.maturity_level}")
        if doc.assessment_type:
            metadata.append(f"assessment_type={doc.assessment_type}")
        if doc.risk_type:
            metadata.append(f"risk_type={doc.risk_type}")
        suffix = f" [{' '.join(metadata)}]" if metadata else ""
        print(f"- {doc.path} :: {doc.title}{suffix}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    project_root = resolve_project_root(args.project)

    if args.command == "init":
        return _cmd_init(project_root, args.force)

    repo_root = resolve_runtime_repo_root(project_root, args.repo)

    if args.command == "status":
        return _cmd_status(project_root, repo_root)
    if args.command == "context":
        return _cmd_context(project_root, repo_root, args.prompt)
    if args.command == "mentor":
        return _cmd_mentor(repo_root, args)
    if args.command == "packs":
        return _cmd_packs(repo_root)
    if args.command == "contracts":
        return _cmd_contracts(repo_root)
    if args.command == "contract-create":
        return _cmd_contract_create(repo_root, args.contract_id, args.brief, args.force)
    if args.command == "contract-open":
        return _cmd_contract_open(repo_root, args.ref)
    if args.command == "apps":
        return _cmd_apps(repo_root)
    if args.command == "app-create":
        return _cmd_app_create(repo_root, args.app_id, args.mode, args.kind)
    if args.command == "app-open":
        return _cmd_app_open(repo_root, args.ref)
    if args.command == "app-run":
        return _cmd_app_run(repo_root, args.ref, args.port)
    if args.command == "app-runtime":
        return _cmd_app_runtime(repo_root, args.ref)
    if args.command == "app-stop":
        return _cmd_app_stop(repo_root, args.ref)
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
