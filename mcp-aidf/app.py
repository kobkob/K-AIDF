from __future__ import annotations

import json
import os
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from flask import Flask, jsonify, make_response, request
from werkzeug.exceptions import BadRequest

import maturity

app = Flask(__name__)
# No hardcoded fallback: without SECRET_KEY a random per-process secret is used
# (fine for local runs). Containers require SECRET_KEY via docker-compose.yml.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)


def _resolve_bearer_token(configured: str | None) -> str:
    """The configured MCP bearer token, or a random one for this process when none is set.

    A generated token changes on every start and is not shared between gunicorn workers, so
    deployments must set MCP_BEARER_TOKEN (docker-compose.yml requires it).
    """
    token = (configured or "").strip()
    return token or secrets.token_urlsafe(32)


MCP_BEARER_TOKEN = os.environ.get("MCP_BEARER_TOKEN", "").strip()
ACTIVE_BEARER_TOKEN = _resolve_bearer_token(MCP_BEARER_TOKEN)
if not MCP_BEARER_TOKEN:
    app.logger.warning(
        "MCP_BEARER_TOKEN is not set; using a temporary token for this process: %s",
        ACTIVE_BEARER_TOKEN,
    )


TOKEN_SCOPES_ENV = "MCP_TOKEN_SCOPES"


@dataclass(frozen=True)
class Principal:
    """The caller of a request. ``namespaces`` None means unrestricted (the primary token)."""

    namespaces: frozenset[str] | None


def _same_secret(presented: str, expected: str) -> bool:
    # Compare bytes: compare_digest raises TypeError on non-ASCII text.
    return secrets.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def _load_token_scopes(raw: str, primary_token: str) -> dict[str, frozenset[str]]:
    """Parse MCP_TOKEN_SCOPES: a JSON object mapping each extra token to its namespaces.

    Invalid configuration stops the server at startup, instead of silently granting or
    denying access.
    """
    if not raw.strip():
        return {}
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{TOKEN_SCOPES_ENV} is not valid JSON: {exc}") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"{TOKEN_SCOPES_ENV} must be a JSON object of token -> namespaces")
    scopes: dict[str, frozenset[str]] = {}
    for token, namespaces in config.items():
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError(f"{TOKEN_SCOPES_ENV} has an empty token")
        token = token.strip()
        if primary_token and token == primary_token:
            raise RuntimeError(f"{TOKEN_SCOPES_ENV} must not reuse MCP_BEARER_TOKEN")
        if not isinstance(namespaces, list) or not namespaces:
            raise RuntimeError(f"{TOKEN_SCOPES_ENV}: a token needs a non-empty namespace list")
        if not all(isinstance(name, str) and name.strip() for name in namespaces):
            raise RuntimeError(f"{TOKEN_SCOPES_ENV}: namespace names must be non-empty strings")
        scopes[token] = frozenset(name.strip() for name in namespaces)
    return scopes


TOKEN_SCOPES: dict[str, frozenset[str]] = _load_token_scopes(
    os.environ.get(TOKEN_SCOPES_ENV, ""), MCP_BEARER_TOKEN
)


def _resolve_principal(auth_header: str | None) -> Principal | None:
    scheme, _, presented = (auth_header or "").partition(" ")
    if scheme.lower() != "bearer" or not presented:
        return None
    match: Principal | None = None
    if ACTIVE_BEARER_TOKEN and _same_secret(presented, ACTIVE_BEARER_TOKEN):
        match = Principal(namespaces=None)
    # Every configured token is compared, so the timing does not reveal which one matched.
    for token, namespaces in TOKEN_SCOPES.items():
        if _same_secret(presented, token):
            match = Principal(namespaces=namespaces)
    return match


def _check_bearer(auth_header: str | None) -> bool:
    return _resolve_principal(auth_header) is not None


def _www_authenticate(auth_header: str | None) -> str:
    challenge = (
        "Bearer "
        'resource_metadata="https://mcp-aidf.kobkob.org/.well-known/oauth-protected-resource", '
        'scope="mcp"'
    )
    if auth_header:
        # RFC 6750: a credential was presented but it is not valid.
        return challenge + ', error="invalid_token"'
    return challenge


