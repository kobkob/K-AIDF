from __future__ import annotations

import click

from ..mentor import continue_mentor_workflow, mentor_status_text, reset_mentor_state
from ..project import init_project_repo, project_repo_root, resolve_project_root, resolve_runtime_repo_root


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


@main.command()
@click.option("--port", default=8501, help="Porta para o servidor web.")
def ui(port: int) -> None:
    """Inicia o daemon e abre a interface web local do mentor."""
    click.echo(f"🌐 kob ui ainda não está implementado (iniciaria o daemon na porta {port}).")


if __name__ == "__main__":
    main()
