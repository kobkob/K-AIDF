from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import KaidfGenError
from .loader import load_yaml
from .schema import validate_spec
from .generator import generate, GenerateOptions


def cmd_validate(args: argparse.Namespace) -> int:
    spec = load_yaml(args.spec)
    validate_spec(spec)
    print("✅ Spec is valid.")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    spec = load_yaml(args.spec)
    out = Path(args.out).expanduser()
    target = generate(spec, out, GenerateOptions(force=args.force))
    print(f"✅ Generated: {target}")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kaidf-gen", description="Generate a K-AIDF repo from a YAML spec.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pval = sub.add_parser("validate", help="Validate a spec file.")
    pval.add_argument("spec", help="Path to YAML spec.")
    pval.set_defaults(func=cmd_validate)

    pgen = sub.add_parser("generate", help="Generate a repo from a spec.")
    pgen.add_argument("spec", help="Path to YAML spec.")
    pgen.add_argument("--out", required=True, help="Output directory to generate into.")
    pgen.add_argument("--force", action="store_true", help="Allow writing into a non-empty directory.")
    pgen.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    try:
        code = args.func(args)
        raise SystemExit(code)
    except KaidfGenError as e:
        print(f"❌ {e}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