SERVER_VERSION = "0.6.0rc1"
# Protocol revisions this server implements, oldest first. A client asking for any other
# revision gets the newest one back, as the MCP version negotiation rules describe.
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05",)
INTERNAL_ERROR_MESSAGE = "Internal error."
DEFAULT_RESOURCE = "https://mcp-aidf.kobkob.org"
INDEXABLE_ROOT_FILES = {"README.md", "MANIFESTO.md"}
INDEXABLE_SUFFIXES = {".md", ".csv"}
CANONICAL_DOCTRINE_FILES = {
    "docs/00-overview/manifesto.md": "manifesto",
    "docs/00-overview/principles.md": "principles",
    "docs/00-overview/best-practices.md": "best-practices",
    "docs/00-overview/governance.md": "governance",
    "docs/00-overview/maturity.md": "maturity",
    "docs/00-overview/implementation.md": "implementation",
    "MANIFESTO.md": "manifesto",
}
DOCTRINE_PRIORITY = {
    "manifesto": 1000,
    "principles": 900,
    "governance": 800,
    "best-practices": 700,
    "maturity": 600,
    "implementation": 500,
    "training": 400,
    "general": 100,
}
STARTER_VARIANT_DOMAINS = {
    "docs/00-overview/best-practices/seo.md": "seo",
    "docs/00-overview/best-practices/content.md": "content",
    "docs/00-overview/best-practices/research.md": "research",
}
MATURITY_LEVEL_PRIORITY = {
    "experimental": 100,
    "assisted": 200,
    "operational": 300,
    "managed": 400,
    "transformative": 500,
}


def _repo_root() -> Path:
    repo_root = os.environ.get("AIDF_REPO_ROOT", "").strip()
    if not repo_root:
        raise ValueError("AIDF_REPO_ROOT is not configured.")
    path = Path(repo_root).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"AIDF_REPO_ROOT does not exist or is not a directory: {path}")
    return path


def _is_indexable(rel_path: str) -> bool:
    path = PurePosixPath(rel_path)
    if rel_path in INDEXABLE_ROOT_FILES:
        return True
    if not rel_path.startswith("docs/"):
        return False
    return path.suffix in INDEXABLE_SUFFIXES


def _iter_indexable_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(root).as_posix()
        if _is_indexable(rel_path):
            paths.append(file_path)
    return sorted(paths)


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    # Windows checkouts can keep CRLF line endings; normalize so the "---" markers still match.
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    marker = "\n---\n"
    end = text.find(marker, 4)
    if end == -1:
        return {}, text
    front_matter_text = text[4:end]
    body = text[end + len(marker) :]
    data = yaml.safe_load(front_matter_text) or {}
    if not isinstance(data, dict):
        return {}, text
    return data, body


def _first_heading(markdown_body: str) -> str | None:
    for line in markdown_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None


def _infer_document_class(rel_path: str) -> str:
    path = PurePosixPath(rel_path)
    if rel_path in {"LICENSE", "CODEOWNERS", "SECURITY.md"}:
        return "governance-doc"
    if "templates" in path.parts:
        return "template-doc"
    if rel_path.endswith(".prompt.md") or "prompts" in path.parts:
        return "prompt-doc"
    return "core-doc"


def _infer_doctrine_category(rel_path: str, title: str, body: str) -> str:
    if rel_path in CANONICAL_DOCTRINE_FILES:
        return CANONICAL_DOCTRINE_FILES[rel_path]
    text = "\n".join([rel_path, title, body]).casefold()
    if "principles" in text or "princípios" in text or "principios" in text:
        return "principles"
    if "boas práticas" in text or "best practice" in text or "best practices" in text:
        return "best-practices"
    if "governança" in text or "governance" in text or "decision-rights" in text:
        return "governance"
    if "maturidade" in text or "maturity" in text:
        return "maturity"
    if "implementação" in text or "implementation" in text:
        return "implementation"
    if (
        "treinamento" in text
        or "training" in text
        or "certificação" in text
        or "certification" in text
    ):
        return "training"
    return "general"


