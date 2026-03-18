from flask import Flask, redirect, request, session, jsonify, make_response
import os
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')

@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    data = request.get_json(force=True) or {}
    req_id = data.get("id")

    auth_header = request.headers.get('Authorization')
    if not auth_header:
        body = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": 401,
                "message": "authorization_required",
                "data": {
                    "_meta": {
                        "mcp/www_authenticate":
                            'Bearer resource_metadata="https://mcp-aidf.kobkob.org/.well-known/oauth-protected-resource", '
                            'scope="mcp", error="authorization_required", error_description="Link your account"'
                    }
                }
            }
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
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": client_proto,
                "serverInfo": {"name": "mcp-aidf", "version": "0.1.0"},
                "capabilities": {"tools": {}}
            }
        })

    if method == "tools/list":
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "search",
                        "description": "Search AIDF content.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"]
                        }
                    },
                    {
                        "name": "fetch",
                        "description": "Fetch a document by id.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                            "required": ["id"]
                        }
                    }
                ]
            }
        })

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "search":
            results = {"results": []}
            return jsonify({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(results)}]
                }
            })

        if name == "fetch":
            doc = {"id": args.get("id"), "title": "Example", "url": "https://mcp-aidf.kobkob.org/"}
            return jsonify({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(doc)}]
                }
            })

        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32602, "message": f"Unknown tool: {name}"}
        }), 400

    return jsonify({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    }), 400

@app.route('/.well-known/oauth-protected-resource')
def protected_resource_metadata():
    return jsonify({
        "resource": "https://mcp-aidf.kobkob.org",
        "authorization_servers": ["https://mcp-aidf.kobkob.org"],
        "scopes_supported": ["mcp"],
        "resource_documentation": "https://mcp-aidf.kobkob.org/docs"
    })

@app.route('/.well-known/oauth-authorization-server')
def oauth_config():
    return jsonify({
        "issuer": "https://mcp-aidf.kobkob.org",
        "authorization_endpoint": "https://mcp-aidf.kobkob.org/oauth/authorize",
        "token_endpoint": "https://mcp-aidf.kobkob.org/oauth/token",
        "registration_endpoint": "https://mcp-aidf.kobkob.org/oauth/register",
        "scopes_supported": ["mcp"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "client_credentials"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"]
    })

@app.route('/oauth/authorize')
def oauth_authorize():
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    state = request.args.get('state')
    resource = request.args.get('resource')
    code_challenge = request.args.get('code_challenge')
    
    if not redirect_uri or not state:
        return "Missing required parameters", 400
    
    # Generate auth code and redirect back (preserve resource in state)
    auth_code = "auth_code_123"
    redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"
    if resource:
        redirect_url += f"&resource={resource}"
    
    return redirect(redirect_url)

@app.route('/oauth/register', methods=['POST'])
def oauth_register():
    data = request.get_json() or {}
    requested_auth_method = data.get('token_endpoint_auth_method', 'client_secret_post')
    
    return jsonify({
        "client_id": "mcp_client", 
        "client_secret": "mcp_secret",
        "token_endpoint_auth_method": requested_auth_method
    })

@app.route('/oauth/token', methods=['POST'])
def oauth_token():
    data = request.get_json(silent=True) or {}
    form_data = request.form.to_dict()
    
    # Handle both JSON and form data
    token_data = {**data, **form_data}
    resource = token_data.get('resource')
    
    response = {
        "access_token": "mcp_token", 
        "token_type": "bearer",
        "expires_in": 3600
    }
    
    if resource:
        response["resource"] = resource
    
    return jsonify(response)

@app.route('/')
def root():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        response = jsonify({"error": "authorization_required"})
        response.status_code = 401
        response.headers['WWW-Authenticate'] = 'Bearer resource_metadata="https://mcp-aidf.kobkob.org/.well-known/oauth-protected-resource"'
        return response
    return "MCP Server Running"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7777, debug=False)
