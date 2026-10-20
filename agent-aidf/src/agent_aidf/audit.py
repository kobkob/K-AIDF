"""Static KAIDF-AMM scorecard: inspects a local K-AIDF repository and scores it out of 100.

Five dimensions of 20 points each. Each check returns a fraction between 0 and 1, and its
points are that fraction of the check's maximum, rounded to the nearest whole point.
Nothing is executed: the audit only reads files, and it never sends data anywhere.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .repo import _parse_front_matter, resolve_repo_root

REQUIRED_FRONT_MATTER = ("id", "title", "document_class", "phase", "visibility", "status")
MAX_SCAN_BYTES = 1_000_000
SKIPPED_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__"}
TIERS = (("Platinum", 90), ("Gold", 75), ("Silver", 60))
UNRATED = "Non-Compliant / Unrated"

# Common credential shapes. A match is a finding, not proof: the report says what matched.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OpenAI-style secret key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "hard-coded credential assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*[\"'][A-Za-z0-9_\-/+]{16,}[\"']"
        ),
    ),
)


@dataclass(frozen=True)
class CheckResult:
    id: str
    title: str
    max_points: int
    points: int
    detail: str


@dataclass(frozen=True)
class DimensionResult:
    id: str
    name: str
    max_points: int
    checks: tuple[CheckResult, ...]

    @property
    def points(self) -> int:
        return sum(check.points for check in self.checks)


@dataclass(frozen=True)
class AuditResult:
    repo_path: str
    dimensions: tuple[DimensionResult, ...]

    @property
    def score(self) -> int:
        return sum(dimension.points for dimension in self.dimensions)

    @property
    def max_score(self) -> int:
        return sum(dimension.max_points for dimension in self.dimensions)

    @property
    def tier(self) -> str:
        return classify_tier(self.score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_path": self.repo_path,
            "score": self.score,
            "max_score": self.max_score,
            "tier": self.tier,
            "dimensions": [
                {
                    "id": dimension.id,
                    "name": dimension.name,
                    "points": dimension.points,
                    "max_points": dimension.max_points,
                    "checks": [
                        {
                            "id": check.id,
                            "title": check.title,
                            "points": check.points,
                            "max_points": check.max_points,
                            "detail": check.detail,
                        }
                        for check in dimension.checks
                    ],
                }
                for dimension in self.dimensions
            ],
        }


def render_audit_report(result: AuditResult) -> str:
    """Plain-text scorecard for the terminal and the REPL. No colors, so output stays greppable."""
    buffer = io.StringIO()
    console = Console(file=buffer, width=100, color_system=None, highlight=False)
    console.print(
        Panel(
            Text(f"Score: {result.score}/{result.max_score}    Tier: {result.tier}"),
            title="K-AIDF Audit Matrix (KAIDF-AMM v1.0)",
        )
    )
    breakdown = Table("Dimension", "Points")
    for dimension in result.dimensions:
        breakdown.add_row(Text(dimension.name), f"{dimension.points}/{dimension.max_points}")
    console.print(breakdown)
    failed = [
        (dimension, check)
        for dimension in result.dimensions
        for check in dimension.checks
        if check.points < check.max_points
    ]
    if not failed:
        console.print("No failed checks.")
    else:
        findings = Table("Dimension", "Check", "Lost", "Finding")
        for dimension, check in failed:
            findings.add_row(
                Text(dimension.name),
                Text(check.title),
                f"-{check.max_points - check.points}",
                Text(check.detail),
            )
        console.print(findings)
    return buffer.getvalue()


def classify_tier(score: int) -> str:
    for name, minimum in TIERS:
        if score >= minimum:
            return name
    return UNRATED


# ---------------------------------------------------------------- file helpers


def _walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in SKIPPED_DIR_NAMES or part.startswith("out") for part in relative.parts[:-1]):
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def _tracked_files(root: Path) -> list[Path]:
    """Files git tracks, or every file on disk when the folder is not a git repository."""
    if not (root / ".git").exists():
        return _walk_files(root)
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", errors="replace")
    return [root / name for name in listed.split("\0") if name]


def _read_text(path: Path) -> str | None:
    """Text content, or None for missing, oversized or binary files."""
    if not path.is_file() or path.stat().st_size > MAX_SCAN_BYTES:
        return None
    data = path.read_bytes()
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def _load_yaml_mapping(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) and data else None


def _load_json_mapping(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _non_empty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


# ---------------------------------------------------------------- checks
# Each check takes the repository root and returns (fraction, detail).

CheckFn = Callable[[Path], tuple[float, str]]


def _check_no_credentials(root: Path) -> tuple[float, str]:
    files = _tracked_files(root)
    if not files:
        # Nothing was inspected, so there is no evidence of absence.
        return 0.0, "no files to inspect"
    findings: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        name = path.name
        if name == ".env" or (
            name.startswith(".env.") and name not in {".env.example", ".env.sample"}
        ):
            findings.append(f"{relative}: environment file is tracked")
            continue
        text = _read_text(path)
        if text is None:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"{relative}: {label}")
    if findings:
        return 0.0, "; ".join(findings[:5]) + (" ..." if len(findings) > 5 else "")
    return 1.0, "no credentials or environment files tracked"


def _check_pii_rules(root: Path) -> tuple[float, str]:
    path = ".kaidf/policy/pii-masking-rules.yaml"
    if _load_yaml_mapping(root / path) is not None:
        return 1.0, f"{path} present and parseable"
    return 0.0, f"{path} missing, empty or not a YAML mapping"


def _check_kaidf_scaffold(root: Path) -> tuple[float, str]:
    kaidf = root / ".kaidf"
    if kaidf.is_dir() and (kaidf / "README.md").is_file() and (kaidf / "docs").is_dir():
        return 1.0, ".kaidf/ has README.md and docs/"
    return 0.0, ".kaidf/ is missing README.md or docs/"


def _check_mentor_state(root: Path) -> tuple[float, str]:
    path = ".kaidf/mentor-workflow.json"
    if _load_json_mapping(root / path) is not None:
        return 1.0, f"{path} is a valid JSON object"
    return 0.0, f"{path} missing or not a valid JSON object"


def _check_specs(root: Path) -> tuple[float, str]:
    specs = sorted((root / "specs").glob("*.yaml")) + sorted((root / "specs").glob("*.yml"))
    if not specs:
        return 0.0, "no YAML specs found under specs/"
    valid = sum(1 for spec in specs if _load_yaml_mapping(spec) is not None)
    return valid / len(specs), f"{valid} of {len(specs)} YAML specs parse as mappings"


def _check_front_matter(root: Path) -> tuple[float, str]:
    documents = [path for path in _walk_files(root) if path.suffix == ".md"]
    if not documents:
        return 0.0, "no Markdown documents found"
    complete = 0
    for path in documents:
        text = _read_text(path)
        if text is None:
            continue
        front_matter, _ = _parse_front_matter(text)
        if all(front_matter.get(field) for field in REQUIRED_FRONT_MATTER):
            complete += 1
    return complete / len(documents), f"{complete} of {len(documents)} Markdown documents complete"


def _artifact_check(relative: str) -> CheckFn:
    def check(root: Path) -> tuple[float, str]:
        if _non_empty_file(root / relative):
            return 1.0, f"{relative} present"
        return 0.0, f"{relative} missing or empty"

    return check


def _check_ci_workflows(root: Path) -> tuple[float, str]:
    workflows = _workflow_files(root)
    if workflows:
        return 1.0, f"{len(workflows)} workflow file(s) in .github/workflows/"
    return 0.0, "no workflow files in .github/workflows/"


def _check_blocking_gates(root: Path) -> tuple[float, str]:
    workflows = _workflow_files(root)
    if not workflows:
        return 0.0, "no workflows, so no gate can block a merge"
    for path in workflows:
        text = _read_text(path) or ""
        if re.search(r"continue-on-error:\s*true", text):
            return 0.0, f"{path.relative_to(root).as_posix()} sets continue-on-error: true"
    return 1.0, "no workflow step is allowed to fail silently"


def _budget_policy(root: Path) -> dict[str, Any] | None:
    return _load_yaml_mapping(root / ".kaidf/policy/budget.yaml")


def _check_budget_caps(root: Path) -> tuple[float, str]:
    policy = _budget_policy(root) or {}
    max_tokens = policy.get("max_tokens")
    timeout = policy.get("request_timeout_seconds")
    valid = (
        isinstance(max_tokens, int)
        and not isinstance(max_tokens, bool)
        and max_tokens > 0
        and isinstance(timeout, (int, float))
        and not isinstance(timeout, bool)
        and timeout > 0
    )
    if valid:
        return 1.0, "token cap and request timeout configured"
    return 0.0, ".kaidf/policy/budget.yaml lacks a positive max_tokens and request_timeout_seconds"


def _check_local_fallback(root: Path) -> tuple[float, str]:
    if (_budget_policy(root) or {}).get("local_fallback") is True:
        return 1.0, "local fallback enabled in .kaidf/policy/budget.yaml"
    return 0.0, "no local_fallback: true in .kaidf/policy/budget.yaml"


def _workflow_files(root: Path) -> list[Path]:
    directory = root / ".github/workflows"
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))


# ---------------------------------------------------------------- dimensions

# (dimension id, name, [(check id, title, max points, check function)])
DIMENSION_SPECS: tuple[tuple[str, str, tuple[tuple[str, str, int, CheckFn], ...]], ...] = (
    (
        "data-sovereignty",
        "Data Sovereignty & Perimeter",
        (
            (
                "no-credentials",
                "No API keys, secrets or .env files in tracked files",
                10,
                _check_no_credentials,
            ),
            ("pii-masking-rules", "PII masking rules defined", 10, _check_pii_rules),
        ),
    ),
    (
        "methodology-as-code",
        "Methodology-as-Code",
        (
            ("kaidf-scaffold", ".kaidf/ scaffold is present", 5, _check_kaidf_scaffold),
            ("mentor-state", "mentor-workflow.json is valid", 5, _check_mentor_state),
            ("specs-parse", "YAML specs parse", 5, _check_specs),
            ("front-matter-v2", "Markdown documents carry Front Matter v2", 5, _check_front_matter),
        ),
    ),
    (
        "regulatory-compliance",
        "Regulatory Compliance",
        (
            (
                "risk-assessment",
                "Risk assessment artifact",
                5,
                _artifact_check("docs/20-ethical-model/risk-assessment.json"),
            ),
            (
                "explicability-schema",
                "Explicability schema artifact",
                5,
                _artifact_check("docs/20-ethical-model/explicability-schema.json"),
            ),
            (
                "hitl-config",
                "Human-in-the-loop configuration",
                5,
                _artifact_check(".kaidf/policy/hitl-config.yaml"),
            ),
            (
                "dataset-audit",
                "Dataset audit manifest",
                5,
                _artifact_check("data/manifests/dataset-audit.yaml"),
            ),
        ),
    ),
    (
        "deterministic-guardrails",
        "Deterministic Guardrails",
        (
            ("ci-workflows", "CI workflows present", 10, _check_ci_workflows),
            ("blocking-gates", "CI gates cannot fail silently", 10, _check_blocking_gates),
        ),
    ),
    (
        "cost-infrastructure-health",
        "Cost & Infrastructure Health",
        (
            ("budget-caps", "Token cap and request timeout configured", 10, _check_budget_caps),
            ("local-fallback", "Local fallback configured", 10, _check_local_fallback),
        ),
    ),
)


def _run_check(
    check_id: str, title: str, max_points: int, check: CheckFn, root: Path
) -> CheckResult:
    fraction, detail = check(root)
    return CheckResult(
        id=check_id,
        title=title,
        max_points=max_points,
        points=round(max_points * fraction),
        detail=detail,
    )


def run_audit(repo_path: str | Path) -> AuditResult:
    """Inspect the repository at ``repo_path`` and return its scorecard. Read-only."""
    root = resolve_repo_root(repo_path)
    dimensions = tuple(
        DimensionResult(
            id=dimension_id,
            name=name,
            max_points=sum(max_points for _, _, max_points, _ in checks),
            checks=tuple(
                _run_check(check_id, title, max_points, check, root)
                for check_id, title, max_points, check in checks
            ),
        )
        for dimension_id, name, checks in DIMENSION_SPECS
    )
    return AuditResult(repo_path=str(root), dimensions=dimensions)