def _doctrine_priority(category: str) -> int:
    return DOCTRINE_PRIORITY.get(category, 0)


def _is_canonical_doctrine(rel_path: str) -> bool:
    return rel_path in CANONICAL_DOCTRINE_FILES


def _normalize_label(value: str) -> str:
    return value.strip().casefold().replace(" ", "-")


def _variant_domain(rel_path: str) -> str | None:
    return STARTER_VARIANT_DOMAINS.get(rel_path)


def _is_pack_readme(rel_path: str, pack: str | None) -> bool:
    if not pack:
        return False
    path = PurePosixPath(rel_path)
    return path.name == "README.md" and pack in rel_path


def _pack_name(front_matter: dict[str, Any]) -> str | None:
    pack = front_matter.get("pack")
    if isinstance(pack, str) and pack.strip():
        return pack.strip()
    return None


def _namespace_name(front_matter: dict[str, Any]) -> str | None:
    namespace = front_matter.get("namespace")
    if isinstance(namespace, str) and namespace.strip():
        return namespace.strip()
    return None


def _maturity_level(front_matter: dict[str, Any]) -> str | None:
    level = front_matter.get("maturity_level")
    if isinstance(level, str) and level.strip():
        return level.strip()
    return None


def _assessment_type(front_matter: dict[str, Any]) -> str | None:
    assessment_type = front_matter.get("assessment_type")
    if isinstance(assessment_type, str) and assessment_type.strip():
        return assessment_type.strip()
    return None


def _ethical_domain(front_matter: dict[str, Any]) -> str | None:
    ethical_domain = front_matter.get("ethical_domain")
    if isinstance(ethical_domain, str) and ethical_domain.strip():
        return ethical_domain.strip()
    return None


def _control_type(front_matter: dict[str, Any]) -> str | None:
    control_type = front_matter.get("control_type")
    if isinstance(control_type, str) and control_type.strip():
        return control_type.strip()
    return None


def _risk_type(front_matter: dict[str, Any]) -> str | None:
    risk_type = front_matter.get("risk_type")
    if isinstance(risk_type, str) and risk_type.strip():
        return risk_type.strip()
    return None


def _infer_phase(rel_path: str) -> str:
    if rel_path == "README.md":
        return "root"
    parts = PurePosixPath(rel_path).parts
    if len(parts) >= 2 and parts[0] == "docs":
        return parts[1]
    return "root"


def _load_document(root: Path, file_path: Path) -> dict[str, Any]:
    rel_path = file_path.relative_to(root).as_posix()
    raw_text = file_path.read_text(encoding="utf-8")
    front_matter, body = (
        _parse_front_matter(raw_text) if file_path.suffix == ".md" else ({}, raw_text)
    )
    title = front_matter.get("title") or _first_heading(body) or file_path.stem
    doctrine_category = _infer_doctrine_category(rel_path, title, body)
    variant_domain = _variant_domain(rel_path)
    pack = _pack_name(front_matter)
    maturity_level = _maturity_level(front_matter)
    assessment_type = _assessment_type(front_matter)
    ethical_domain = _ethical_domain(front_matter)
    control_type = _control_type(front_matter)
    risk_type = _risk_type(front_matter)
    return {
        "id": front_matter.get("id", rel_path),
        "path": rel_path,
        "title": title,
        "document_class": front_matter.get("document_class", _infer_document_class(rel_path)),
        "phase": front_matter.get("phase", _infer_phase(rel_path)),
        "visibility": front_matter.get("visibility", "internal"),
        "namespace": _namespace_name(front_matter),
        "status": front_matter.get("status", "active"),
        "doctrine_category": doctrine_category,
        "canonical_doctrine": _is_canonical_doctrine(rel_path),
        "doctrine_priority": _doctrine_priority(doctrine_category),
        "variant_domain": variant_domain,
        "pack": pack,
        "maturity_level": maturity_level,
        "assessment_type": assessment_type,
        "ethical_domain": ethical_domain,
        "control_type": control_type,
        "risk_type": risk_type,
        "content": raw_text,
        "body": body,
    }


