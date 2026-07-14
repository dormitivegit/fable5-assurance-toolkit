import json
import tempfile
import unittest
from pathlib import Path

from assurance_toolkit.pilots import run_pilot


class PilotPublicTests(unittest.TestCase):
    def new_root(self, temporary, name):
        return Path(temporary) / name

    def test_pilot_a_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = run_pilot("A", self.new_root(temporary, "a"))
        self.assertEqual("PASS", result["result"])
        self.assertEqual(20, result["normal_variants"])
        self.assertEqual(0, result["blocking_false_positive_count"])
        self.assertEqual(2, result["escalation_detected_count"])
        self.assertEqual(0, result["manufactured_defect_count"])

    def test_pilot_a_normalized_output_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = run_pilot("A", self.new_root(temporary, "a1"))
            second = run_pilot("A", self.new_root(temporary, "a2"))
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_pilot_b_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = run_pilot("B", self.new_root(temporary, "b"))
        self.assertEqual("PASS", result["result"])
        self.assertEqual(5, result["defect_class_count"])
        self.assertEqual(0, result["false_negative_count"])
        self.assertEqual(0, result["blocking_false_positive_count"])
        self.assertEqual(0, result["scope_outside_write_count"])
        self.assertEqual(0, result["global_or_user_git_config_delta"])
        self.assertEqual(0, result["network_contact_count"])
        self.assertTrue(result["valid_workflow_pass"])

    def test_pilot_b_adversarial_traps_present(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = run_pilot("B", self.new_root(temporary, "b"))
        names = {item["name"] for item in result["adversarial_traps"]}
        self.assertTrue({"symlink_escape", "nested_repository_ambiguity", "remote_trap", "staged_unstaged_mismatch", "file_mode_drift", "evidence_collision", "cleanup_failure_simulation"}.issubset(names))

    def test_pilot_c1_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = run_pilot("C1", self.new_root(temporary, "c1"))
        self.assertEqual("PASS", result["result"])
        self.assertEqual(5, result["trap_count"])
        self.assertEqual(5, result["traps_blocked_before_mutation"])
        self.assertEqual(0, result["filesystem_mutation_count"])
        self.assertTrue(result["happy_path_preflight_pass"])

    def test_pilot_c2_atomic_race_and_fault_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = run_pilot("C2", self.new_root(temporary, "c2"))
        self.assertEqual("PASS", result["result"])
        self.assertEqual(50, result["two_writer_race_rounds"])
        self.assertEqual(20, result["multi_writer_race_rounds"])
        self.assertEqual(0, result["clobber_count"])
        self.assertEqual(0, result["partial_target_count"])
        self.assertEqual(0, result["orphan_temp_count"])
        self.assertEqual(0, result["outside_root_write_count"])
        self.assertTrue(result["fault_cases_pass"])
        faults = {item["case"]: item for item in result["fault_results"]}
        self.assertEqual("GUARD_DENIED", faults["terminal_state_change_at_write_seam"]["status"])
        self.assertEqual("GUARD_DENIED", faults["authorization_change_at_write_seam"]["status"])

    def test_pilot_root_collision_holds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "occupied"
            root.mkdir()
            result = run_pilot("A", root)
        self.assertEqual("HOLD", result["result"])
        self.assertEqual("PI01_ROOT_COLLISION", result["code"])

    def test_unknown_pilot_fails_without_root_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "unknown"
            result = run_pilot("Z", root)
            self.assertEqual("FAIL", result["result"])
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
