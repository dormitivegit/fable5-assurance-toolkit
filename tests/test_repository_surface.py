"""Regression checks for the published informational dogfood surface."""

from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "fable5-dogfood.yml"


class RepositorySurfaceTests(unittest.TestCase):
    def test_dogfood_uses_current_distribution_and_subject_assertions(self) -> None:
        with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as handle:
            project_version = tomllib.load(handle)["project"]["version"]
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        pinned_versions = re.findall(
            r"fable5-assurance-toolkit==([0-9A-Za-z.+-]+)", workflow
        )
        self.assertTrue(pinned_versions)
        self.assertTrue(all(version == project_version for version in pinned_versions))
        self.assertNotIn("0.3.0rc5", workflow)

        for artifact in ("base-positive.json", "canary.json", "head-observation.json"):
            command_line = next(
                line for line in workflow.splitlines() if artifact in line and "corpus verify" in line
            )
            self.assertIn('--expected-root "$source_path"', command_line)


if __name__ == "__main__":
    unittest.main()
