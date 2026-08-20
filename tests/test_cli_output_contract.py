import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from assurance_toolkit.findings import finding, outcome


REPOSITORY = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPOSITORY / "contracts" / "schemas" / "CLI_OUTPUT_CONTRACT.json"
ENV = os.environ | {"PYTHONPATH": str(REPOSITORY / "src"), "PYTHONDONTWRITEBYTECODE": "1"}


def cli(*args, input_text=None):
    return subprocess.run(
        [sys.executable, "-m", "assurance_toolkit", *args],
        cwd=REPOSITORY,
        env=ENV,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class CliOutputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
        cls.contract = json.loads(cls.contract_text)
        cls.envelopes = {item["id"]: item for item in cls.contract["envelopes"]}
        finding_path = CONTRACT_PATH.parent / cls.contract["finding_schema"]["relative_path"]
        cls.finding_schema = json.loads(finding_path.read_text(encoding="utf-8"))

    def exit_for(self, classification):
        for code, spec in self.contract["exit_semantics"]["codes"].items():
            if spec["class"] == classification:
                return int(code)
        self.fail(f"exit class absent from published contract: {classification}")

    def assert_not_json(self, text):
        with self.assertRaises((json.JSONDecodeError, TypeError)):
            json.loads(text)

    def assert_finding(self, item):
        self.assertTrue(set(self.finding_schema["required"]).issubset(item))
        self.assertIn(item["severity"], self.finding_schema["severity"])
        self.assertTrue(any(item["code"].startswith(prefix) for prefix in self.finding_schema["code_families"]))

    def assert_module_result(self, completed, operation):
        spec = self.envelopes["module_result_json"]
        self.assertEqual("", completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["exit_code"], completed.returncode)
        required = set(spec["required_top_level_fields"])
        self.assertTrue(required.issubset(payload))
        self.assertFalse(set(spec["forbidden_top_level_fields"]) & set(payload))
        self.assertIn(payload["result"], spec["result_enum"])
        self.assertEqual(spec["module_version"], payload["module_version"])
        self.assertIn(payload["module_id"], spec["modules"])
        module = spec["modules"][payload["module_id"]]
        self.assertEqual(module["rule_set_version"], payload["rule_set_version"])
        self.assertIn(operation, module["operations"])
        operation_spec = module["operations"][operation]
        allowed = required | set(operation_spec["allowed_extension_fields"])
        self.assertFalse(set(payload) - allowed)
        if payload["result"] == "PASS":
            self.assertTrue(set(operation_spec["required_extension_fields_on_pass"]).issubset(payload))
        self.assertIsInstance(payload["findings"], list)
        self.assertIsInstance(payload["facts"], list)
        for item in payload["findings"]:
            self.assert_finding(item)
        return payload

    def test_contract_identity_structure_and_deterministic_encoding(self):
        self.assertEqual("cli-output-contract/v1", self.contract["schema_version"])
        self.assertTrue(self.contract["normative"])
        self.assertEqual(
            "PUBLISHED_CONTRACT_TO_TEST_EXPECTATION_TO_ACTUAL_CLI_OUTPUT",
            self.contract["authority_direction"],
        )
        required_envelopes = {
            "module_result_json",
            "cli_parse_failure_json",
            "argparse_usage_error",
            "help_and_version_text",
            "synthetic_pilot_result_json",
        }
        self.assertEqual(required_envelopes, set(self.envelopes))
        self.assertEqual(required_envelopes, set(self.contract["scope"]["covered_envelope_ids"]))
        self.assertEqual({str(code) for code in range(6)}, set(self.contract["exit_semantics"]["codes"]))
        self.assertFalse(self.contract["scope"]["complete_current_input_contract_published"])
        self.assertEqual(
            self.contract_text,
            json.dumps(self.contract, ensure_ascii=False, indent=2) + "\n",
        )

    def test_module_result_json_conforms_for_all_six_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "task.json"
            task.write_text(json.dumps({
                "schema_version": "risk-descriptor/v1",
                "task_id": "contract",
                "action_class": "read",
                "target_class": "local_document",
                "reversibility": "not_applicable",
                "mutation_requested": False,
                "production_effect": "none",
                "credential_or_identity_effect": "none",
                "authority_effect": "none",
                "recovery_path": "not_applicable",
            }), encoding="utf-8")
            guard_target = root / "guard-target"
            corpus_root = root / "corpus"
            corpus_root.mkdir()
            (corpus_root / "source.txt").write_text("source", encoding="utf-8")
            manifest = root / "manifest.jsonl"
            prepared = root / "prepared.json"

            executions = [
                ("classify", cli("classify", str(task), "--format", "json")),
                ("check", cli("check", "fixtures/governance/valid-pack.json", "--format", "json")),
                ("guard", cli("guard", "fixtures/terminal/open-task.json", str(guard_target), "--executor", "synthetic-executor", "--format", "json")),
                ("corpus_freeze", cli("corpus", "freeze", str(corpus_root), "--manifest", str(manifest), "--format", "json")),
            ]
            self.assertEqual(0, executions[-1][1].returncode)
            accepted = hashlib.sha256(manifest.read_bytes()).hexdigest()
            executions.extend([
                ("corpus_verify", cli("corpus", "verify", str(manifest), "--accepted-manifest-sha256", accepted, "--format", "json")),
                ("handoff", cli("handoff", "fixtures/handoff/valid-observation.json", "--carrier", "direct-v1-ax1-ax2", "--format", "json")),
                ("closeout", cli("closeout", "fixtures/closeout/valid-closeout.json", "--format", "json")),
                ("eval_prepare", cli("eval", "prepare", "contracts/successor-eval/cases.jsonl", "--out", str(prepared), "--format", "json")),
            ])
            observed_modules = set()
            for operation, completed in executions:
                with self.subTest(operation=operation):
                    payload = self.assert_module_result(completed, operation)
                    self.assertEqual(self.exit_for("success"), completed.returncode)
                    observed_modules.add(payload["module_id"])
        self.assertEqual({f"PM-{index:02d}" for index in range(1, 7)}, observed_modules)

    def test_cli_parse_failure_json_conforms_as_distinct_envelope(self):
        spec = self.envelopes["cli_parse_failure_json"]
        completed = cli("classify", "--stdin", "--format", "json", input_text="{")
        payload = json.loads(completed.stdout)
        self.assertEqual(spec["exit_code"], completed.returncode)
        self.assertEqual("", completed.stderr)
        self.assertEqual(set(spec["required_top_level_fields"]), set(payload))
        self.assertFalse(set(payload) - set(spec["allowed_top_level_fields"]))
        self.assertEqual(spec["result"], payload["result"])
        self.assertIn(payload["module_id"], spec["module_id_enum"])
        self.assertNotIn(payload["module_id"], self.envelopes["module_result_json"]["modules"])
        for name in ("module_version", "rule_set_version", "profile", "exit_code"):
            self.assertEqual(spec[name], payload[name])
        self.assertEqual(1, len(payload["findings"]))
        self.assert_finding(payload["findings"][0])
        for name, expected in spec["finding"].items():
            self.assertEqual(expected, payload["findings"][0][name])

    def test_argparse_usage_error_is_exit_two_without_json(self):
        spec = self.envelopes["argparse_usage_error"]
        completed = cli("classify", "--profile", "not-a-profile")
        self.assertEqual(spec["exit_code"], completed.returncode)
        self.assertEqual("", completed.stdout)
        for marker in spec["stderr_contains"]:
            self.assertIn(marker, completed.stderr)
        self.assert_not_json(completed.stderr)

    def test_help_and_version_are_exit_zero_without_json(self):
        spec = self.envelopes["help_and_version_text"]
        for name, variant in spec["variants"].items():
            with self.subTest(variant=name):
                completed = cli(*variant["arguments"])
                self.assertEqual(spec["exit_code"], completed.returncode)
                self.assertEqual("", completed.stderr)
                for marker in variant["stdout_contains"]:
                    self.assertIn(marker, completed.stdout)
                self.assert_not_json(completed.stdout)

    def test_existing_synthetic_pilot_json_has_its_own_envelope(self):
        spec = self.envelopes["synthetic_pilot_result_json"]
        with tempfile.TemporaryDirectory() as temporary:
            completed = cli("pilot", "run", "A", "--root", str(Path(temporary) / "pilot-a"), "--format", "json")
        payload = json.loads(completed.stdout)
        variant = spec["variants"][payload["pilot"]]
        required = set(spec["required_top_level_fields"])
        allowed = required | set(spec["failure_extension_fields"]) | set(variant["allowed_extension_fields"])
        self.assertTrue(required.issubset(payload))
        self.assertFalse(set(payload) - allowed)
        self.assertIn(payload["result"], spec["result_enum"])
        self.assertIn(payload["pilot"], spec["pilot_id_enum"])
        self.assertEqual(spec["exit_codes_by_result"][payload["result"]], completed.returncode)
        if payload["result"] == "PASS":
            self.assertTrue(set(variant["required_extension_fields_on_pass"]).issubset(payload))

    def test_module_input_finding_is_structured_exit_two(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "unsupported.json"
            path.write_text(json.dumps({"schema_version": "risk-descriptor/v99"}), encoding="utf-8")
            completed = cli("classify", str(path), "--format", "json")
        payload = self.assert_module_result(completed, "classify")
        self.assertEqual(self.exit_for("input_or_invocation_fail"), completed.returncode)
        self.assertTrue(any(item["code"].startswith("IN") for item in payload["findings"]))

    def test_accepted_manifest_cli_distinguishes_input_and_integrity_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            (root / "file.txt").write_text("source", encoding="utf-8")
            manifest = Path(temporary) / "manifest.jsonl"
            frozen = cli("corpus", "freeze", str(root), "--manifest", str(manifest), "--format", "json")
            self.assertEqual(self.exit_for("success"), frozen.returncode)
            malformed = cli("corpus", "verify", str(manifest), "--accepted-manifest-sha256", "0" * 63, "--format", "json")
            mismatched = cli("corpus", "verify", str(manifest), "--accepted-manifest-sha256", "0" * 64, "--format", "json")

        malformed_payload = self.assert_module_result(malformed, "corpus_verify")
        mismatched_payload = self.assert_module_result(mismatched, "corpus_verify")
        self.assertEqual(self.exit_for("input_or_invocation_fail"), malformed.returncode)
        self.assertEqual(self.exit_for("integrity_hold"), mismatched.returncode)
        self.assertIn("IN01_PARSE_ERROR", [item["code"] for item in malformed_payload["findings"]])
        self.assertIn("CI11_ACCEPTED_MANIFEST_MISMATCH", [item["code"] for item in mismatched_payload["findings"]])

    def test_direct_process_exit_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generic-fail.json"
            path.write_text(json.dumps({
                "schema_version": "risk-descriptor/v1",
                "task_id": "exit-one",
                "action_class": "unknown_action",
                "target_class": "local_document",
                "reversibility": "not_applicable",
                "mutation_requested": False,
                "production_effect": "none",
                "credential_or_identity_effect": "none",
                "authority_effect": "none",
                "recovery_path": "not_applicable",
            }), encoding="utf-8")
            completed = cli("classify", str(path), "--format", "json")
        self.assertEqual(self.exit_for("generic_fail"), completed.returncode)
        self.assert_module_result(completed, "classify")

    def test_existing_process_exit_three(self):
        with tempfile.TemporaryDirectory() as temporary:
            pack = json.loads((REPOSITORY / "fixtures" / "governance" / "valid-pack.json").read_text(encoding="utf-8"))
            pack["actions"][0].update({"executed": True, "mutates": True, "authorization_ref": "DEC-001"})
            path = Path(temporary) / "hold.json"
            path.write_text(json.dumps(pack), encoding="utf-8")
            completed = cli("check", str(path), "--format", "json")
        self.assertEqual(self.exit_for("generic_hold"), completed.returncode)
        self.assert_module_result(completed, "check")

    def test_direct_cli_exit_four(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            source = root / "file.txt"
            source.write_text("before", encoding="utf-8")
            manifest = Path(temporary) / "manifest.jsonl"
            frozen = cli("corpus", "freeze", str(root), "--manifest", str(manifest), "--format", "json")
            self.assertEqual(self.exit_for("success"), frozen.returncode)
            source.write_text("after", encoding="utf-8")
            completed = cli("corpus", "verify", str(manifest), "--format", "json")
        self.assertEqual(self.exit_for("integrity_hold"), completed.returncode)
        self.assert_module_result(completed, "corpus_verify")

    def test_direct_process_exit_five(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = json.loads((REPOSITORY / "fixtures" / "terminal" / "open-task.json").read_text(encoding="utf-8"))
            state["terminal_state"] = "CLOSED"
            state_path = Path(temporary) / "closed.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            completed = cli("guard", str(state_path), str(Path(temporary) / "target"), "--executor", "synthetic-executor", "--format", "json")
        self.assertEqual(self.exit_for("terminal_or_target_hold"), completed.returncode)
        self.assert_module_result(completed, "guard")

    def test_published_precedence_controls_actual_outcome(self):
        precedence = {
            item["family"]: item
            for item in self.contract["exit_semantics"]["structured_precedence_high_to_low"]
        }
        input_item = finding(precedence["input"]["finding_prefix"] + "99_TEST", "ERROR", "$", "$", "input", None)
        integrity_item = finding(precedence["integrity"]["finding_prefix"] + "99_TEST", "ERROR", "$", "$", "integrity", None)
        terminal_item = finding(precedence["terminal"]["finding_prefix"] + "99_TEST", "HOLD", "$", "$", "terminal", None)
        hold_item = finding("GP99_TEST", precedence["hold_severity"]["severity"], "$", "$", "hold", None)
        generic_item = finding("GP98_TEST", "ERROR", "$", "$", "generic", None)

        self.assertEqual(precedence["input"]["exit_code"], outcome([input_item], "normal")[1])
        self.assertEqual(precedence["integrity"]["exit_code"], outcome([input_item, integrity_item], "normal")[1])
        self.assertEqual(precedence["terminal"]["exit_code"], outcome([input_item, integrity_item, terminal_item], "normal")[1])
        self.assertEqual(precedence["hold_severity"]["exit_code"], outcome([input_item, hold_item], "normal")[1])
        self.assertEqual(precedence["generic"]["exit_code"], outcome([generic_item], "normal")[1])


if __name__ == "__main__":
    unittest.main()
