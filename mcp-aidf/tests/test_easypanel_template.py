"""The EasyPanel template must describe the server this repository builds.

`deploy/easypanel/easypanel.json` is static JSON pasted into EasyPanel ("Create From Schema").
Nothing in the panel checks it against `mcp-aidf`, so these tests do: the build path and
Dockerfile exist, the proxied port is the one the container listens on, every variable is one the
image reads, and the volume is where `AIDF_REPO_ROOT` points. The sources of truth are
`mcp-aidf/Dockerfile` and `mcp-aidf/app.py`; the template and the guide follow them.
"""

from __future__ import annotations

import copy
import json
import os
import posixpath
import re
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = WORKSPACE_ROOT / "deploy" / "easypanel" / "easypanel.json"
GUIDE_PATH = WORKSPACE_ROOT / "docs" / "06-deploy" / "easypanel.md"
APP_SOURCE = WORKSPACE_ROOT / "mcp-aidf" / "app.py"

# Keys of an App service in the EasyPanel schema (easypanel-io/templates utils/schema.ts and the
# panel's createFromSchema API). An unknown key is a typo the panel would reject or drop.
APP_DATA_KEYS = {
    "serviceName",
    "source",
    "build",
    "env",
    "basicAuth",
    "deploy",
    "domains",
    "mounts",
    "ports",
    "resources",
    "maintenance",
    "scripts",
    "dotEnvPath",
}
NAME_RULE = re.compile(r"^[a-z0-9-_]+$")
REQUIRED_ENV = ("PORT", "MCP_PUBLIC_URL", "MCP_BEARER_TOKEN", "AIDF_REPO_ROOT")
# Read by the container's start command (Dockerfile CMD), not by app.py.
CONTAINER_ENV = {"PORT"}


def load_template() -> dict:
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def parse_env(env: str) -> dict[str, str]:
    """EasyPanel stores the environment as one string of KEY=VALUE lines."""
    pairs: dict[str, str] = {}
    for line in env.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError(f"not a KEY=VALUE line: {line!r}")
        pairs[key.strip()] = value
    return pairs


def variables_read_by_app() -> set[str]:
    """Names app.py passes to os.environ.get, as literals or through a module constant."""
    source = APP_SOURCE.read_text(encoding="utf-8")
    constants = dict(re.findall(r'^([A-Z_]+) = "([A-Z_]+)"$', source, flags=re.MULTILINE))
    names = set(re.findall(r'os\.environ\.get\(\s*"([A-Z_]+)"', source))
    for constant in re.findall(r"os\.environ\.get\(\s*([A-Z_]+)\s*,", source):
        if constant in constants:
            names.add(constants[constant])
    return names


def build_context_of(data: dict) -> Path:
    """EasyPanel resolves the Dockerfile from the build path, which is also the build context."""
    return WORKSPACE_ROOT / data["source"]["path"].lstrip("/")


def dockerfile_of(data: dict) -> Path:
    return build_context_of(data) / data["build"].get("file", "Dockerfile")


def instructions(dockerfile: Path) -> list[str]:
    """Dockerfile instructions, with backslash-continued lines joined."""
    text = dockerfile.read_text(encoding="utf-8")
    return [line.strip() for line in re.sub(r"\\\n", " ", text).splitlines()]


def copy_sources(dockerfile: Path) -> list[str]:
    """Paths a Dockerfile copies from its build context (not from a stage or a URL)."""
    sources: list[str] = []
    for line in instructions(dockerfile):
        words = line.split()
        if not words or words[0] not in {"COPY", "ADD"}:
            continue
        if any(word.startswith("--from=") for word in words):
            continue
        arguments = [word for word in words[1:] if not word.startswith("--")]
        sources.extend(source for source in arguments[:-1] if "://" not in source)
    return sources


def in_build_context(context: Path, source: str) -> bool:
    """Docker resolves a source inside the context: a leading `/` or `../` cannot leave it."""
    relative = posixpath.normpath("/" + source).lstrip("/")
    if any(char in relative for char in "*?["):
        return any(context.glob(relative))
    return (context / relative).exists()


def start_command(dockerfile: Path) -> str:
    commands = [line for line in instructions(dockerfile) if line.startswith("CMD ")]
    return commands[-1] if commands else ""


