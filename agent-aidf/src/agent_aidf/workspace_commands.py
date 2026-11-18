"""Workspace subcommands: the project's documents, contracts, instant apps and chat.

These run in two places: as root `kob` subcommands (cli/main.py) and, through the legacy
`python -m agent_aidf.legacy_cli` entry point. `kob shell` delegates to the root CLI, so there is
one implementation of each command.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
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
from .ports import tcp_port_argument
from .repo import filter_documents, find_documents, get_document, list_packs, load_documents

WORKSPACE_COMMANDS: frozenset[str] = frozenset(
    {
        "packs",
        "docs",
        "find",
        "open",
        "chat",
        "apps",
        "app-create",
        "app-open",
        "app-run",
        "app-runtime",
        "app-stop",
        "contracts",
        "contract-create",
        "contract-open",
    }
)


def add_workspace_subcommands(
    subparsers: argparse._SubParsersAction,
    add: Callable[..., argparse.ArgumentParser] | None = None,
) -> None:
    """Register the workspace subcommands on a CLI's subparsers.

    `add` lets the root CLI attach help text to each parser; the legacy CLI uses plain parsers.
    """
    add = add or subparsers.add_parser
    add("packs", help="List doctrine packs discovered in the repository.")
    add("apps", help="List persistent instant apps in .kaidf/apps.")
    add("contracts", help="List generated basic contracts in .kaidf/contracts.")

    contract_create_parser = add(
        "contract-create",
        help="Create a mentor-aware basic contract scaffold under .kaidf/contracts.",
    )
    contract_create_parser.add_argument("contract_id", nargs="?")
    contract_create_parser.add_argument(
        "--brief", help="Optional project brief to seed the contract."
    )
    contract_create_parser.add_argument(
        "--force", action="store_true", help="Replace an existing contract directory."
    )

    contract_open_parser = add("contract-open", help="Print contract metadata by id or path.")
    contract_open_parser.add_argument("ref")

    app_create_parser = add("app-create", help="Create an instant app scaffold.")
    app_create_parser.add_argument(
        "app_id", help="App id used as the persistent folder name or ephemeral label."
    )
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

    app_open_parser = add("app-open", help="Print instant app metadata by id or path.")
    app_open_parser.add_argument("ref")
    app_run_parser = add("app-run", help="Start a background runtime for a web instant app.")
    app_run_parser.add_argument("ref")
    app_run_parser.add_argument("--port", type=tcp_port_argument)
    app_runtime_parser = add("app-runtime", help="Show stored runtime state for an instant app.")
    app_runtime_parser.add_argument("ref")
    app_stop_parser = add("app-stop", help="Stop a background runtime for an instant app.")
    app_stop_parser.add_argument("ref")

    docs_parser = add("docs", help="List documents filtered by metadata.")
    docs_parser.add_argument("--pack")
    docs_parser.add_argument("--phase")
    docs_parser.add_argument("--ethical-domain")
    docs_parser.add_argument("--maturity-level")
    docs_parser.add_argument("--assessment-type")
    docs_parser.add_argument("--risk-type")

    find_parser = add("find", help="Find documents by simple text match.")
    find_parser.add_argument("query")

    open_parser = add("open", help="Open a document by id or path.")
    open_parser.add_argument("ref")

    chat_parser = add("chat", help="Send a prompt to the configured chat controller.")
    chat_parser.add_argument("prompt")


def dispatch_workspace_command(args: argparse.Namespace, repo_root: Path) -> int:
    """Run a workspace subcommand parsed by add_workspace_subcommands()."""
    command = args.command
    if command == "packs":
        return _cmd_packs(repo_root)
    if command == "docs":
        return _cmd_docs(repo_root, args)
    if command == "find":
        return _cmd_find(repo_root, args.query)
    if command == "open":
        return _cmd_open(repo_root, args.ref)
    if command == "chat":
        return _cmd_chat(repo_root, args.prompt)
    if command == "apps":
        return _cmd_apps(repo_root)
    if command == "app-create":
        return _cmd_app_create(repo_root, args.app_id, args.mode, args.kind)
    if command == "app-open":
        return _cmd_app_open(repo_root, args.ref)
    if command == "app-run":
        return _cmd_app_run(repo_root, args.ref, args.port)
    if command == "app-runtime":
        return _cmd_app_runtime(repo_root, args.ref)
    if command == "app-stop":
        return _cmd_app_stop(repo_root, args.ref)
    if command == "contracts":
        return _cmd_contracts(repo_root)
    if command == "contract-create":
        return _cmd_contract_create(repo_root, args.contract_id, args.brief, args.force)
    if command == "contract-open":
        return _cmd_contract_open(repo_root, args.ref)
    raise ValueError(f"not a workspace command: {command}")


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


def _cmd_contract_create(
    repo_root: Path, contract_id: str | None, brief: str | None, force: bool
) -> int:
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