# In-memory index cache. Validity is checked on every call by comparing a signature of the
# indexable files (path, mtime, size), so unchanged documents are never re-read or re-parsed,
# and edits, additions and removals are visible on the next request.
_index_cache_lock = threading.Lock()
_index_cache: dict[str, Any] = {"root": None, "signature": None, "documents": []}


def _index_signature(root: Path, paths: list[Path]) -> tuple[tuple[str, int, int], ...]:
    entries = []
    for file_path in paths:
        stat = file_path.stat()
        entries.append((file_path.relative_to(root).as_posix(), stat.st_mtime_ns, stat.st_size))
    return tuple(entries)


def _load_index() -> list[dict[str, Any]]:
    root = _repo_root()
    paths = _iter_indexable_paths(root)
    signature = _index_signature(root, paths)
    with _index_cache_lock:
        if _index_cache["root"] == root and _index_cache["signature"] == signature:
            # Shallow copies so callers cannot mutate the cached records.
            return [dict(doc) for doc in _index_cache["documents"]]
    documents = [_load_document(root, file_path) for file_path in paths]
    with _index_cache_lock:
        _index_cache.update(root=root, signature=signature, documents=documents)
    return [dict(doc) for doc in documents]


def _is_visible(doc: dict[str, Any], is_authenticated: bool) -> bool:
    """Visibility ACL: private never, internal only when authenticated, public always.

    A document with no visibility key is public. Any other value fails closed (hidden).
    """
    visibility = doc.get("visibility")
    if visibility == "private":
        return False
    if visibility == "internal":
        return is_authenticated
    if visibility is None or visibility == "public":
        return True
    return False


def _can_read(doc: dict[str, Any], principal: Principal | None) -> bool:
    """Visibility ACL plus tenant scope. Unauthenticated callers (None) see only public docs.

    A scoped token reads documents in its namespaces. A document with no namespace is shared
    with every tenant only when it is public; internal and private documents without a
    namespace belong to the primary token alone.
    """
    if principal is None:
        return _is_visible(doc, is_authenticated=False)
    if principal.namespaces is not None:
        namespace = doc.get("namespace")
        if namespace is None:
            if doc.get("visibility") != "public":
                return False
        elif namespace not in principal.namespaces:
            return False
    return _is_visible(doc, is_authenticated=True)


