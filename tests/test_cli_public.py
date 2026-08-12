import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
ENV = os.environ | {"PYTHONPATH": str(REPOSITORY / "src"), "PYTHONDONTWRITEBYTECODE": "1"}


def cli(*args, input_text=None, cwd=REPOSITORY):
    return subprocess.run(
        [sys.executable, "-m", "assurance_toolkit", *args],
        cwd=cwd,
        env=ENV,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PublicCliTests(unittest.TestCase):
    def test_version(self):
        result = cli("--version")
        self.assertEqual(0, result.returncode)
        self.assertIn("assurance 0.3.0-recovery.3", result.stdout)
        self.assertIn("0.3.0rc3", result.stdout)

    def test_help_lists_complete_surface(self):
        result = cli("--help")
        self.assertEqual(0, result.returncode)
        for command in ("classify", "check", "guard", "corpus", "handoff", "closeout", "eval", "pilot"):
            self.assertIn(command, result.stdout)

    def test_authority_option_is_limited_to_dependent_commands(self):
        for command in ("check", "guard", "closeout"):
            with self.subTest(command=command):
                self.assertIn("--authority-id", cli(command, "--help").stdout)
        for command in ("classify", "handoff"):
            with self.subTest(command=command):
                self.assertNotIn("--authority-id", cli(command, "--help").stdout)

    def test_classify_file_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            path.write_text(json.dumps({
                "task_id": "cli", "action_class": "read", "target_class": "local_document",
                "reversibility": "not_applicable", "mutation_requested": False,
                "production_effect": "none", "credential_or_identity_effect": "read",
                "authority_effect": "none", "recovery_path": "not_applicable",
            }), encoding="utf-8")
            result = cli("classify", str(path), "--format", "json")
            self.assertEqual(0, result.returncode)
            self.assertEqual("T0", json.loads(result.stdout)["tier"])

    def test_classify_stdin_json(self):
        task = {
            "task_id": "stdin", "action_class": "rotate", "target_class": "credential",
            "reversibility": "irreversible", "mutation_requested": True,
            "production_effect": "none", "credential_or_identity_effect": "rotate",
            "authority_effect": "none", "recovery_path": "rotation procedure",
        }
        result = cli("classify", "--stdin", "--format", "json", input_text=json.dumps(task))
        self.assertEqual("T3", json.loads(result.stdout)["tier"])

    def test_malformed_stdin_exit_two(self):
        result = cli("classify", "--stdin", "--format", "json", input_text="{")
        self.assertEqual(2, result.returncode)
        self.assertIn("IN01_PARSE_ERROR", result.stdout)

    def test_check_file(self):
        result = cli("check", "fixtures/governance/valid-pack.json", "--format", "json")
        self.assertEqual(0, result.returncode)
        self.assertEqual("PASS", json.loads(result.stdout)["result"])

    def test_check_authority_is_supplied_out_of_band(self):
        with tempfile.TemporaryDirectory() as temporary:
            pack = json.loads((REPOSITORY / "fixtures/governance/valid-pack.json").read_text(encoding="utf-8"))
            pack["actions"][0].update({"executed": True, "mutates": True, "authorization_ref": "DEC-001"})
            path = Path(temporary) / "pack.json"
            path.write_text(json.dumps(pack), encoding="utf-8")
            matched = cli("check", str(path), "--authority-id", "PROJECT_AUTHORITY", "--format", "json")
            mismatched = cli("check", str(path), "--authority-id", "OTHER_AUTHORITY", "--format", "json")
            omitted = cli("check", str(path), "--format", "json")
            self.assertEqual(0, matched.returncode)
            self.assertEqual(3, mismatched.returncode)
            self.assertEqual(3, omitted.returncode)

    def test_check_stdin(self):
        pack = {"pack_version": "governance-pack/v1", "claims": [], "decisions": [], "actions": [], "task": {}}
        result = cli("check", "--stdin", "--format", "json", input_text=json.dumps(pack))
        self.assertEqual(0, result.returncode)

    def test_guard_public_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "new-target"
            result = cli("guard", "fixtures/terminal/open-task.json", str(target), "--executor", "synthetic-executor", "--format", "json")
            self.assertEqual(0, result.returncode)
            self.assertEqual("CREATE_NEW_ATOMICALLY", json.loads(result.stdout)["plan"])
            self.assertFalse(target.exists())

    def test_guard_authority_option_validates_reopen_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = json.loads((REPOSITORY / "fixtures/terminal/open-task.json").read_text(encoding="utf-8"))
            state["terminal_state"] = "CLOSED"
            state_path = root / "state.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            receipt = {
                "current_terminal_hash": state["terminal_hash"],
                "new_attempt_identity": state["new_attempt_identity"],
                "proposed_target_sha256": state["target"]["proposed_sha256"],
                "authorized_executor": "synthetic-executor",
                "authorized_object": state["task_id"],
                "authorization_state": "AUTHORIZED",
                "decider": "alice@example.org",
            }
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            target = root / "new-target"
            result = cli("guard", str(state_path), str(target), "--executor", "synthetic-executor", "--reopen", str(receipt_path), "--authority-id", "alice@example.org", "--format", "json")
            self.assertEqual(0, result.returncode)
            self.assertEqual("CREATE_NEW_ATOMICALLY", json.loads(result.stdout)["plan"])

    def test_corpus_freeze_verify_public_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            (root / "file").write_text("bytes", encoding="utf-8")
            manifest = Path(temporary) / "manifest.jsonl"
            frozen = cli("corpus", "freeze", str(root), "--manifest", str(manifest), "--format", "json")
            checked = cli("corpus", "verify", str(manifest), "--format", "json")
            self.assertEqual(0, frozen.returncode)
            self.assertEqual(0, checked.returncode)

    def test_handoff_public_cli(self):
        result = cli("handoff", "fixtures/handoff/valid-observation.json", "--carrier", "direct-v1-ax1-ax2", "--format", "json")
        self.assertEqual(0, result.returncode)
        self.assertEqual("OBSERVATION_AND_STRUCTURAL_LINT_ONLY", json.loads(result.stdout)["mode"])

    def test_closeout_public_cli(self):
        result = cli("closeout", "fixtures/closeout/valid-closeout.json", "--format", "json")
        self.assertEqual(0, result.returncode)
        self.assertEqual("PASS", json.loads(result.stdout)["result"])

    def test_closeout_authority_option_validates_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = json.loads((REPOSITORY / "fixtures/closeout/valid-closeout.json").read_text(encoding="utf-8"))
            document["actions"] = [{"id": "A", "executed": True, "mutates": True, "authorization_ref": "D", "object_identity": "obj"}]
            document["authorizations"] = [{"id": "D", "state": "AUTHORIZED", "decider": "ACME-RELEASE-BOARD", "object_identity": "obj"}]
            document["source_mutation_count"] = 1
            path = Path(temporary) / "closeout.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result = cli("closeout", str(path), "--authority-id", "ACME-RELEASE-BOARD", "--format", "json")
            self.assertEqual(0, result.returncode)
            self.assertEqual("PASS", json.loads(result.stdout)["result"])

    def test_eval_prepare_public_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "prepared.json"
            result = cli("eval", "prepare", "contracts/successor-eval/cases.jsonl", "--out", str(output), "--format", "json")
            self.assertEqual(0, result.returncode)
            self.assertTrue(output.is_file())

    def test_eval_score_public_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            scores = Path(temporary) / "scores.jsonl"
            scores.write_text("".join(json.dumps({
                "case_id": f"SE-{index:02d}", "score": 2, "automatic_fail": False,
                "must_cite_met": True, "evidence_quote": "synthetic quote", "contaminated": False,
            }, separators=(",", ":")) + "\n" for index in range(1, 13)), encoding="utf-8")
            result = cli("eval", "score", "contracts/successor-eval/cases.jsonl", str(scores), "--format", "json")
            self.assertEqual(0, result.returncode)
            self.assertEqual(31, json.loads(result.stdout)["total_score"])

    def test_pilot_a_public_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pilot-a"
            result = cli("pilot", "run", "A", "--root", str(root), "--format", "json")
            self.assertEqual(0, result.returncode)
            self.assertEqual(20, json.loads(result.stdout)["normal_variants"])

    def test_json_output_is_deterministic(self):
        task = {
            "task_id": "deterministic", "action_class": "read", "target_class": "local_document",
            "reversibility": "not_applicable", "mutation_requested": False,
            "production_effect": "none", "credential_or_identity_effect": "none",
            "authority_effect": "none", "recovery_path": "not_applicable",
        }
        first = cli("classify", "--stdin", "--format", "json", input_text=json.dumps(task)).stdout
        second = cli("classify", "--stdin", "--format", "json", input_text=json.dumps(task)).stdout
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
