"""Regression checks for the published informational dogfood surface."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import tomllib
import unittest

from software_evidence_controls.cli import build_parser
from software_evidence_controls.version import PRODUCT_VERSION, PYTHON_DISTRIBUTION_VERSION


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = (
    REPOSITORY_ROOT
    / ".github"
    / "workflows"
    / "software-evidence-controls-dogfood.yml"
)


def profile_command_paths(
    parser: argparse.ArgumentParser,
    prefix: tuple[str, ...] = (),
) -> set[str]:
    paths = set()
    if any("--profile" in action.option_strings for action in parser._actions):
        paths.add(" ".join(prefix))
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                paths.update(profile_command_paths(child, (*prefix, name)))
    return paths


class RepositorySurfaceTests(unittest.TestCase):
    def test_dogfood_uses_current_distribution_and_subject_assertions(self) -> None:
        with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as handle:
            project_version = tomllib.load(handle)["project"]["version"]
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        pinned_versions = re.findall(
            r"software-evidence-controls==([0-9A-Za-z.+-]+)", workflow
        )
        self.assertTrue(pinned_versions)
        self.assertTrue(all(version == project_version for version in pinned_versions))
        self.assertNotIn("0.3.0rc5", workflow)

        for artifact in ("base-positive.json", "canary.json", "head-observation.json"):
            command_line = next(
                line for line in workflow.splitlines() if artifact in line and "corpus verify" in line
            )
            self.assertIn('--expected-root "$source_path"', command_line)

    def test_repository_version_copies_match_runtime_constants(self) -> None:
        with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as handle:
            project_version = tomllib.load(handle)["project"]["version"]
        product_version = (REPOSITORY_ROOT / "VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(PYTHON_DISTRIBUTION_VERSION, project_version)
        self.assertEqual(PRODUCT_VERSION, product_version)

    def test_readme_scopes_strict_profile_to_commands_that_expose_it(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        profile_paragraph = next(
            (
                paragraph
                for paragraph in readme.split("\n\n")
                if "`--profile strict`" in paragraph and "`corpus verify`" in paragraph
            ),
            "",
        )
        self.assertTrue(profile_paragraph, "README must document the corpus profile boundary")
        self.assertIn("not available", profile_paragraph)

        documented_commands = {
            token
            for token in re.findall(r"`([^`]+)`", profile_paragraph)
            if re.fullmatch(r"[a-z]+", token)
        }
        runtime_commands = profile_command_paths(build_parser())

        self.assertEqual(runtime_commands, documented_commands)
        self.assertNotIn("corpus verify", runtime_commands)


if __name__ == "__main__":
    unittest.main()
