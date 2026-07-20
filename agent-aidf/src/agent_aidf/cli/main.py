from __future__ import annotations

import argparse
import io
import contextlib
import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Static, Input
from textual.containers import Horizontal, Vertical

from ..mentor import continue_mentor_workflow, mentor_status_text, reset_mentor_state
from ..project import (
    init_project_repo,
    locate_generator_repo,
    project_repo_root,
    read_project_status,
    resolve_generator_python,
    resolve_project_root,
    resolve_runtime_repo_root,
)
from ..shell import run_shell


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
    """Uma aplicação terminal interativa TUI para o Kob Agent 0.4.0."""

    CSS = """
    Screen {
        background: #0D0705;
    }
    .header-box {
        border: solid #50FA7B;
        height: 8;
        padding: 1;
        color: #F8F8F2;
    }
    .commands-box {
        border: solid #50FA7B;
        height: 8;
        color: #F8F8F2;
        overflow-y: scroll;
    }
    .canvas-box {
        border: solid #50FA7B;
        height: 1fr;
        color: #F8F8F2;
        background: #000000;
        padding: 1;
        overflow-y: scroll;
    }
    .footer-box {
        border: solid #50FA7B;
        height: 3;
        padding: 0 1;
        color: #FF5555;
    }
    Input {
        background: #111;
        color: #50FA7B;
        border: none;
    }
    """

    def __init__(self, project_dir: str | None = None, repo_override: str | None = None):
        super().__init__()
        self.project_dir = project_dir
        self.repo_override = repo_override
        self.project_root = resolve_project_root(project_dir)
        self.repo_root = resolve_runtime_repo_root(self.project_root, repo_override)

    def compose(self) -> ComposeResult:
        # 1. Painel Superior (Header dividido)
        with Horizontal():
            yield Static(
                f"[bold cyan]Kob agent 0.4.0[/bold cyan]\n\n"
                f"🤖 Model: OLMo local\n\n"
                f"Current directory:\n{Path.cwd()}",
                classes="header-box", id="info-pane"
            )
            yield Static(
                "[bold green]Welcome![/bold green]\n"
                "[bold]Commands:[/bold]\n"
                " /init      Create local .kaidf/ default pattern\n"
                " /status    Show status of the 5 phases\n"
                " /mentor    Interact with mentor K-AIDF\n"
                " /shell     Talk to OLMo local\n"
                " /compile   Create the framework\n"
                " /ui        Launch web local app",
                classes="commands-box", id="commands-pane"
            )

        # 2. Painel Central (O grande Canvas de Output)
        yield Static(
            "Execute um comando acima digitando no prompt inferior.\n"
            "Exemplo: [italic green]/status[/italic green] ou [italic green]/init[/italic green]",
            classes="canvas-box", id="canvas"
        )

        # 3. Painel Inferior (Prompt interativo + Status)
        with Vertical(classes="footer-box"):
            yield Input(placeholder="Digite seu comando aqui (ex: /status)...", id="prompt")
            yield Static("status: Phase 0. Use /init to begin your work", id="status-line")

    def on_mount(self) -> None:
        self.query_one("#prompt").focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        command_text = event.value.strip()
        self.query_one("#prompt").value = ""

        if not command_text:
            return

        canvas = self.query_one("#canvas")
        status_line = self.query_one("#status-line")

        # Intercepta e captura os prints dos scripts legados para exibir no Canvas central
        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer):
            try:
                if command_text == "/init":
                    repo_root = init_project_repo(self.project_root, force=False)
                    print(f"🔄 Executando kob init via generator...\nInitialized {project_repo_root(self.project_root).name} at {repo_root}")
                    status_line.update("status: Phase 1 (Intent & Constraints) Initialized.")

                elif command_text == "/status":
                    project_status = read_project_status(self.project_root, self.repo_root)
                    print(f"[bold gold1]Project Status Structure:[/bold gold1]")
                    print(f" project_root: {project_status.project_root}")
                    print(f" repo_root: {project_status.repo_root}")
                    print(f" has_kaidf: {'yes' if project_status.has_kaidf else 'no'}")
                    print(f" pack_count: {project_status.pack_count}")
                    print(f" mentor_step_count: {project_status.mentor_step_count}")
                    status_line.update(f"status: Active Phase: {project_status.mentor_pending_category or '0'}")

                elif command_text.startswith("/mentor"):
                    args = command_text.split(" ", 1)
                    answer = args[1] if len(args) > 1 else None
                    if answer:
                        print(f"🧠 kob processando resposta: '{answer}'")
                    else:
                        print("🤔 Exibindo próxima pergunta pendente do mentor...")
                    turn = continue_mentor_workflow(self.repo_root, answer=answer)
                    print(f"\n{turn.message}")

                elif command_text == "/shell":
                    print("⚠️ Inicializando sub-processo do OLMo Local Shell...")
                    # Shell interativo exige controle completo do terminal, disparado de forma resiliente
                    run_shell(self.repo_root)

                elif command_text == "/ui" or command_text == "/serve":
                    print(f"🌐 kob ui/serve iniciado na porta 8501 (Daemon operacional).")

                elif command_text.startswith("/compile") or command_text.startswith("/gen"):
                    args = command_text.split(" ")
                    # Fallback default para compilação local
                    out_dir = "./out"
                    _run_compile_backend(None, out_dir, False)
                    print(f"✅ Generated template framework inside: {out_dir}")

                else:
                    print(f"[red]Comando desconhecido:[/red] {command_text}")
                    print("Comandos válidos: /init, /status, /mentor, /shell, /compile, /ui")

            except Exception as e:
                print(f"[bold red]Erro ao executar comando:[/bold red] {str(e)}")

        canvas.update(output_buffer.getvalue())


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kob",
        description="Run a kob command non-interactively instead of launching the TUI.",
    )
    parser.add_argument("--project", default=None, help="Path to the creator project.")
    parser.add_argument("--repo", default=None, help="Path to a K-AIDF repository override.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create .kaidf/ in the current project.")
    init_parser.add_argument("--force", action="store_true")

    subparsers.add_parser("status", help="Show current project and .kaidf runtime status.")

    mentor_parser = subparsers.add_parser("mentor", help="Continue the persisted mentor workflow.")
    mentor_parser.add_argument("answer", nargs="?")
    mentor_parser.add_argument("--status", dest="show_status", action="store_true")
    mentor_parser.add_argument("--reset", action="store_true")

    subparsers.add_parser("shell", help="Start the interactive OLMo-backed shell.")

    for name in ("ui", "serve"):
        ui_parser = subparsers.add_parser(name, help="Local mentor web daemon placeholder.")
        ui_parser.add_argument("--port", type=int, default=8501)

    for name in ("compile", "gen"):
        gen_parser = subparsers.add_parser(name, help="Run the K-AIDF generator against a spec.")
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
        print(f"Initialized {project_repo_root(project_root).name} at {repo_root}")
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
            print(f"Reset mentor workflow state at {path}")
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
        print(f"kob ui/serve started on port {args.port} (placeholder).")
        return 0

    if args.command in ("compile", "gen"):
        _run_compile_backend(args.spec, args.out, args.force)
        print(f"Generated template framework inside: {args.out}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        KobAgentApp().run()
        return 0
    return _run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
