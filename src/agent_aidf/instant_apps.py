from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

APP_METADATA_FILENAME = "app.json"
APPS_DIRNAME = "apps"
DEFAULT_WEB_PORT = 8765
MENTOR_NOTES_FILENAME = "mentor-notes.md"
MENTOR_BRIEF_FILENAME = "mentor-brief.json"
RUNTIME_STATE_FILENAME = "app-runtime.json"
RUNTIME_LOG_FILENAME = "app-runtime.log"


@dataclass(frozen=True)
class InstantApp:
    app_id: str
    mode: str
    kind: str
    root: Path
    entrypoint: Path
    title: str
    description: str
    url: str | None


@dataclass(frozen=True)
class InstantAppRuntime:
    app_id: str
    status: str
    pid: int | None
    port: int | None
    command: list[str]
    log_path: Path


def apps_root(repo_root: str | Path | None) -> Path:
    return Path(repo_root).expanduser().resolve() / APPS_DIRNAME


def list_instant_apps(repo_root: str | Path | None) -> list[InstantApp]:
    root = apps_root(repo_root)
    if not root.is_dir():
        return []
    apps: list[InstantApp] = []
    for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
        app = load_instant_app(candidate)
        if app is not None:
            apps.append(app)
    return apps


def load_instant_app(ref: str | Path) -> InstantApp | None:
    root = Path(ref).expanduser().resolve()
    metadata_path = root / APP_METADATA_FILENAME
    if not metadata_path.is_file():
        return None
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    app_id = data.get("app_id")
    mode = data.get("mode")
    kind = data.get("kind")
    title = data.get("title")
    description = data.get("description")
    entrypoint = data.get("entrypoint")
    if not all(isinstance(value, str) and value for value in [app_id, mode, kind, title, description, entrypoint]):
        return None
    url = data.get("url")
    if url is not None and not isinstance(url, str):
        url = None
    return InstantApp(
        app_id=app_id,
        mode=mode,
        kind=kind,
        root=root,
        entrypoint=root / entrypoint,
        title=title,
        description=description,
        url=url,
    )


def get_instant_app(repo_root: str | Path | None, ref: str) -> InstantApp | None:
    direct = load_instant_app(ref)
    if direct is not None:
        return direct
    candidate = apps_root(repo_root) / ref
    return load_instant_app(candidate)


def create_instant_app(
    repo_root: str | Path | None,
    *,
    app_id: str,
    mode: str,
    kind: str,
) -> InstantApp:
    normalized_mode = mode.strip().casefold()
    normalized_kind = kind.strip().casefold()
    if normalized_mode not in {"persistent", "ephemeral"}:
        raise ValueError(f"Unsupported instant app mode: {mode}")
    if normalized_kind not in {"shell", "web"}:
        raise ValueError(f"Unsupported instant app kind: {kind}")

    slug = _slugify(app_id)
    if not slug:
        raise ValueError("Instant app id must contain at least one alphanumeric character.")

    repo = Path(repo_root).expanduser().resolve()
    if normalized_mode == "persistent":
        root = apps_root(repo) / slug
        if root.exists():
            raise ValueError(f"Instant app already exists: {root}")
        root.mkdir(parents=True, exist_ok=False)
    else:
        root = Path(tempfile.mkdtemp(prefix=f"agent-aidf-{slug}-"))

    _scaffold_instant_app(root, app_id=slug, mode=normalized_mode, kind=normalized_kind)
    app = load_instant_app(root)
    if app is None:
        raise RuntimeError(f"Failed to load scaffolded instant app metadata from {root}")
    return app


def ensure_persistent_instant_app(
    repo_root: str | Path | None,
    *,
    app_id: str,
    kind: str,
) -> tuple[InstantApp, bool]:
    slug = _slugify(app_id)
    if not slug:
        raise ValueError("Instant app id must contain at least one alphanumeric character.")
    existing = get_instant_app(repo_root, slug)
    if existing is not None:
        return existing, False
    return create_instant_app(repo_root, app_id=slug, mode="persistent", kind=kind), True


def append_mentor_note(
    repo_root: str | Path | None,
    app_id: str,
    *,
    heading: str,
    body: str,
) -> Path:
    app = get_instant_app(repo_root, app_id)
    if app is None:
        raise ValueError(f"Instant app not found: {app_id}")
    notes_path = app.root / MENTOR_NOTES_FILENAME
    existing = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else f"# Mentor Notes for {app.app_id}\n"
    entry = f"\n## {heading}\n\n{body.strip()}\n"
    notes_path.write_text(existing.rstrip() + entry + "\n", encoding="utf-8")
    return notes_path


