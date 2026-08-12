import os
import subprocess
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "examples" / "agent-change-assurance" / "run.sh"


class AgentChangeAssuranceExampleTests(unittest.TestCase):
    def test_walkthrough_exercises_expected_contracts(self):
        self.assertTrue(
            os.access(SCRIPT, os.X_OK),
            "documented entry point must be executable",
        )
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=REPOSITORY,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        for expected in (
            "DEMO_RESULT=PASS",
            "MODULES_EXERCISED=PM-01,PM-04,PM-05",
            "RISK_TIER=T1",
            "CLASSIFICATION_IS_AUTHORIZATION=false",
            "BASELINE_VERIFY=PASS",
            "EXPECTED_NEGATIVE_EXIT=4",
            "EXPECTED_NEGATIVE_FINDING=CI03_SOURCE_CHANGED",
            "POST_CHANGE_VERIFY=PASS",
            "HANDOFF_EVIDENCE_REFERENCE=RESOLVED",
            "HANDOFF_MODE=OBSERVATION_AND_STRUCTURAL_LINT_ONLY",
            "RECEIVER_READY=NOT_MACHINE_DETERMINED",
            "HUMAN_REVIEW_REQUIRED=YES",
            "RUNTIME_NETWORK_DEPENDENCY=NONE",
            "EXTERNAL_AI_DEPENDENCY=NONE",
            "TEMP_WORKSPACE_CLEANUP=automatic",
            '"code": "CI03_SOURCE_CHANGED"',
            '"exit_code": 4',
            '"receiver_ready": "NOT_MACHINE_DETERMINED"',
        ):
            self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