def _search_documents(
    query: str, limit: int = 10, *, principal: Principal | None = None
) -> list[dict[str, Any]]:
    query_norm = query.strip().casefold()
    if not query_norm:
        return []
    query_label = _normalize_label(query)
    results: list[tuple[int, dict[str, Any]]] = []
    for doc in _load_index():
        if not _can_read(doc, principal):
            continue
        haystack = "\n".join(
            [
                doc["id"],
                doc["path"],
                doc["title"],
                doc["document_class"],
                doc["doctrine_category"],
                doc["variant_domain"] or "",
                doc["pack"] or "",
                doc["maturity_level"] or "",
                doc["assessment_type"] or "",
                doc["ethical_domain"] or "",
                doc["control_type"] or "",
                doc["risk_type"] or "",
                doc["phase"],
                doc["body"],
            ]
        ).casefold()
        if query_norm not in haystack:
            continue
        score_details = {
            "title": 0,
            "id": 0,
            "path": 0,
            "body": 0,
            "doctrine_category": 0,
            "doctrine_exact": 0,
            "canonical_doctrine": 0,
            "doctrine_priority": 0,
            "variant_exact": 0,
            "variant_partial": 0,
            "pack_exact": 0,
            "pack_partial": 0,
            "pack_readme": 0,
            "maturity_level_exact": 0,
            "maturity_level_partial": 0,
            "assessment_exact": 0,
            "assessment_partial": 0,
            "ethical_domain_exact": 0,
            "ethical_domain_partial": 0,
            "control_exact": 0,
            "control_partial": 0,
            "risk_exact": 0,
            "risk_partial": 0,
        }
        if query_norm in doc["title"].casefold():
            score_details["title"] = 50
        if query_norm in doc["id"].casefold():
            score_details["id"] = 40
        if query_norm in doc["path"].casefold():
            score_details["path"] = 30
        if query_norm in doc["body"].casefold():
            score_details["body"] = 10
        category_label = _normalize_label(doc["doctrine_category"])
        if query_label == category_label:
            score_details["doctrine_exact"] = 500
        elif query_norm in doc["doctrine_category"].casefold():
            score_details["doctrine_category"] = 150
        if doc["canonical_doctrine"]:
            score_details["canonical_doctrine"] = 200
        score_details["doctrine_priority"] = doc["doctrine_priority"]
        variant_domain = doc["variant_domain"]
        if variant_domain:
            variant_label = _normalize_label(variant_domain)
            if query_label == variant_label:
                score_details["variant_exact"] = 450
            elif query_norm in variant_domain.casefold():
                score_details["variant_partial"] = 120
        pack = doc["pack"]
        if pack:
            pack_label = _normalize_label(pack)
            if query_label == pack_label:
                score_details["pack_exact"] = 250
                if _is_pack_readme(doc["path"], pack):
                    score_details["pack_readme"] = 1000
            elif query_norm in pack.casefold():
                score_details["pack_partial"] = 90
        maturity_level = doc["maturity_level"]
        if maturity_level:
            level_label = _normalize_label(maturity_level)
            if query_label == level_label:
                score_details["maturity_level_exact"] = 420
            elif query_norm in maturity_level.casefold():
                score_details["maturity_level_partial"] = 140
        assessment_type = doc["assessment_type"]
        if assessment_type:
            assessment_label = _normalize_label(assessment_type)
            if query_label == assessment_label:
                score_details["assessment_exact"] = 180
            elif query_norm in assessment_type.casefold():
                score_details["assessment_partial"] = 80
        ethical_domain = doc["ethical_domain"]
        if ethical_domain:
            ethical_label = _normalize_label(ethical_domain)
            if query_label == ethical_label:
                score_details["ethical_domain_exact"] = 420
            elif query_norm in ethical_domain.casefold():
                score_details["ethical_domain_partial"] = 140
        control_type = doc["control_type"]
        if control_type:
            control_label = _normalize_label(control_type)
            if query_label == control_label:
                score_details["control_exact"] = 180
            elif query_norm in control_type.casefold():
                score_details["control_partial"] = 80
        risk_type = doc["risk_type"]
        if risk_type:
            risk_label = _normalize_label(risk_type)
            if query_label == risk_label:
                score_details["risk_exact"] = 260
            elif query_norm in risk_type.casefold():
                score_details["risk_partial"] = 100
        score = sum(score_details.values())
        doc = dict(doc)
        doc["ranking"] = score_details
        doc["score"] = score
        results.append((score, doc))
    results.sort(key=lambda item: (-item[0], item[1]["path"]))
    trimmed: list[dict[str, Any]] = []
    for _, doc in results[:limit]:
        trimmed.append(
            {
                "id": doc["id"],
                "path": doc["path"],
                "title": doc["title"],
                "document_class": doc["document_class"],
                "doctrine_category": doc["doctrine_category"],
                "canonical_doctrine": doc["canonical_doctrine"],
                "doctrine_priority": doc["doctrine_priority"],
                "variant_domain": doc["variant_domain"],
                "pack": doc["pack"],
                "maturity_level": doc["maturity_level"],
                "assessment_type": doc["assessment_type"],
                "ethical_domain": doc["ethical_domain"],
                "control_type": doc["control_type"],
                "risk_type": doc["risk_type"],
                "score": doc["score"],
                "ranking": doc["ranking"],
                "phase": doc["phase"],
                "visibility": doc["visibility"],
                "status": doc["status"],
                "snippet": doc["body"][:240].strip(),
            }
        )
    return trimmed


