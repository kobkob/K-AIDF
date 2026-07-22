from __future__ import annotations

import argparse
import contextlib
import io
import os
import subprocess
import sys
from functools import partial
from importlib import metadata
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Static
from werkzeug.serving import BaseWSGIServer

from ..controller import OpenAIResponsesController, build_controller
from ..i18n import _
from ..maturity import phase_progress
from ..mentor import continue_mentor_workflow, mentor_status_text, reset_mentor_state
from ..project import (
    ProjectStatus,
    init_project_repo,
    locate_generator_repo,
    project_repo_root,
    read_project_status,
    resolve_generator_python,
    resolve_project_root,
    resolve_runtime_repo_root,
)
from ..shell import run_shell
from ..webui import run_webui

PACKAGE_DISTRIBUTION = "agent-aidf"
DEFAULT_LOCAL_MODEL = "OLMo local"
DEFAULT_UI_PORT = 8501
MAX_LOG_LINES = 400

# Source: top-level README.md "## Logo" section.
LOGO = (
    " ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄\n"
    " █  ▄▄▄    ▄▄▄  █\n"
    " █  █ █    █ █  █\n"
    " █  ▀▀▀    ▀▀▀  █\n"
    " █              █\n"
    " █   █▀▀▀▀▀▀█   █\n"
    " █   ▀▀▀▀▀▀▀▀   █\n"
    " ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀"
)

# (command, description) pairs, kept alphabetical by command name.
COMMAND_HELP = (
    ("/compile", lambda: _("Run the K-AIDF generator and write the scaffolded framework.")),
    ("/exit", lambda: _("Stop the web UI if running, then quit kob.")),
    ("/gen", lambda: _("Alias for /compile.")),
    ("/init", lambda: _("Create the local .kaidf/ directory using the default pattern.")),
    ("/mentor", lambda: _("Show the pending mentor question, or record an answer.")),
    ("/serve", lambda: _("Alias for /ui.")),
    ("/shell", lambda: _("Hand off the terminal to the interactive OLMo-backed shell.")),
    ("/status", lambda: _("Show the status of the 5 K-AIDF delivery phases.")),
    (
        "/ui",
        lambda: _("Launch the mentor web UI (Maturity Model phases + mentor chat)."),
    ),
)


def package_version() -> str:
    try:
        return metadata.version(PACKAGE_DISTRIBUTION)
    except metadata.PackageNotFoundError:
        return _("unknown")


def active_model_label() -> str:
    """The model actually driving /mentor and /shell, resolved like build_controller() does."""
    controller = build_controller()
    if isinstance(controller, OpenAIResponsesController):
        return controller.model
    return os.environ.get("AIDF_MODEL", DEFAULT_LOCAL_MODEL)


def ui_port() -> int:
    return int(os.environ.get("AIDF_UI_PORT", str(DEFAULT_UI_PORT)))


def _run_compile_backend(spec: str | None, out: str, force: bool) -> None:
    generator_repo = locate_generator_repo()
    generator_python = resolve_generator_python(generator_repo)
    spec_path = Path(spec).expanduser() if spec else generator_repo / "specs/kaidf.default.yaml"
    command = [
        str(generator_python),
        "-m",
        "kaidf_gen.cli",
        "generate",
        str(spec_path),
        "--out",
        str(Path(out).expanduser()),
    ]
    if force:
        command.append("--force")
    subprocess.run(command, cwd=generator_repo, check=True)


