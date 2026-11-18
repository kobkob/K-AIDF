# Extension: Model setup
# Description: Create, check and export the model profile (.kaidf/model-setup.json)
# Version: 1.0.0
# Author: Kobkob LLC
# Entrypoints: cli
# Topics: model, profile, rag, qlora, ollama
"""Core extension: `kob model-setup init | check | modelfile`.

It manages .kaidf/model-setup.json, the declarative profile of the model: who it is (profile), the
project documents it may quote (RAG), and an optional QLoRA adapter (weights). The rules live in
agent_aidf.model_setup; this file only wires them to the command line.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_aidf.controller import resolve_local_model
from agent_aidf.model_setup import (
    PROFILE_FILE,
    ModelSetupError,
    dataset_problems,
    load_profile,
    modelfile_text,
    resolve_plan,
)
from agent_aidf.project import resolve_project_root, resolve_runtime_repo_root

MODELFILE_NAME = "Modelfile"


def default_profile() -> dict:
    return {
        "name": "kob-default",
        "identity": "A K-AIDF mentor and auditor for this project. Answer from its documents.",
        "mood": "pragmatic-auditor",
        "parameters": {
            "temperature": 0.4,
            "top_p": 0.9,
            "max_tokens": 1024,
            "context_window": 8192,
        },
        "custom_instructions": "",
        "rag": {
            "enabled": True,
            "sources": [{"path": "docs"}],
            "allowed_url_hosts": [],
            "top_k": 4,
            "max_context_chars": 4000,
        },
        "qlora": {
            "enabled": False,
            "base_model": resolve_local_model(),
            "adapter_path": "models/adapters/kob-qlora",
            "quantization": "nf4",
            "lora_config": {
                "r": 16,
                "alpha": 32,
                "dropout": 0.05,
                "target_modules": ["q_proj", "v_proj"],
            },
            "dataset_manifest": "data/qlora/dataset.jsonl",
            "fallback_to_base": True,
        },
    }


def _configure(parser) -> None:
    actions = parser.add_subparsers(dest="model_setup_action", required=True)
    init = actions.add_parser("init", help="Write a default profile to .kaidf/model-setup.json.")
    init.add_argument("--force", action="store_true", help="Overwrite an existing profile.")
    actions.add_parser("check", help="Validate the profile and show which layers are in use.")
    modelfile = actions.add_parser("modelfile", help="Export an Ollama Modelfile for the profile.")
    modelfile.add_argument("--out", help="Where to write it (default: .kaidf/Modelfile).")


def _repo_root(args) -> Path:
    project_root = resolve_project_root(getattr(args, "project", None))
    return resolve_runtime_repo_root(project_root, getattr(args, "repo", None))


def _run_init(repo_root: Path, *, force: bool) -> int:
    target = repo_root / PROFILE_FILE
    if target.exists() and not force:
        print(f"error: {target} already exists (use --force to overwrite)")
        return 1
    if not repo_root.is_dir():
        print(f"error: {repo_root} does not exist; run `kob init` first")
        return 1
    target.write_text(
        json.dumps(default_profile(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {target}")
    return 0


def _run_check(repo_root: Path) -> int:
    try:
        profile = load_profile(repo_root)
    except ModelSetupError as exc:
        print(f"error: {exc}")
        return 1
    if profile is None:
        print(f"No profile: {repo_root / PROFILE_FILE} does not exist. Run `kob model-setup init`.")
        return 1
    plan = resolve_plan(profile, repo_root)
    print(f"profile:   {profile['name']} ({plan.mood})")
    print(f"strategy:  {plan.strategy}")
    print(f"rag:       {'on' if plan.rag_enabled else 'off'}")
    if plan.qlora_enabled:
        print(f"qlora:     {'ready' if plan.qlora_ready else 'not ready'}")
    if plan.fallback_active:
        print(f"fallback:  base model ({plan.fallback_reason})")
    problems = dataset_problems(profile, repo_root)
    for problem in problems:
        print(f"dataset:   {problem}")
    if plan.blocked_reason:
        print(f"blocked:   {plan.blocked_reason} (fallback_to_base is false)")
        return 1
    return 1 if problems else 0


def _run_modelfile(repo_root: Path, out: str | None) -> int:
    try:
        profile = load_profile(repo_root)
    except ModelSetupError as exc:
        print(f"error: {exc}")
        return 1
    if profile is None:
        print(f"error: no profile at {repo_root / PROFILE_FILE}")
        return 1
    base = profile.get("qlora", {}).get("base_model") or resolve_local_model()
    target = Path(out).expanduser() if out else repo_root / MODELFILE_NAME
    target.write_text(modelfile_text(profile, repo_root, base_model=base), encoding="utf-8")
    print(f"Wrote {target}")
    return 0


def _handle(args) -> int:
    repo_root = _repo_root(args)
    action = args.model_setup_action
    if action == "init":
        return _run_init(repo_root, force=args.force)
    if action == "check":
        return _run_check(repo_root)
    return _run_modelfile(repo_root, args.out)


def register(hooks) -> None:
    hooks.add_subcommand(
        "model-setup",
        help="Create, check and export the model profile (.kaidf/model-setup.json).",
        configure=_configure,
        handler=_handle,
    )
