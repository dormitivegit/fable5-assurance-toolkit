import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "examples" / "machine-consumer" / "run.py"


class MachineConsumerExampleTests(unittest.TestCase):
    def test_consumer_parses_nonblocking_warning_before_branching(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=REPOSITORY,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        for expected in (
            "STRUCTURED_JSON=PARSED",
            "PROCESS_EXIT=0",
            "FINDING_CODES=CI10_NEW_SOURCE_DETECTED",
            "CONSUMER_DECISION=REVIEW_NEW_SOURCE",
            "HUMAN_DECISION_REQUIRED=YES",
            "RUNTIME_NETWORK_DEPENDENCY=NONE",
            "TEMP_WORKSPACE_CLEANUP=automatic",
        ):
            self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