def problems(template: dict) -> list[str]:
    """Everything that makes the template disagree with the server it deploys."""
    found: list[str] = []
    services = template.get("services", [])
    if len(services) != 1 or services[0].get("type") != "app":
        return ["the template must define exactly one service of type app"]
    data = services[0]["data"]

    unknown = set(data) - APP_DATA_KEYS
    if unknown:
        found.append(f"unknown App service keys: {sorted(unknown)}")
    if not NAME_RULE.match(data.get("serviceName", "")):
        found.append("serviceName must match ^[a-z0-9-_]+$")

    source = data.get("source", {})
    if source.get("type") != "github" or not all(source.get(k) for k in ("owner", "repo", "ref")):
        found.append("source must be a github source with owner, repo and ref")
    if not str(source.get("path", "")).startswith("/"):
        found.append("source.path must start with /")
    if source.get("autoDeploy") is not False:
        found.append("autoDeploy must be false: a webhook needs a GitHub token in the panel")
    if data.get("build", {}).get("type") != "dockerfile":
        found.append("build.type must be dockerfile")
    if found:
        return found

    dockerfile = dockerfile_of(data)
    if not dockerfile.is_file():
        return [f"no Dockerfile at {dockerfile.relative_to(WORKSPACE_ROOT)}"]
    for copied in copy_sources(dockerfile):
        if not in_build_context(build_context_of(data), copied):
            found.append(f"the Dockerfile copies {copied}, which is outside the build path")

    env = parse_env(data.get("env", ""))
    for name in REQUIRED_ENV:
        if name not in env:
            found.append(f"env is missing {name}")
    unread = set(env) - variables_read_by_app() - CONTAINER_ENV
    if unread:
        found.append(f"env sets variables the image never reads: {sorted(unread)}")
    if env.get("MCP_BEARER_TOKEN"):
        found.append("MCP_BEARER_TOKEN must ship empty: a published value is a known token")
    if not data.get("env", "").endswith("\nMCP_BEARER_TOKEN="):
        found.append("MCP_BEARER_TOKEN= must end env: the guide says to paste the token there")
    public_url = env.get("MCP_PUBLIC_URL", "")
    if public_url != "https://$(PRIMARY_DOMAIN)":
        found.append("MCP_PUBLIC_URL must be the bare origin https://$(PRIMARY_DOMAIN)")

    port = env.get("PORT", "")
    if "${PORT" not in start_command(dockerfile):
        found.append("the Dockerfile start command does not read PORT")
    domains = data.get("domains", [])
    if len(domains) != 1 or domains[0].get("host") != "$(EASYPANEL_DOMAIN)":
        found.append("one domain on $(EASYPANEL_DOMAIN) is expected")
    elif not port.isdigit() or domains[0].get("port") != int(port):
        found.append("the domain port must equal PORT")

    volumes = [mount for mount in data.get("mounts", []) if mount.get("type") == "volume"]
    if not any(mount.get("mountPath") == env.get("AIDF_REPO_ROOT") for mount in volumes):
        found.append("no volume is mounted at AIDF_REPO_ROOT")
    if any(not NAME_RULE.match(mount.get("name", "")) for mount in volumes):
        found.append("volume names must match ^[a-z0-9-_]+$")
    return found


class EasyPanelTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = load_template()
        self.data = self.template["services"][0]["data"]

    def test_template_agrees_with_the_dockerfile_and_the_server(self) -> None:
        self.assertEqual(problems(self.template), [])

    def test_app_reads_the_variables_the_template_relies_on(self) -> None:
        read = variables_read_by_app()

        for name in ("MCP_PUBLIC_URL", "MCP_BEARER_TOKEN", "AIDF_REPO_ROOT", "MCP_TOKEN_SCOPES"):
            self.assertIn(name, read)

    def test_dockerfile_keeps_7777_as_the_default_port(self) -> None:
        # mcp-aidf/docker-compose.yml publishes 7777:7777 and passes no PORT.
        self.assertIn("${PORT:-7777}", start_command(dockerfile_of(self.data)))

    def test_guide_documents_every_variable_with_the_template_value(self) -> None:
        guide = GUIDE_PATH.read_text(encoding="utf-8")

        for name, value in parse_env(self.data["env"]).items():
            self.assertIn(f"`{name}`", guide)
            if value:
                row = rf"(?m)^\| `{re.escape(name)}` \|.*\| `{re.escape(value)}` \|$"
                self.assertRegex(guide, row)

    def test_checks_would_catch_a_drifted_template(self) -> None:
        # The two build-path edits are relative to the current layout, so they keep meaning
        # "the wrong context" if the Dockerfile later moves to a repository-root context.
        current = self.data["source"]["path"]
        other = "/" if current.strip("/") else "/mcp-aidf"
        real_dockerfile = dockerfile_of(self.data)

        def point_at_a_path_without_the_dockerfile(data: dict) -> None:
            data["source"]["path"] = other

        def build_the_dockerfile_from_another_context(data: dict) -> None:
            data["source"]["path"] = other
            data["build"]["file"] = os.path.relpath(
                real_dockerfile, WORKSPACE_ROOT / other.lstrip("/")
            ).replace(os.sep, "/")

        def proxy_another_port(data: dict) -> None:
            data["domains"][0]["port"] += 1

        def publish_a_token(data: dict) -> None:
            data["env"] = data["env"].replace("MCP_BEARER_TOKEN=", "MCP_BEARER_TOKEN=example")

        def move_the_token_line(data: dict) -> None:
            data["env"] = "MCP_BEARER_TOKEN=\n" + data["env"].removesuffix("\nMCP_BEARER_TOKEN=")

        def add_unread_variable(data: dict) -> None:
            data["env"] = "SERVER_PORT=8000\n" + data["env"]

        def add_a_path_to_the_public_url(data: dict) -> None:
            data["env"] = data["env"].replace("$(PRIMARY_DOMAIN)", "$(PRIMARY_DOMAIN)/mcp")

        def move_the_volume(data: dict) -> None:
            data["mounts"][0]["mountPath"] = "/data"

        def add_an_unknown_key(data: dict) -> None:
            data["volumes"] = []

        expected = (
            (point_at_a_path_without_the_dockerfile, "no Dockerfile at"),
            (build_the_dockerfile_from_another_context, "outside the build path"),
            (proxy_another_port, "the domain port must equal PORT"),
            (publish_a_token, "must ship empty"),
            (move_the_token_line, "must end env"),
            (add_unread_variable, "variables the image never reads"),
            (add_a_path_to_the_public_url, "MCP_PUBLIC_URL must be the bare origin"),
            (move_the_volume, "no volume is mounted at AIDF_REPO_ROOT"),
            (add_an_unknown_key, "unknown App service keys"),
        )
        for edit, message in expected:
            with self.subTest(edit.__name__):
                template = copy.deepcopy(self.template)
                edit(template["services"][0]["data"])
                self.assertTrue(any(message in problem for problem in problems(template)))


if __name__ == "__main__":
    unittest.main()
