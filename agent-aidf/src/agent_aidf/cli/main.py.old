from __future__ import annotations

import subprocess
from pathlib import Path

import click

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


@click.group()
@click.option("--project", default=None, envvar="AIDF_PROJECT_ROOT", help="Path to the creator project. Defaults to the current directory.")
@click.option("--repo", default=None, help="Path to a K-AIDF repository override. Defaults to .kaidf in the project, then AIDF_REPO_ROOT.")
@click.pass_context
def main(ctx: click.Context, project: str | None, repo: str | None) -> None:
    """🤖 kob: O agente definitivo de governança e ciclo de vida K-AIDF."""
    ctx.ensure_object(dict)
    ctx.obj["project"] = project
    ctx.obj["repo"] = repo


@main.command()
@click.option("--force", is_flag=True, help="Força a reinicialização.")
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    """Inicializa o repositório local .kaidf/ usando o spec padrão."""
    click.echo("🔄 Executando kob init via generator...")
    project_root = resolve_project_root(ctx.obj.get("project"))
    repo_root = init_project_repo(project_root, force=force)
    click.echo(f"Initialized {project_repo_root(project_root).name} at {repo_root}")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Mostra o status visual e a fase atual das 5 fases."""
    project_root = resolve_project_root(ctx.obj.get("project"))
    repo_root = resolve_runtime_repo_root(project_root, ctx.obj.get("repo"))
    project_status = read_project_status(project_root, repo_root)
    click.echo(f"project_root: {project_status.project_root}")
    click.echo(f"repo_root: {project_status.repo_root}")
    click.echo(f"has_kaidf: {'yes' if project_status.has_kaidf else 'no'}")
    click.echo(f"document_count: {project_status.document_count}")
    click.echo(f"pack_count: {project_status.pack_count}")
    click.echo(f"packs: {', '.join(project_status.packs) if project_status.packs else 'none'}")
    click.echo(f"instant_app_count: {project_status.instant_app_count}")
    click.echo(f"instant_apps: {', '.join(project_status.instant_apps) if project_status.instant_apps else 'none'}")
    click.echo(f"mentor_step_count: {project_status.mentor_step_count}")
    click.echo(f"mentor_pending_category: {project_status.mentor_pending_category or 'none'}")
    click.echo(f"mentor_current_app_id: {project_status.mentor_current_app_id or 'none'}")
    click.echo(f"mentor_current_app_url: {project_status.mentor_current_app_url or 'none'}")


@main.command()
@click.argument("answer", required=False)
@click.option("--status", "show_status", is_flag=True, help="Mostra o estado persistido do mentor.")
@click.option("--reset", is_flag=True, help="Reinicia o estado persistido do mentor.")
@click.pass_context
def mentor(ctx: click.Context, answer: str | None, show_status: bool, reset: bool) -> None:
    """Interage com o fluxo guiado do mentor K-AIDF (OLMo Local)."""
    project_root = resolve_project_root(ctx.obj.get("project"))
    repo_root = resolve_runtime_repo_root(project_root, ctx.obj.get("repo"))

    if reset:
        path = reset_mentor_state(repo_root)
        click.echo(f"Reset mentor workflow state at {path}")
        return
    if show_status:
        click.echo(mentor_status_text(repo_root))
        return
    if answer:
        click.echo(f"🧠 kob processando resposta: '{answer}'")
    else:
        click.echo("🤔 Exibindo próxima pergunta pendente do mentor...")
    turn = continue_mentor_workflow(repo_root, answer=answer)
    click.echo(turn.message)


def _ui_placeholder(port: int) -> None:
    click.echo(f"🌐 kob ui/serve ainda não está implementado (iniciaria o daemon na porta {port}).")


@main.command()
@click.option("--port", default=8501, help="Porta para o servidor web.")
def ui(port: int) -> None:
    """Inicia o daemon e abre a interface web local do mentor."""
    _ui_placeholder(port)


@main.command()
@click.option("--port", default=8501, help="Porta para o servidor web.")
def serve(port: int) -> None:
    """Alias de kob ui."""
    _ui_placeholder(port)


@main.command()
@click.pass_context
def shell(ctx: click.Context) -> None:
    """Inicia o terminal iterativo direto com o OLMo local."""
    project_root = resolve_project_root(ctx.obj.get("project"))
    repo_root = resolve_runtime_repo_root(project_root, ctx.obj.get("repo"))
    raise SystemExit(run_shell(repo_root))


def _run_compile(spec: str | None, out: str, force: bool) -> None:
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
    click.echo(f"✅ Generated: {out}")


@main.command()
@click.argument("spec", required=False)
@click.option("--out", required=True, help="Diretório de saída para o repositório gerado.")
@click.option("--force", is_flag=True, help="Permite escrever em um diretório não vazio.")
def compile(spec: str | None, out: str, force: bool) -> None:
    """Expõe o motor do gerador de scaffolds via spec YAML (kaidf-gen generate)."""
    _run_compile(spec, out, force)


@main.command()
@click.argument("spec", required=False)
@click.option("--out", required=True, help="Diretório de saída para o repositório gerado.")
@click.option("--force", is_flag=True, help="Permite escrever em um diretório não vazio.")
def gen(spec: str | None, out: str, force: bool) -> None:
    """Alias de kob compile."""
    _run_compile(spec, out, force)


if __name__ == "__main__":
    main()
