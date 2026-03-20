from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from flask import Flask, jsonify, make_response, redirect, request

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-in-prod")

SERVER_VERSION = "0.1.1"
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
    if "treinamento" in text or "training" in text or "certificação" in text or "certification" in text:
        return "training"
    return "general"


def _doctrine_priority(category: str) -> int:
    return DOCTRINE_PRIORITY.get(category, 0)


def _is_canonical_doctrine(rel_path: str) -> bool:
    return rel_path in CANONICAL_DOCTRINE_FILES


def _normalize_label(value: str) -> str:
    return value.strip().casefold().replace(" ", "-")


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
    front_matter, body = _parse_front_matter(raw_text) if file_path.suffix == ".md" else ({}, raw_text)
    title = front_matter.get("title") or _first_heading(body) or file_path.stem
    doctrine_category = _infer_doctrine_category(rel_path, title, body)
    return {
        "id": front_matter.get("id", rel_path),
        "path": rel_path,
        "title": title,
        "document_class": front_matter.get("document_class", _infer_document_class(rel_path)),
        "phase": front_matter.get("phase", _infer_phase(rel_path)),
        "visibility": front_matter.get("visibility", "internal"),
        "status": front_matter.get("status", "active"),
        "doctrine_category": doctrine_category,
        "canonical_doctrine": _is_canonical_doctrine(rel_path),
        "doctrine_priority": _doctrine_priority(doctrine_category),
        "content": raw_text,
        "body": body,
    }


def _load_index() -> list[dict[str, Any]]:
    root = _repo_root()
    return [_load_document(root, file_path) for file_path in _iter_indexable_paths(root)]


def _search_documents(query: str, limit: int = 10) -> list[dict[str, Any]]:
    query_norm = query.strip().casefold()
    if not query_norm:
        return []
    query_label = _normalize_label(query)
    results: list[tuple[int, dict[str, Any]]] = []
    for doc in _load_index():
        haystack = "\n".join(
            [
                doc["id"],
                doc["path"],
                doc["title"],
                doc["document_class"],
                doc["doctrine_category"],
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
                "score": doc["score"],
                "ranking": doc["ranking"],
                "phase": doc["phase"],
                "visibility": doc["visibility"],
                "status": doc["status"],
                "snippet": doc["body"][:240].strip(),
            }
        )
    return trimmed


def _fetch_document(doc_id: str) -> dict[str, Any] | None:
    for doc in _load_index():
        if doc["id"] == doc_id or doc["path"] == doc_id:
            return {
                "id": doc["id"],
                "path": doc["path"],
                "title": doc["title"],
                "document_class": doc["document_class"],
                "doctrine_category": doc["doctrine_category"],
                "canonical_doctrine": doc["canonical_doctrine"],
                "doctrine_priority": doc["doctrine_priority"],
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


@app.route("/mcp", methods=["POST"])
def mcp_endpoint():
    data = request.get_json(force=True) or {}
    req_id = data.get("id")

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        body = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": 401,
                "message": "authorization_required",
                "data": {
                    "_meta": {
                        "mcp/www_authenticate": (
                            'Bearer resource_metadata="https://mcp-aidf.kobkob.org/.well-known/oauth-protected-resource", '
                            'scope="mcp", error="authorization_required", error_description="Link your account"'
                        )
                    }
                },
            },
        }
        resp = make_response(jsonify(body), 401)
        resp.headers["WWW-Authenticate"] = (
            'Bearer resource_metadata="https://mcp-aidf.kobkob.org/.well-known/oauth-protected-resource", scope="mcp"'
        )
        return resp

    method = data.get("method")
    params = data.get("params") or {}

    if method == "initialize":
        client_proto = params.get("protocolVersion")
        return jsonify(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": client_proto,
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
                            "description": "Search indexed documents in a configured local K-AIDF repository.",
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
                            "description": "Fetch a document by metadata id or repository-relative path.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"id": {"type": "string"}},
                                "required": ["id"],
                            },
                        },
                    ]
                },
            }
        )

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}

        try:
            if name == "search":
                query = str(args.get("query", "")).strip()
                limit = int(args.get("limit", 10))
                results = {"results": _search_documents(query, limit)}
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
                doc = _fetch_document(doc_id)
                if doc is None:
                    return _json_error(req_id, -32602, f"Document not found: {doc_id}", 404)
                return jsonify(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": json.dumps(doc)}]},
                    }
                )
        except ValueError as exc:
            return _json_error(req_id, -32603, str(exc), 500)

        return _json_error(req_id, -32602, f"Unknown tool: {name}")

    return _json_error(req_id, -32601, f"Method not found: {method}")


@app.route("/.well-known/oauth-protected-resource")
def protected_resource_metadata():
    return jsonify(
        {
            "resource": DEFAULT_RESOURCE,
            "authorization_servers": [DEFAULT_RESOURCE],
            "scopes_supported": ["mcp"],
            "resource_documentation": f"{DEFAULT_RESOURCE}/docs",
        }
    )


@app.route("/.well-known/oauth-authorization-server")
def oauth_config():
    return jsonify(
        {
            "issuer": DEFAULT_RESOURCE,
            "authorization_endpoint": f"{DEFAULT_RESOURCE}/oauth/authorize",
            "token_endpoint": f"{DEFAULT_RESOURCE}/oauth/token",
            "registration_endpoint": f"{DEFAULT_RESOURCE}/oauth/register",
            "scopes_supported": ["mcp"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
        }
    )


@app.route("/oauth/authorize")
def oauth_authorize():
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state")
    resource = request.args.get("resource")

    if not redirect_uri or not state:
        return "Missing required parameters", 400

    auth_code = "auth_code_123"
    redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"
    if resource:
        redirect_url += f"&resource={resource}"
    return redirect(redirect_url)


@app.route("/oauth/register", methods=["POST"])
def oauth_register():
    data = request.get_json() or {}
    requested_auth_method = data.get("token_endpoint_auth_method", "client_secret_post")
    return jsonify(
        {
            "client_id": "mcp_client",
            "client_secret": "mcp_secret",
            "token_endpoint_auth_method": requested_auth_method,
        }
    )


@app.route("/oauth/token", methods=["POST"])
def oauth_token():
    data = request.get_json(silent=True) or {}
    form_data = request.form.to_dict()
    token_data = {**data, **form_data}
    resource = token_data.get("resource")

    response = {"access_token": "mcp_token", "token_type": "bearer", "expires_in": 3600}
    if resource:
        response["resource"] = resource
    return jsonify(response)


@app.route("/")
def root():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        response = jsonify({"error": "authorization_required"})
        response.status_code = 401
        response.headers["WWW-Authenticate"] = (
            'Bearer resource_metadata="https://mcp-aidf.kobkob.org/.well-known/oauth-protected-resource"'
        )
        return response
    return "MCP Server Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7777, debug=False)