def runtime_state_path(repo_root: str | Path | None, app_id: str) -> Path:
    app = get_instant_app(repo_root, app_id)
    if app is None:
        raise ValueError(f"Instant app not found: {app_id}")
    return app.root / RUNTIME_STATE_FILENAME


def load_instant_app_runtime(repo_root: str | Path | None, app_id: str) -> InstantAppRuntime | None:
    path = runtime_state_path(repo_root, app_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    log_path_raw = data.get("log_path")
    command = data.get("command", [])
    if not isinstance(log_path_raw, str) or not isinstance(command, list):
        return None
    return InstantAppRuntime(
        app_id=str(data.get("app_id", app_id)),
        status=str(data.get("status", "unknown")),
        pid=int(data["pid"]) if isinstance(data.get("pid"), int) else None,
        port=int(data["port"]) if isinstance(data.get("port"), int) else None,
        command=[str(item) for item in command],
        log_path=Path(log_path_raw),
    )


def run_instant_app(
    repo_root: str | Path | None,
    app_id: str,
    *,
    port: int | None = None,
) -> InstantAppRuntime:
    app = get_instant_app(repo_root, app_id)
    if app is None:
        raise ValueError(f"Instant app not found: {app_id}")
    if app.kind != "web":
        raise ValueError(f"Background runtime is currently supported only for web instant apps: {app_id}")
    existing = load_instant_app_runtime(repo_root, app_id)
    if existing and existing.pid and _process_is_running(existing.pid):
        return existing

    selected_port = port or _find_free_port()
    command = [sys.executable, str(app.entrypoint)]
    log_path = app.root / RUNTIME_LOG_FILENAME
    log_handle = log_path.open("ab")
    env = os.environ.copy()
    env["INSTANT_APP_PORT"] = str(selected_port)
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        command,
        cwd=app.root,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    log_handle.close()
    _wait_for_port("127.0.0.1", selected_port, timeout_s=2.0)
    runtime = InstantAppRuntime(
        app_id=app.app_id,
        status="running",
        pid=process.pid,
        port=selected_port,
        command=command,
        log_path=log_path,
    )
    _write_runtime_state(app.root / RUNTIME_STATE_FILENAME, runtime)
    return runtime


def stop_instant_app(repo_root: str | Path | None, app_id: str) -> InstantAppRuntime:
    app = get_instant_app(repo_root, app_id)
    if app is None:
        raise ValueError(f"Instant app not found: {app_id}")
    runtime = load_instant_app_runtime(repo_root, app_id)
    if runtime is None:
        stopped = InstantAppRuntime(
            app_id=app.app_id,
            status="stopped",
            pid=None,
            port=None,
            command=[],
            log_path=app.root / RUNTIME_LOG_FILENAME,
        )
        _write_runtime_state(app.root / RUNTIME_STATE_FILENAME, stopped)
        return stopped
    if runtime.pid and _process_is_running(runtime.pid):
        os.kill(runtime.pid, signal.SIGTERM)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if not _process_is_running(runtime.pid):
                break
            time.sleep(0.05)
        if _process_is_running(runtime.pid):
            os.kill(runtime.pid, signal.SIGKILL)
    stopped = InstantAppRuntime(
        app_id=runtime.app_id,
        status="stopped",
        pid=None,
        port=runtime.port,
        command=runtime.command,
        log_path=runtime.log_path,
    )
    _write_runtime_state(app.root / RUNTIME_STATE_FILENAME, stopped)
    return stopped


def apply_mentor_update(
    repo_root: str | Path | None,
    app_id: str,
    *,
    step: int,
    category: str,
    question: str,
    answer: str,
    mentor_reply: str,
) -> Path:
    app = get_instant_app(repo_root, app_id)
    if app is None:
        raise ValueError(f"Instant app not found: {app_id}")
    brief = {
        "app_id": app.app_id,
        "kind": app.kind,
        "step": step,
        "category": category,
        "question": question,
        "answer_summary": _summarize(answer),
        "implementation_focus": _implementation_focus(answer, app.kind),
        "mentor_reply_summary": _summarize(mentor_reply),
    }
    brief_path = app.root / MENTOR_BRIEF_FILENAME
    _write(brief_path, json.dumps(brief, indent=2, sort_keys=True) + "\n")
    _write(
        app.root / "README.md",
        (
            f"# {app.app_id} instant app\n\n"
            f"- mode: `{app.mode}`\n"
            f"- kind: `{app.kind}`\n"
            f"- entrypoint: `{app.entrypoint.name}`\n"
            f"- current_step: `{step}`\n"
            f"- framework_category: `{category}`\n"
            "\n"
            "## Current Intent\n\n"
            f"{_summarize(answer)}\n\n"
            "## Mentor Direction\n\n"
            f"{_summarize(mentor_reply)}\n"
        ),
    )
    if app.kind == "web":
        _write(app.root / "index.html", _render_web_index(app, brief))
        _write(app.root / "main.py", _render_web_main(app, brief))
    else:
        _write(app.root / "main.py", _render_shell_main(app, brief))
    return brief_path


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold())
    return normalized.strip("-")


