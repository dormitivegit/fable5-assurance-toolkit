#!/usr/bin/env python3
"""Consume a nonblocking FABLE5 JSON finding with an explicit review branch."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def run_assurance(*arguments: str) -> tuple[int, dict[str, object]]:
    environment = os.environ | {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(REPOSITORY_ROOT / "src"),
    }
    completed = subprocess.run(
        [sys.executable, "-m", "assurance_toolkit", *arguments, "--format", "json"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.stderr:
        raise RuntimeError(f"assurance wrote to stderr: {completed.stderr.strip()}")
    return completed.returncode, json.loads(completed.stdout)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="fable5-machine-consumer-") as temporary:
        workspace = Path(temporary)
        source = workspace / "source"
        source.mkdir()
        manifest = workspace / "baseline.jsonl"
        (source / "tracked.py").write_text("VALUE = 'tracked'\n", encoding="utf-8")

        freeze_exit, freeze = run_assurance(
            "corpus", "freeze", str(source), "--manifest", str(manifest)
        )
        require(freeze_exit == 0 and freeze["result"] == "PASS", "baseline freeze failed")

        (source / "new.py").write_text("VALUE = 'new'\n", encoding="utf-8")
        verify_exit, verification = run_assurance(
            "corpus", "verify", str(manifest), "--detect-new"
        )
        findings = verification["findings"]
        warning_codes = sorted(
            finding["code"]
            for finding in findings
            if finding["severity"] == "WARN"
        )
        require(verify_exit == 0, f"expected nonblocking exit 0, observed {verify_exit}")
        require(verification["result"] == "PASS", "expected normal-profile PASS")
        require(
            warning_codes == ["CI10_NEW_SOURCE_DETECTED"],
            f"unexpected warning codes: {warning_codes}",
        )

    print("STRUCTURED_JSON=PARSED")
    print(f"PROCESS_EXIT={verify_exit}")
    print(f"FINDING_CODES={','.join(warning_codes)}")
    print("CONSUMER_DECISION=REVIEW_NEW_SOURCE")
    print("HUMAN_DECISION_REQUIRED=YES")
    print("RUNTIME_NETWORK_DEPENDENCY=NONE")
    print("TEMP_WORKSPACE_CLEANUP=automatic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