class KobAgentApp(App):
    """Interactive Textual TUI for the kob agent."""

    CSS = """
    Screen {
        background: #0D0705;
    }
    #header-box {
        border: solid #50FA7B;
        height: auto;
        color: #F8F8F2;
    }
    #info-pane {
        width: 1fr;
        height: auto;
        padding: 1;
    }
    #logo-row {
        height: auto;
    }
    #logo {
        width: auto;
        color: #50FA7B;
        padding-right: 2;
    }
    #model-label {
        color: #F8F8F2;
        padding-top: 1;
    }
    #directory-line {
        color: #F8F8F2;
        padding-top: 1;
    }
    #commands-pane {
        width: 1fr;
        height: auto;
        padding: 1;
        border-left: solid #50FA7B;
        color: #F8F8F2;
    }
    .canvas-box {
        border: solid #50FA7B;
        height: 1fr;
    }
    #canvas-status {
        height: 1;
        padding: 0 1;
        color: #FFB86C;
        text-style: bold;
    }
    #canvas-scroll {
        height: 1fr;
        background: #000000;
    }
    #canvas {
        padding: 0 1;
        color: #F8F8F2;
        background: #000000;
    }
    .footer-box {
        border: solid #50FA7B;
        height: 4;
        padding: 0 1;
        color: #FF5555;
    }
    Input {
        background: #111;
        color: #50FA7B;
        border: none;
        height: 1;
    }
    """

    def __init__(self, project_dir: str | None = None, repo_override: str | None = None):
        super().__init__()
        self.project_dir = project_dir
        self.repo_override = repo_override
        self.project_root = resolve_project_root(project_dir)
        self.repo_root = resolve_runtime_repo_root(self.project_root, repo_override)
        self._web_server: BaseWSGIServer | None = None
        self._web_url: str | None = None
        self._log_lines: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-box"):
            with Vertical(id="info-pane"):
                with Horizontal(id="logo-row"):
                    yield Static(LOGO, id="logo")
                    yield Static("", id="model-label")
                yield Static("", id="directory-line")
            with Vertical(id="commands-pane"):
                yield Static(self._commands_text(), id="commands-list")

        with Vertical(classes="canvas-box"):
            yield Static("", id="canvas-status")
            with VerticalScroll(id="canvas-scroll"):
                yield Static(self._canvas_placeholder_text(), id="canvas")

        with Vertical(classes="footer-box"):
            yield Input(placeholder=_("Type a command here (e.g. /status)..."), id="prompt")
            yield Static("", id="status-line")

    def on_mount(self) -> None:
        self.query_one("#header-box").border_title = self._header_title_text()
        model_line = _("Model: {model}").format(model=active_model_label())
        self.query_one("#model-label").update(model_line)
        directory_line = _("Current directory:\n{path}").format(path=Path.cwd())
        self.query_one("#directory-line").update(directory_line)
        self.query_one("#prompt").focus()
        self._refresh_status_panels()

    def on_unmount(self) -> None:
        # Guarantee the background web server dies with the app, however it quits
        # (typed /exit, Ctrl+C, Ctrl+Q, or the terminal window closing).
        self._stop_webui()

    def _header_title_text(self) -> str:
        return _("Kob agent {version} - model {model}").format(
            version=package_version(), model=active_model_label()
        )

    def _commands_text(self) -> str:
        lines = [_("Welcome!"), _("Commands:")]
        for name, describe in COMMAND_HELP:
            lines.append(f" {name:<10}{describe()}")
        return "\n".join(lines)

    def _canvas_placeholder_text(self) -> str:
        return _(
            "Run a command above by typing it into the prompt below.\n"
            "Example: [italic green]/status[/italic green] or [italic green]/init[/italic green]"
        )

    def _canvas_status_text(self, status: ProjectStatus) -> str:
        current, total = phase_progress(status)
        return _("Current Status - K-AIDF Phase {current}/{total}").format(
            current=current, total=total
        )

    def _footer_status_text(self, status: ProjectStatus) -> str:
        current, total = phase_progress(status)
        if not status.has_kaidf:
            return _("status: Phase 0. Use /init to begin your work")
        if current == 0:
            return _("status: Phase 0/{total}. Use /mentor to begin your work").format(total=total)
        if status.mentor_pending_category:
            return _("status: Phase {current}/{total}. Pending category: {category}").format(
                current=current, total=total, category=status.mentor_pending_category
            )
        return _("status: Phase {current}/{total}.").format(current=current, total=total)

    def _refresh_status_panels(self) -> None:
        status = read_project_status(self.project_root, self.repo_root)
        self.query_one("#canvas-status").update(self._canvas_status_text(status))
        self.query_one("#status-line").update(self._footer_status_text(status))

    def _log(self, text: str) -> None:
        """Append a block of output to the scrolling canvas. Must run on the Textual thread."""
        if not text:
            return
        self._log_lines.append(text)
        del self._log_lines[:-MAX_LOG_LINES]
        self.query_one("#canvas", Static).update("\n".join(self._log_lines))
        self.query_one("#canvas-scroll", VerticalScroll).scroll_end(animate=False)

    def _log_from_thread(self, text: str) -> None:
        """log_sink for run_webui(): called from the web server's background thread."""
        self.call_from_thread(self._log, text)

    def _set_web_server(self, server: BaseWSGIServer) -> None:
        self._web_server = server

    def _run_webui_worker(self, port: int) -> None:
        try:
            run_webui(
                self.project_root,
                self.repo_root,
                port=port,
                log_sink=self._log_from_thread,
                on_server_ready=self._set_web_server,
            )
        finally:
            self._web_server = None
            self._web_url = None
            self.call_from_thread(self._refresh_status_panels)

    def _start_webui(self) -> str:
        if self._web_server is not None:
            return _("Web UI is already running at {url}").format(url=self._web_url)
        port = ui_port()
        self._web_url = f"http://127.0.0.1:{port}"
        self.run_worker(partial(self._run_webui_worker, port), thread=True, group="webui")
        return _("Starting the web UI at {url} ...").format(url=self._web_url)

    def _stop_webui(self) -> str | None:
        if self._web_server is None:
            return None
        self._web_server.shutdown()
        self._web_server = None
        self._web_url = None
        return _("Web UI stopped.")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        command_text = event.value.strip()
        self.query_one("#prompt").value = ""

        if not command_text:
            return

        should_exit = False

        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer):
            try:
                if command_text == "/init":
                    repo_root = init_project_repo(self.project_root, force=False)
                    name = project_repo_root(self.project_root).name
                    message = _("Running /init via the generator...\nInitialized {name} at {path}")
                    print(message.format(name=name, path=repo_root))
                    self._refresh_status_panels()

                elif command_text == "/status":
                    status = read_project_status(self.project_root, self.repo_root)
                    title = _("Project Status")
                    has_kaidf = _("yes") if status.has_kaidf else _("no")
                    print(f"[bold gold1]{title}[/bold gold1]")
                    print(f" project_root: {status.project_root}")
                    print(f" repo_root: {status.repo_root}")
                    print(f" has_kaidf: {has_kaidf}")
                    print(f" pack_count: {status.pack_count}")
                    print(f" mentor_step_count: {status.mentor_step_count}")
                    self._refresh_status_panels()

                elif command_text.startswith("/mentor"):
                    parts = command_text.split(" ", 1)
                    answer = parts[1] if len(parts) > 1 else None
                    if answer:
                        print(_("Processing mentor answer: '{answer}'").format(answer=answer))
                    else:
                        print(_("Showing the pending mentor question..."))
                    turn = continue_mentor_workflow(self.repo_root, answer=answer)
                    print(f"\n{turn.message}")
                    self._refresh_status_panels()

                elif command_text == "/shell":
                    print(_("Starting the interactive OLMo-backed shell..."))
                    run_shell(self.repo_root)

                elif command_text in ("/ui", "/serve"):
                    print(self._start_webui())

                elif command_text.startswith("/compile") or command_text.startswith("/gen"):
                    out_dir = "./out"
                    _run_compile_backend(None, out_dir, False)
                    print(_("Generated template framework inside: {out}").format(out=out_dir))

                elif command_text == "/exit":
                    stopped_message = self._stop_webui()
                    if stopped_message:
                        print(stopped_message)
                    print(_("Goodbye!"))
                    should_exit = True

                else:
                    unknown_label = _("Unknown command:")
                    print(f"[red]{unknown_label}[/red] {command_text}")
                    commands = ", ".join(name for name, _d in COMMAND_HELP)
                    print(_("Valid commands: {commands}").format(commands=commands))

            except Exception as e:
                error_label = _("Error running command:")
                print(f"[bold red]{error_label}[/bold red] {str(e)}")

        self._log(output_buffer.getvalue())
        if should_exit:
            self.exit()


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kob",
        description=_("Run a kob command non-interactively instead of launching the TUI."),
    )
    parser.add_argument("--project", default=None, help=_("Path to the creator project."))
    parser.add_argument("--repo", default=None, help=_("Path to a K-AIDF repository override."))
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help=_("Create .kaidf/ in the current project."))
    init_parser.add_argument("--force", action="store_true")

    subparsers.add_parser("status", help=_("Show current project and .kaidf runtime status."))

    mentor_help = _("Continue the persisted mentor workflow.")
    mentor_parser = subparsers.add_parser("mentor", help=mentor_help)
    mentor_parser.add_argument("answer", nargs="?")
    mentor_parser.add_argument("--status", dest="show_status", action="store_true")
    mentor_parser.add_argument("--reset", action="store_true")

    subparsers.add_parser("shell", help=_("Start the interactive OLMo-backed shell."))

    ui_help = _("Launch the mentor web UI (Maturity Model phases + mentor chat).")
    for name in ("ui", "serve"):
        ui_parser = subparsers.add_parser(name, help=ui_help)
        ui_parser.add_argument("--port", type=int, default=ui_port())

    for name in ("compile", "gen"):
        gen_parser = subparsers.add_parser(name, help=_("Run the K-AIDF generator against a spec."))
        gen_parser.add_argument("spec", nargs="?")
        gen_parser.add_argument("--out", default="./out")
        gen_parser.add_argument("--force", action="store_true")

    return parser