def _scaffold_instant_app(root: Path, *, app_id: str, mode: str, kind: str) -> None:
    if kind == "web":
        _write(
            root / "index.html",
            (
                "<!doctype html>\n"
                "<html lang=\"en\">\n"
                "<head>\n"
                "  <meta charset=\"utf-8\">\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                f"  <title>{app_id}</title>\n"
                "  <style>\n"
                "    body { font-family: Georgia, serif; margin: 2rem; line-height: 1.5; }\n"
                "    main { max-width: 42rem; }\n"
                "  </style>\n"
                "</head>\n"
                "<body>\n"
                "  <main>\n"
                f"    <h1>{app_id}</h1>\n"
                "    <p>Instant web app scaffold for mentor-driven iteration.</p>\n"
                f"    <p>Mode: {mode}</p>\n"
                "  </main>\n"
                "</body>\n"
                "</html>\n"
            ),
        )
        _write(
            root / "main.py",
            (
                "from __future__ import annotations\n\n"
                "import os\n"
                "from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler\n"
                "from pathlib import Path\n\n"
                "ROOT = Path(__file__).resolve().parent\n"
                "PORT = int(os.environ.get(\"INSTANT_APP_PORT\", \"8765\"))\n\n"
                "if __name__ == \"__main__\":\n"
                "    server = ThreadingHTTPServer((\"127.0.0.1\", PORT), SimpleHTTPRequestHandler)\n"
                "    os.chdir(ROOT)\n"
                "    print(f\"Serving instant app at http://127.0.0.1:{PORT}\")\n"
                "    server.serve_forever()\n"
            ),
        )
        entrypoint = "main.py"
        description = "Local web app scaffold for fast mentor-guided iteration."
        url = f"http://127.0.0.1:{DEFAULT_WEB_PORT}"
    else:
        _write(
            root / "main.py",
            (
                "from __future__ import annotations\n\n"
                "def main() -> None:\n"
                "    print(\"instant shell app\")\n"
                "    print(\"type 'quit' to exit\")\n"
                "    while True:\n"
                "        raw = input(\"instant-app> \").strip()\n"
                "        if raw in {\"quit\", \"exit\"}:\n"
                "            return\n"
                "        if not raw:\n"
                "            continue\n"
                "        print(f\"echo: {raw}\")\n\n"
                "if __name__ == \"__main__\":\n"
                "    main()\n"
            ),
        )
        entrypoint = "main.py"
        description = "Local shell app scaffold for mentor-guided interactive workflows."
        url = None

    metadata = {
        "app_id": app_id,
        "mode": mode,
        "kind": kind,
        "title": f"{app_id} instant app",
        "description": description,
        "entrypoint": entrypoint,
        "url": url,
    }
    _write(root / APP_METADATA_FILENAME, json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    _write(
        root / "README.md",
        (
            f"# {app_id} instant app\n\n"
            f"- mode: `{mode}`\n"
            f"- kind: `{kind}`\n"
            f"- entrypoint: `{entrypoint}`\n"
            "\n"
            "This scaffold is intended to be extended by the mentor workflow.\n"
        ),
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_runtime_state(path: Path, runtime: InstantAppRuntime) -> None:
    payload = {
        "app_id": runtime.app_id,
        "status": runtime.status,
        "pid": runtime.pid,
        "port": runtime.port,
        "command": runtime.command,
        "log_path": str(runtime.log_path),
    }
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _wait_for_port(host: str, port: int, *, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"Instant app did not start listening on {host}:{port}")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _summarize(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split()).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _implementation_focus(answer: str, kind: str) -> str:
    answer_norm = answer.casefold()
    if kind == "web":
        if "review" in answer_norm or "approve" in answer_norm:
            return "guided review screen on localhost"
        if "form" in answer_norm or "input" in answer_norm:
            return "simple interactive input page on localhost"
        return "lightweight browser workflow on localhost"
    if "review" in answer_norm or "checklist" in answer_norm:
        return "guided checklist flow in the terminal"
    return "interactive shell workflow in the terminal"


def _render_web_index(app: InstantApp, brief: dict[str, object]) -> str:
    answer_summary = str(brief["answer_summary"])
    focus = str(brief["implementation_focus"])
    category = str(brief["category"])
    step = int(brief["step"])
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"  <title>{app.app_id}</title>\n"
        "  <style>\n"
        "    :root { color-scheme: light; }\n"
        "    body { font-family: Georgia, serif; margin: 0; background: linear-gradient(180deg, #f6f0e8, #ffffff); color: #1f1a17; }\n"
        "    main { max-width: 52rem; margin: 0 auto; padding: 3rem 1.5rem 4rem; }\n"
        "    .card { background: rgba(255,255,255,0.9); border: 1px solid #d6c6b6; border-radius: 16px; padding: 1.25rem; margin-top: 1rem; box-shadow: 0 8px 24px rgba(60,40,20,0.08); }\n"
        "    .eyebrow { text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.8rem; color: #8b5e34; }\n"
        "    h1 { font-size: 2.5rem; margin: 0.3rem 0 0.75rem; }\n"
        "    p { line-height: 1.6; }\n"
        "    code { background: #f2e7da; padding: 0.1rem 0.3rem; border-radius: 4px; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        f"    <div class=\"eyebrow\">Mentor-driven instant app · Step {step}</div>\n"
        f"    <h1>{app.app_id}</h1>\n"
        f"    <p>{focus}.</p>\n"
        "    <div class=\"card\">\n"
        f"      <strong>Framework focus</strong><p>{category}</p>\n"
        "    </div>\n"
        "    <div class=\"card\">\n"
        "      <strong>Current intent</strong>\n"
        f"      <p>{answer_summary}</p>\n"
        "    </div>\n"
        "    <div class=\"card\">\n"
        f"      <strong>Run</strong><p><code>python main.py</code> then open <code>{app.url or 'http://127.0.0.1:8765'}</code></p>\n"
        "    </div>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _render_web_main(app: InstantApp, brief: dict[str, object]) -> str:
    return (
        "from __future__ import annotations\n\n"
        "import os\n"
        "from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler\n"
        "from pathlib import Path\n\n"
        "ROOT = Path(__file__).resolve().parent\n"
        f"APP_ID = {app.app_id!r}\n"
        f"IMPLEMENTATION_FOCUS = {str(brief['implementation_focus'])!r}\n"
        "PORT = int(os.environ.get(\"INSTANT_APP_PORT\", \"8765\"))\n\n"
        "if __name__ == \"__main__\":\n"
        "    server = ThreadingHTTPServer((\"127.0.0.1\", PORT), SimpleHTTPRequestHandler)\n"
        "    os.chdir(ROOT)\n"
        "    print(f\"Serving {APP_ID} at http://127.0.0.1:{PORT}\")\n"
        "    print(f\"Focus: {IMPLEMENTATION_FOCUS}\")\n"
        "    server.serve_forever()\n"
    )


def _render_shell_main(app: InstantApp, brief: dict[str, object]) -> str:
    answer_summary = str(brief["answer_summary"])
    focus = str(brief["implementation_focus"])
    return (
        "from __future__ import annotations\n\n"
        f"APP_ID = {app.app_id!r}\n"
        f"IMPLEMENTATION_FOCUS = {focus!r}\n"
        f"ANSWER_SUMMARY = {answer_summary!r}\n\n"
        "def main() -> None:\n"
        "    print(f\"instant shell app: {APP_ID}\")\n"
        "    print(f\"focus: {IMPLEMENTATION_FOCUS}\")\n"
        "    print(f\"intent: {ANSWER_SUMMARY}\")\n"
        "    print(\"type 'quit' to exit\")\n"
        "    while True:\n"
        "        raw = input(\"instant-app> \").strip()\n"
        "        if raw in {\"quit\", \"exit\"}:\n"
        "            return\n"
        "        if not raw:\n"
        "            continue\n"
        "        print(f\"{APP_ID} captured: {raw}\")\n\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n"
    )