def _fetch_document(doc_id: str, *, principal: Principal | None = None) -> dict[str, Any] | None:
    for doc in _load_index():
        # Hidden documents look exactly like missing ones, so their existence is not revealed.
        if not _can_read(doc, principal):
            continue
        if doc["id"] == doc_id or doc["path"] == doc_id:
            return {
                "id": doc["id"],
                "path": doc["path"],
                "title": doc["title"],
                "document_class": doc["document_class"],
                "doctrine_category": doc["doctrine_category"],
                "canonical_doctrine": doc["canonical_doctrine"],
                "doctrine_priority": doc["doctrine_priority"],
                "variant_domain": doc["variant_domain"],
                "pack": doc["pack"],
                "maturity_level": doc["maturity_level"],
                "assessment_type": doc["assessment_type"],
                "ethical_domain": doc["ethical_domain"],
                "control_type": doc["control_type"],
                "risk_type": doc["risk_type"],
                "phase": doc["phase"],
                "visibility": doc["visibility"],
                "status": doc["status"],
                "content": doc["content"],
            }
    return None


def _json_error(req_id: Any, code: int, message: str, status_code: int = 400) -> tuple[Any, int]:
    return (
        jsonify(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": code, "message": message},
            }
        ),
        status_code,
    )


def _negotiate_protocol_version(requested: Any) -> str:
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return SUPPORTED_PROTOCOL_VERSIONS[-1]


@app.route("/mcp", methods=["POST"])
def mcp_endpoint():
    try:
        data = request.get_json(force=True)
    except BadRequest:
        return _json_error(None, -32700, "Parse error: request body is not valid JSON.")
    if not isinstance(data, dict):
        return _json_error(None, -32600, "Invalid Request: expected a JSON-RPC object.")

    req_id = data.get("id")
    try:
        return _handle_mcp_request(data, req_id)
    except Exception:
        # The traceback stays in the server log; the client only sees a generic message.
        app.logger.exception("Unhandled error while handling MCP request")
        return _json_error(req_id, -32603, INTERNAL_ERROR_MESSAGE, 500)


def _handle_mcp_request(data: dict[str, Any], req_id: Any):
    auth_header = request.headers.get("Authorization")
    principal = _resolve_principal(auth_header)
    if principal is None:
        body = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": 401,
                "message": "authorization_required",
                "data": {
                    "_meta": {
                        "mcp/www_authenticate": (
                            "Bearer "
                            'resource_metadata="https://mcp-aidf.kobkob.org/.well-known/'
                            'oauth-protected-resource", '
                            'scope="mcp", error="authorization_required", '
                            'error_description="Provide a valid bearer token."'
                        )
                    }
                },
            },
        }
        resp = make_response(jsonify(body), 401)
        resp.headers["WWW-Authenticate"] = _www_authenticate(auth_header)
        return resp

    method = data.get("method")
    params = data.get("params") or {}
    if not isinstance(params, dict):
        return _json_error(req_id, -32602, "Invalid params: expected an object.")

    if method == "initialize":
        return jsonify(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": _negotiate_protocol_version(params.get("protocolVersion")),
                    "serverInfo": {"name": "mcp-aidf", "version": SERVER_VERSION},
                    "capabilities": {"tools": {}},
                },
            }
        )

    if method == "tools/list":
        return jsonify(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "search",
                            "description": "Search indexed documents in a configured local K-AIDF "
                            "repository.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                                },
                                "required": ["query"],
                            },
                        },
                        {
                            "name": "fetch",
                            "description": "Fetch a document by metadata id or repository-relative "
                            "path.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"id": {"type": "string"}},
                                "required": ["id"],
                            },
                        },
                        {
                            "name": "get_maturity_scorecard",
                            "description": "Return the KAIDF-AMM maturity matrix: dimensions, "
                            "point weights, severities and the criteria the audit engine applies.",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                        {
                            "name": "evaluate_repository_maturity",
                            "description": "Score a repository under the configured K-AIDF root. "
                            "Returns the global and per-dimension score, violations and gaps by "
                            "severity, and an ordered mitigation backlog. Requires the primary "
                            "token.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "path": {
                                        "type": "string",
                                        "description": "Directory to evaluate, relative to the "
                                        "configured root or inside it. Defaults to the root.",
                                    },
                                    "format": {
                                        "type": "string",
                                        "enum": list(maturity.OUTPUT_FORMATS),
                                        "description": "json (default) or prompt, a ready-made "
                                        "prompt for a local model.",
                                    },
                                },
                            },
                        },
                    ]
                },
            }
        )

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "search":
            query = str(args.get("query", "")).strip()
            try:
                limit = int(args.get("limit", 10))
            except (TypeError, ValueError):
                return _json_error(req_id, -32602, "Invalid params: limit must be an integer.")
            results = {"results": _search_documents(query, limit, principal=principal)}
            return jsonify(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(results)}]},
                }
            )

        if name == "fetch":
            doc_id = str(args.get("id", "")).strip()
            if not doc_id:
                return _json_error(req_id, -32602, "Missing document id.")
            doc = _fetch_document(doc_id, principal=principal)
            if doc is None:
                return _json_error(req_id, -32602, f"Document not found: {doc_id}", 404)
            return jsonify(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(doc)}]},
                }
            )
        if name == "get_maturity_scorecard":
            return _maturity_tool(req_id, maturity.get_scorecard_matrix)

        if name == "evaluate_repository_maturity":
            if principal.namespaces is not None:
                return _json_error(
                    req_id,
                    -32001,
                    "Forbidden: repository evaluation requires the primary token.",
                    403,
                )
            return _evaluate_maturity_tool(req_id, args)
        return _json_error(req_id, -32602, f"Unknown tool: {name}")

    return _json_error(req_id, -32601, f"Method not found: {method}")


