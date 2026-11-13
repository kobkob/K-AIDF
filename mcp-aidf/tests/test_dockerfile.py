"""The image contract that the deployment files rely on.

`mcp-aidf/Dockerfile` is checked by `scripts/check-image.sh` end to end (build, run, call the
maturity tools). These tests pin the parts a reader could change without noticing: the audit
engine is bundled, git is in the runtime, and the health check probes the public port.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from test_easypanel_template import copy_sources, dockerfile_of, instructions, load_template

DOCKERFILE = dockerfile_of(load_template()["services"][0]["data"])


class DockerfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = instructions(DOCKERFILE)
        self.text = " ".join(self.lines)

    def test_the_audit_engine_is_built_into_a_wheel_and_installed(self) -> None:
        self.assertIn("COPY agent-aidf /src/agent-aidf", self.text)
        self.assertIn("python -m build --wheel", self.text)
        self.assertIn("pip install --no-cache-dir /tmp/wheels/*.whl", self.text)

    def test_git_is_installed_without_recommends_and_trusts_the_mount(self) -> None:
        self.assertIn("apt-get install -y --no-install-recommends git", self.text)
        self.assertIn("rm -rf /var/lib/apt/lists/*", self.text)
        self.assertIn("safe.directory /workspace", self.text)

    def test_health_check_probes_the_protected_resource_metadata(self) -> None:
        health = [line for line in self.lines if line.startswith("HEALTHCHECK")]
        self.assertEqual(len(health), 1)
        self.assertIn("/.well-known/oauth-protected-resource", self.text)
        self.assertIn("status == 200", self.text)
        self.assertNotIn("curl", " ".join(health))

    def test_only_the_engine_and_the_server_files_enter_the_image(self) -> None:
        # Build-context sources (not --from stages): the engine for the builder, and the server
        # files for the runtime. Nothing else of the repository is copied in.
        self.assertEqual(
            sorted(copy_sources(DOCKERFILE)),
            sorted(
                [
                    "agent-aidf",
                    "mcp-aidf/requirements.txt",
                    "mcp-aidf/app.py",
                    "mcp-aidf/maturity.py",
                ]
            ),
        )

    def test_the_root_context_has_an_ignore_file(self) -> None:
        self.assertTrue((Path(DOCKERFILE).parents[1] / ".dockerignore").is_file())


if __name__ == "__main__":
    unittest.main()
