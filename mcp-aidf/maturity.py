"""KAIDF-AMM maturity tools for the MCP server.

Two read-only tools are built on the audit engine in `agent-aidf` (`agent_aidf.audit`):

- `get_maturity_scorecard` returns the matrix: dimensions, weights, and the check criteria.
- `evaluate_repository_maturity` scores one repository and returns violations, gaps by severity
  and an ordered mitigation backlog. It can also return a prompt for a local model.

The engine is imported lazily. A deployment without `agent-aidf` gets a clear error from these
tools and keeps working for `search` and `fetch`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEVERITY_ORDER: tuple[str, ...] = ("critical", "high", "medium", "low")
OUTPUT_FORMATS = ("json", "prompt")

# JSON-RPC codes: -32602 is a bad request, -32000 is a server-side condition.
INVALID_PARAMS = -32602
ENGINE_UNAVAILABLE = -32000


class MaturityError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _engine():
    try:
        from agent_aidf import audit
    except ImportError as exc:
        raise MaturityError(
            ENGINE_UNAVAILABLE,
            "The KAIDF-AMM audit engine (agent-aidf) is not installed in this deployment.",
        ) from exc
    return audit


def get_scorecard_matrix() -> dict[str, Any]:
    engine = _engine()
    dimensions = []
    for dimension_id, name, checks in engine.DIMENSION_SPECS:
        dimensions.append(
            {
                "id": dimension_id,
                "name": name,
                "max_points": sum(max_points for _, _, max_points, _ in checks),
                "checks": [
                    {
                        "id": check_id,
                        "title": title,
                        "max_points": max_points,
                        "severity": engine.SEVERITIES[check_id],
                        "remediation": engine.REMEDIATIONS[check_id],
                    }
                    for check_id, title, max_points, _ in checks
                ],
            }
        )
    return {
        "framework": "KAIDF-AMM",
        "total_points": sum(dimension["max_points"] for dimension in dimensions),
        "tiers": [{"name": name, "min_score": minimum} for name, minimum in engine.TIERS]
        + [{"name": engine.UNRATED, "min_score": 0}],
        "severity_order": list(SEVERITY_ORDER),
        "dimensions": dimensions,
    }


def resolve_evaluation_path(repo_root: Path, requested: str | None) -> Path:
    """Map the requested path to a directory inside repo_root, or raise.

    Relative paths are taken from repo_root. Symlinks are resolved first, so a link pointing
    outside the root is rejected. Containment is checked before existence, so the reply does
    not reveal whether a path outside the root exists.
    """
    base = repo_root.resolve()
    text = (requested or "").strip()
    if not text:
        return base
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    target = candidate.resolve()
    if not target.is_relative_to(base):
        raise MaturityError(INVALID_PARAMS, "path is outside the configured repository root.")
    if not target.exists():
        raise MaturityError(INVALID_PARAMS, f"path does not exist: {text}")
    if not target.is_dir():
        raise MaturityError(INVALID_PARAMS, f"path is not a directory: {text}")
    return target


def evaluate_repository(repo_root: Path, requested: str | None = None) -> dict[str, Any]:
    target = resolve_evaluation_path(repo_root, requested)
    engine = _engine()
    result = engine.run_audit(target)
    rank = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}

    violations = []
    for dimension, check in engine.failed_checks(result):
        violations.append(
            {
                "check_id": check.id,
                "title": check.title,
                "dimension": {"id": dimension.id, "name": dimension.name},
                "severity": check.severity,
                "points": check.points,
                "max_points": check.max_points,
                "gap_points": check.max_points - check.points,
                "detail": check.detail,
                "remediation": check.remediation,
            }
        )
    violations.sort(
        key=lambda item: (rank[item["severity"]], -item["gap_points"], item["check_id"])
    )

    gaps_by_severity = {severity: 0 for severity in SEVERITY_ORDER}
    for item in violations:
        gaps_by_severity[item["severity"]] += 1

    backlog = [
        {
            "priority": position,
            "severity": item["severity"],
            "check_id": item["check_id"],
            "action": item["remediation"],
            "points_recoverable": item["gap_points"],
        }
        for position, item in enumerate(violations, start=1)
    ]

    return {
        "repo_root": result.repo_path,
        "score": result.score,
        "max_score": result.max_score,
        "tier": result.tier,
        "dimensions": [
            {
                "id": dimension.id,
                "name": dimension.name,
                "points": dimension.points,
                "max_points": dimension.max_points,
            }
            for dimension in result.dimensions
        ],
        "violations": violations,
        "gaps_by_severity": gaps_by_severity,
        "recommendations": backlog,
    }


MITIGATION_PROMPT = """\
Você é um assistente de governança K-AIDF. Use somente os dados JSON abaixo, sem inventar \
achados que não estejam neles.

Responda em português, neste formato:

1. Diagnóstico: até 5 linhas com o score, o tier e o estado geral da governança.
2. Backlog de mitigação: lista numerada na ordem do campo "recommendations". Para cada item,
   informe a ação, o critério de aceite e os pontos recuperáveis. Trate primeiro os itens
   "critical" e depois os "high".

Dados da avaliação:
```json
{evaluation}
```
"""


def render_mitigation_prompt(evaluation: dict[str, Any]) -> str:
    payload = json.dumps(evaluation, ensure_ascii=False, indent=2)
    return MITIGATION_PROMPT.format(evaluation=payload)