def _tool_text_result(req_id: Any, text: str):
    return jsonify(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": text}]},
        }
    )


def _maturity_tool(req_id: Any, action):
    try:
        payload = action()
    except maturity.MaturityError as exc:
        return _maturity_error(req_id, exc)
    return _tool_text_result(req_id, json.dumps(payload, ensure_ascii=False))


def _evaluate_maturity_tool(req_id: Any, args: dict[str, Any]):
    path = args.get("path")
    output_format = args.get("format", "json")
    if path is not None and not isinstance(path, str):
        return _json_error(req_id, -32602, "Invalid params: path must be a string.")
    if output_format not in maturity.OUTPUT_FORMATS:
        return _json_error(req_id, -32602, "Invalid params: format must be json or prompt.")
    try:
        repo_root = _repo_root()
    except ValueError as exc:
        return _json_error(req_id, -32000, str(exc), 503)
    try:
        evaluation = maturity.evaluate_repository(repo_root, path)
    except maturity.MaturityError as exc:
        return _maturity_error(req_id, exc)
    if output_format == "prompt":
        return _tool_text_result(req_id, maturity.render_mitigation_prompt(evaluation))
    return _tool_text_result(req_id, json.dumps(evaluation, ensure_ascii=False))


def _maturity_error(req_id: Any, exc: maturity.MaturityError):
    if exc.code == maturity.ENGINE_UNAVAILABLE:
        return _json_error(req_id, exc.code, exc.message, 503)
    return _json_error(req_id, exc.code, f"Invalid params: {exc.message}")


@app.route("/.well-known/oauth-protected-resource")
def protected_resource_metadata():
    return jsonify(
        {
            "resource": DEFAULT_RESOURCE,
            "scopes_supported": ["mcp"],
            "resource_documentation": f"{DEFAULT_RESOURCE}/docs",
        }
    )


@app.route("/")
def root():
    auth_header = request.headers.get("Authorization")
    if not _check_bearer(auth_header):
        response = jsonify({"error": "authorization_required"})
        response.status_code = 401
        response.headers["WWW-Authenticate"] = _www_authenticate(auth_header)
        return response
    return "MCP Server Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7777, debug=False)