def _run_cli(argv: list[str]) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    project_root = resolve_project_root(args.project)

    if args.command == "init":
        repo_root = init_project_repo(project_root, force=args.force)
        name = project_repo_root(project_root).name
        print(_("Initialized {name} at {path}").format(name=name, path=repo_root))
        return 0

    repo_root = resolve_runtime_repo_root(project_root, args.repo)

    if args.command == "status":
        status = read_project_status(project_root, repo_root)
        print(f"project_root: {status.project_root}")
        print(f"repo_root: {status.repo_root}")
        print(f"has_kaidf: {'yes' if status.has_kaidf else 'no'}")
        print(f"pack_count: {status.pack_count}")
        print(f"mentor_step_count: {status.mentor_step_count}")
        return 0

    if args.command == "mentor":
        if args.reset:
            path = reset_mentor_state(repo_root)
            print(_("Reset mentor workflow state at {path}").format(path=path))
            return 0
        if args.show_status:
            print(mentor_status_text(repo_root))
            return 0
        turn = continue_mentor_workflow(repo_root, answer=args.answer)
        print(turn.message)
        return 0

    if args.command == "shell":
        return run_shell(repo_root)

    if args.command in ("ui", "serve"):
        try:
            run_webui(project_root, repo_root, port=args.port, log_sink=print)
        except KeyboardInterrupt:
            pass
        return 0

    if args.command in ("compile", "gen"):
        _run_compile_backend(args.spec, args.out, args.force)
        print(_("Generated template framework inside: {out}").format(out=args.out))
        return 0

    parser.error(_("Unknown command: {command}").format(command=args.command))
    return 2


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        KobAgentApp().run()
        return 0
    return _run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
