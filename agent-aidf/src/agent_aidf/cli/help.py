"""Per-command help for `kob`: what each command does, its flags and worked examples.

Every built-in command gets a description and an examples epilog, shown by `kob <command> -h`.
`kob help` lists the commands, and `kob help <command>` prints the same page as `-h`.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from dataclasses import dataclass

from ..i18n import _


@dataclass(frozen=True)
class Example:
    command: str
    note: str


@dataclass(frozen=True)
class CommandDoc:
    description: str
    examples: tuple[Example, ...]


# Keys are command paths: "audit", or "ext list" for a nested subcommand.
COMMAND_DOCS: dict[str, CommandDoc] = {
    "init": CommandDoc(
        description=(
            "Create the .kaidf/ directory in the project. It holds the K-AIDF scaffold: "
            "the README, docs/, policy/, specs/, data/manifests/ and the mentor state. "
            "The project is the current directory, or the one given with --project. "
            "An existing .kaidf/ is never overwritten unless --force is given."
        ),
        examples=(
            Example("kob init", "Create .kaidf/ in the current directory."),
            Example("kob init --force", "Recreate .kaidf/ from scratch, replacing it."),
            Example("kob --project ~/work/acme init", "Initialize another project folder."),
        ),
    ),
    "status": CommandDoc(
        description=(
            "Print where kob sees the project and its K-AIDF runtime: the project root, the "
            "repository root, whether .kaidf/ exists, how many packs are installed and how many "
            "mentor steps are recorded. Read-only."
        ),
        examples=(
            Example("kob status", "Show the status of the current project."),
            Example(
                "kob --repo ~/src/K-AIDF status",
                "Use a K-AIDF repository override as the runtime root.",
            ),
        ),
    ),
    "audit": CommandDoc(
        description=(
            "Score a K-AIDF repository against the KAIDF-AMM audit matrix. The audit reads the "
            "files and never writes or executes anything. Each failed check costs points and "
            "carries a severity: critical, high, medium or low (most to least severe).\n\n"
            "--severity LEVEL   show only the findings at LEVEL or above. The score does not "
            "change. --json always lists every check.\n"
            "--json             print the full result as JSON (schema for CI and dashboards).\n"
            "--fail-under N     exit with code 1 when the score is below N (0-100).\n"
            "--fail-on-critical exit with code 1 when any critical finding is present.\n\n"
            "Exit codes: 0 the audit ran and no gate failed; 1 a gate failed; 2 the path is "
            "not a valid directory or the arguments are wrong."
        ),
        examples=(
            Example("kob audit", "Score the current directory and print the report."),
            Example("kob audit ./acme-repo", "Score another repository."),
            Example("kob audit --severity high", "Show only critical and high findings."),
            Example("kob audit --json > audit.json", "Save the full result, with every check."),
            Example("kob audit --fail-under 80", "CI gate: fail when the score drops below 80."),
            Example("kob audit --fail-on-critical", "CI gate: fail on any critical finding."),
        ),
    ),
    "mentor": CommandDoc(
        description=(
            "Continue the persisted mentor workflow of the project. Without an answer, it shows "
            "the pending question; with an answer, it records it and moves to the next step. "
            "The state survives between runs. Requires `kob init` first."
        ),
        examples=(
            Example("kob mentor", "Show the pending mentor question."),
            Example('kob mentor "Two teams share one repository"', "Record an answer and advance."),
            Example("kob mentor --status", "Show progress through the mentor workflow."),
            Example("kob mentor --reset", "Clear the mentor state and start over."),
            Example("kob --model llama3.1:8b mentor", "Use a specific model for this run."),
        ),
    ),
    "shell": CommandDoc(
        description=(
            "Start an interactive shell backed by the local OLMo model (or the provider chosen "
            "with AIDF_CHAT_PROVIDER). Type 'help' inside the shell for its commands and 'quit' "
            "to leave."
        ),
        examples=(
            Example("kob shell", "Open the interactive shell in the current project."),
            Example("kob --model olmo2:13b shell", "Open it with a specific model."),
        ),
    ),
    "ui": CommandDoc(
        description=(
            "Launch the mentor web UI: the Maturity Model phases on one side and the mentor "
            "chat on the other. The server listens on 127.0.0.1 only. The port comes from "
            "--port, else AIDF_UI_PORT, else 8501. Stop it with Ctrl+C. `kob serve` is an "
            "alias for this command."
        ),
        examples=(
            Example("kob ui", "Start the web UI on http://127.0.0.1:8501."),
            Example("kob ui --port 9000", "Start it on another port."),
            Example("AIDF_UI_PORT=9000 kob ui", "Set the default port through the environment."),
            Example("kob serve --model llama3.1:8b", "Same as `kob ui`, with a model override."),
        ),
    ),
    "serve": CommandDoc(
        description=(
            "Alias for `kob ui`: launch the mentor web UI with the same options. See `kob help ui`."
        ),
        examples=(
            Example("kob serve", "Start the web UI on http://127.0.0.1:8501."),
            Example("kob serve --port 9000", "Start it on another port."),
        ),
    ),
    "compile": CommandDoc(
        description=(
            "Run the K-AIDF generator against a spec and write the scaffold to --out. Without a "
            "spec, it uses the generator's default specs/kaidf.default.yaml. Relative paths are "
            "resolved from the directory where you run kob. `kob gen` is an alias for this "
            "command. Existing files in --out are kept unless --force is given."
        ),
        examples=(
            Example("kob compile", "Generate the default scaffold into ./out."),
            Example("kob compile my-spec.yaml --out ./acme", "Generate from your own spec."),
            Example("kob compile --out ./acme --force", "Overwrite files already in ./acme."),
        ),
    ),
    "gen": CommandDoc(
        description=(
            "Alias for `kob compile`: run the K-AIDF generator against a spec and write the "
            "scaffold to --out. See `kob help compile`."
        ),
        examples=(
            Example("kob gen", "Generate the default scaffold into ./out."),
            Example("kob gen my-spec.yaml --out ./acme --force", "Generate and overwrite."),
        ),
    ),
    "ext": CommandDoc(
        description=(
            "Inspect and install extensions. Built-in commands come from the package; user "
            "extensions live in the extensions directory and load on the next kob start.\n\n"
            "Installing an extension uses the top-level flag -x, not a subcommand:\n"
            "  kob -x SOURCE [--sha256 HASH] [--yes]\n"
            "SOURCE is a local .tgz path or an https:// .tgz URL. kob shows a summary (name, "
            "author, version, origin, SHA-256) and asks for confirmation. --sha256 refuses the "
            "archive unless its digest matches. --yes approves without asking; it is required "
            "when there is no terminal to ask on. An extension runs Python code at startup, so "
            "install only archives from authors you trust."
        ),
        examples=(
            Example("kob ext list", "Show every extension, its load state and integrity."),
            Example("kob ext list --json", "Print the same inventory as JSON."),
            Example("kob -x ./my-extension.tgz", "Install a local archive after reviewing it."),
            Example(
                "kob -x https://example.org/ext.tgz --sha256 <hex-digest>",
                "Install a remote archive only if its digest matches.",
            ),
            Example("kob -x https://example.org/ext.tgz --yes", "Install without a prompt."),
        ),
    ),
    "ext list": CommandDoc(
        description=(
            "Print the extension inventory: each built-in and user extension with its version, "
            "author, origin and load state (loaded, failed, disabled or shadowed), its CLI "
            "arguments, handlers, subcommands and prompt interceptors. For user extensions, "
            "integrity is `verified`, `MODIFIED` (with the changed files), `no-record` or "
            "`unreadable`. Read-only."
        ),
        examples=(
            Example("kob ext list", "Show the inventory as text."),
            Example("kob ext list --json", "Show the inventory as JSON (schema_version 1)."),
        ),
    ),
    "appliance": CommandDoc(
        description=(
            "Bootstrap a K-AIDF appliance from a Jupyter notebook: a notebook can create the "
            "workspace on Google Colab, Kaggle or JupyterLab. `template` writes a starter "
            "notebook with install, init and audit cells. `init` reads the settings from the "
            "notebook cell tagged `kaidf-config` and writes .kaidf/appliance.yaml, without "
            "running any other cell. Notebooks with secret-looking keys are refused."
        ),
        examples=(
            Example("kob appliance template kaidf-start.ipynb", "Write the starter notebook."),
            Example(
                "kob appliance init --from-notebook kaidf-start.ipynb",
                "Configure .kaidf/ from the notebook's kaidf-config cell.",
            ),
        ),
    ),
    "appliance init": CommandDoc(
        description=(
            "Create .kaidf/ if it is missing and record the notebook's settings "
            "(project_name, model, audit_fail_under) in .kaidf/appliance.yaml, together with the "
            "notebook name, title and SHA-256. An existing .kaidf/ is kept unless --force is given."
        ),
        examples=(
            Example(
                "kob appliance init --from-notebook kaidf-start.ipynb",
                "Configure the project from the notebook.",
            ),
            Example(
                "kob appliance init --from-notebook kaidf-start.ipynb --force",
                "Recreate .kaidf/ from scratch first.",
            ),
        ),
    ),
    "appliance template": CommandDoc(
        description=(
            "Write a starter notebook for Google Colab, Kaggle and JupyterLab, with install, "
            "init and audit cells and a kaidf-config cell to edit. Refuses to overwrite FILE "
            "unless --force is given."
        ),
        examples=(
            Example("kob appliance template kaidf-start.ipynb", "Write the starter notebook."),
            Example("kob appliance template kaidf-start.ipynb --force", "Overwrite an old one."),
        ),
    ),
    "help": CommandDoc(
        description=(
            "Show the command list, or the full help of one command. `kob help <command>` "
            "prints the same page as `kob <command> -h`; nested commands take several words, "
            "as in `kob help ext list`."
        ),
        examples=(
            Example("kob help", "List the commands with a one-line summary each."),
            Example("kob help audit", "Full help for `kob audit`."),
            Example("kob help ext list", "Full help for a nested subcommand."),
        ),
    ),
}

MAIN_EXAMPLES: tuple[Example, ...] = (
    Example("kob", "Open the interactive terminal UI."),
    Example("kob help", "List every command."),
    Example("kob help audit", "Full help for one command."),
    Example("kob audit --fail-under 80", "Score the current repository and gate on the result."),
    Example("kob --project ~/work/acme status", "Run a command against another project."),
)


def command_description(name: str) -> str | None:
    doc = COMMAND_DOCS.get(name)
    return _(doc.description) if doc else None


def command_epilog(name: str) -> str | None:
    doc = COMMAND_DOCS.get(name)
    return _format_examples(doc.examples) if doc else None


def main_epilog() -> str:
    return _format_examples(MAIN_EXAMPLES)


def _format_examples(examples: tuple[Example, ...]) -> str:
    width = max(len(example.command) for example in examples)
    lines = [_("examples:")]
    lines += [f"  {example.command.ljust(width)}  {_(example.note)}" for example in examples]
    return "\n".join(lines)


def command_parser(
    subparsers: argparse._SubParsersAction,
    name: str,
    *,
    help: str,
    **kwargs,
) -> argparse.ArgumentParser:
    """Add a built-in subcommand with its description and examples attached."""
    return subparsers.add_parser(
        name.split()[-1],
        help=help,
        description=command_description(name),
        epilog=command_epilog(name),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        **kwargs,
    )


def _subparsers_of(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def command_overview(parser: argparse.ArgumentParser) -> str:
    """The one-line-per-command listing printed by `kob help`."""
    action = _subparsers_of(parser)
    lines = [_("kob commands (run `kob help <command>` for details):")]
    if action is None:
        return "\n".join(lines)
    # argparse keeps each subcommand's help line here; there is no public accessor for it.
    summaries = {choice.dest: choice.help or "" for choice in action._choices_actions}
    width = max((len(name) for name in action.choices), default=0)
    for name in action.choices:
        lines.append(f"  {name.ljust(width)}  {summaries.get(name, '')}")
    return "\n".join(lines)


def run_help(parser: argparse.ArgumentParser, topic: list[str]) -> int:
    """Implements `kob help [command ...]`. Returns the process exit code."""
    if not topic:
        print(command_overview(parser))
        return 0
    target = parser
    walked: list[str] = []
    for word in topic:
        action = _subparsers_of(target)
        choices = list(action.choices) if action is not None else []
        if word not in choices:
            where = f"kob {' '.join(walked)}".strip()
            print(_unknown_command_message(word, where, choices), file=sys.stderr)
            return 2
        target = action.choices[word]
        walked.append(word)
    print(target.format_help(), end="")
    return 0


def _unknown_command_message(word: str, where: str, choices: list[str]) -> str:
    message = _("kob help: unknown command '{word}' for '{where}'.").format(word=word, where=where)
    if not choices:
        return message + " " + _("It takes no subcommands.")
    suggestion = difflib.get_close_matches(word, choices, n=1)
    if suggestion:
        message += " " + _("Did you mean '{name}'?").format(name=suggestion[0])
    return message + " " + _("Available: {names}.").format(names=", ".join(choices))
