# Build from the repository root so the image can bundle the agent-aidf audit engine:
#   docker build -f mcp-aidf/Dockerfile .
# mcp-aidf/docker-compose.yml and deploy/easypanel/easypanel.json set this context.

# Stage 1: build the agent-aidf wheel. Nothing from this stage but the wheel reaches the runtime.
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install build wheel

COPY agent-aidf /src/agent-aidf
RUN python -m build --wheel --outdir /dist /src/agent-aidf

# Stage 2: the runtime image.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AIDF_REPO_ROOT=/workspace \
    PORT=7777

# git: the audit engine runs `git ls-files` on a repository that has a .git directory. The volume
# is usually cloned by another user, so git would refuse it as "dubious ownership"; trust exactly
# the mount point, not every path.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory /workspace

# Unprivileged runtime user; the app only needs to read its code and the read-only mounted
# K-AIDF repository.
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser \
    && mkdir -p /workspace

WORKDIR /app

COPY mcp-aidf/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=builder /dist/ /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels

COPY mcp-aidf/app.py mcp-aidf/maturity.py ./

# Listen port: 7777 unless the platform sets PORT (deploy/easypanel/easypanel.json sets 8000).
EXPOSE 7777

USER appuser

# Healthy when the unauthenticated protected-resource metadata answers 200 on the port the server
# listens on. Python's urllib is already in the image, so no curl is needed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, sys, urllib.request as u; r = u.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '7777') + '/.well-known/oauth-protected-resource', timeout=4); sys.exit(0 if r.status == 200 else 1)"]

# Production WSGI server instead of the Flask development server. The exec form does not expand
# variables, so a shell resolves PORT and then execs gunicorn, which stays PID 1.
CMD ["sh", "-c", "exec gunicorn --bind \"0.0.0.0:${PORT:-7777}\" --workers 2 --access-logfile - app:app"]
