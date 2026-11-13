#!/usr/bin/env bash
# Builds the mcp-aidf image from the repository root and checks that the container serves the
# maturity tools (200, not the 503 of an image without the engine) and reports healthy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="kaidf-mcp-aidf:check"
NAME="kaidf-mcp-aidf-check"
TOKEN="check-token-$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
WORKSPACE="$(mktemp -d)"
BODY="$(mktemp)"

cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -rf "$WORKSPACE" "$BODY"
}
trap cleanup EXIT

docker build -q -f "$ROOT/mcp-aidf/Dockerfile" -t "$IMAGE" "$ROOT" >/dev/null

# A repository with a .git owned by another user: the case the image's safe.directory covers.
git -C "$WORKSPACE" init -q
printf '# Demo\n' > "$WORKSPACE/README.md"
git -C "$WORKSPACE" add README.md
git -C "$WORKSPACE" -c user.email=check@localhost -c user.name=check commit -qm init
chmod -R a+rX "$WORKSPACE"

docker run -d --name "$NAME" -e MCP_BEARER_TOKEN="$TOKEN" -e MCP_PUBLIC_URL=http://localhost:7777 \
  -p 127.0.0.1::7777 -v "$WORKSPACE:/workspace" "$IMAGE" >/dev/null
PORT_MAP="$(docker port "$NAME" 7777/tcp | head -n1 | sed 's/.*://')"

for _ in $(seq 1 60); do
  [[ "$(docker inspect -f '{{.State.Health.Status}}' "$NAME")" == "healthy" ]] && break
  sleep 1
done
[[ "$(docker inspect -f '{{.State.Health.Status}}' "$NAME")" == "healthy" ]] \
  || { echo "container is not healthy"; docker logs "$NAME"; exit 1; }

for tool in get_maturity_scorecard evaluate_repository_maturity; do
  status="$(curl -s -o "$BODY" -w '%{http_code}' -X POST "http://127.0.0.1:$PORT_MAP/mcp" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$tool\",\"arguments\":{}}}")"
  if [[ "$status" != "200" ]] || grep -q '"error"' "$BODY"; then
    echo "$tool answered HTTP $status:"; cat "$BODY"; echo; docker logs "$NAME"; exit 1
  fi
  echo "$tool: HTTP 200"
done
echo "image check passed"
