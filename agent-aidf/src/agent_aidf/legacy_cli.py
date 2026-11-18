from __future__ import annotations

import argparse
import os
from pathlib import Path

from .controller import build_controller, select_context_documents
from .mentor import continue_mentor_workflow, mentor_status_text, reset_mentor_state
from .project import (
    MentorNotInitializedError,
    init_project_repo,
    project_repo_root,
    read_project_status,
    resolve_mentor_repo_root,
    resolve_project_root,
    resolve_runtime_repo_root,
)
from .repo import load_documents
from .shell import run_shell
from .workspace_commands import (
    WORKSPACE_COMMANDS,
    add_workspace_subcommands,
    dispatch_workspace_command,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m agent_aidf.legacy_cli")
    parser.add_argument(
        "--project",
        default=os.environ.get("AIDF_PROJECT_ROOT"),
        help="Path to the creator project. Defaults to the current directory.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Path to a K-AIDF repository override. Defaults to .kaidf in the project, then "
        "AIDF_REPO_ROOT.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create .kaidf in the current project.")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing .kaidf directory. The old one is kept as .kaidf.bak-<timestamp>, "
        "and mentor state, instant apps, contracts and policy are carried over.",
    )

    subparsers.add_parser("status", help="Show current project and .kaidf runtime status.")

    context_parser = subparsers.add_parser(
        "context",
        help="Inspect the current project runtime context, optionally for a prompt.",
    )
    context_parser.add_argument(
        "prompt", nargs="?", help="Optional prompt to score relevant documents."
    )

    mentor_parser = subparsers.add_parser(
        "mentor",
        help="Continue the persisted mentor workflow against the project runtime.",
    )
    mentor_parser.add_argument(
        "answer", nargs="?", help="Optional answer for the current mentor question."
    )
    mentor_parser.add_argument(
        "--status", action="store_true", help="Show persisted mentor workflow state."
    )
    mentor_parser.add_argument(
        "--reset", action="store_true", help="Reset the persisted mentor workflow state."
    )

    add_workspace_subcommands(subparsers)
    subparsers.add_parser("shell", help="Start the interactive shell.")
    return parser


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
        try:
            mentor_repo_root = resolve_mentor_repo_root(project_root)
        except MentorNotInitializedError as exc:
            print(str(exc))
            return 1
        return _cmd_mentor(mentor_repo_root, args)
    if args.command in WORKSPACE_COMMANDS:
        return dispatch_workspace_command(args, repo_root)
    if args.command == "shell":
        return run_shell(repo_root, project_root)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
