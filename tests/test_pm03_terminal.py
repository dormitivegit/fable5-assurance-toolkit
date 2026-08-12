import copy
import json
import tempfile
import unittest
from pathlib import Path

from assurance_toolkit.identities import file_identity
from assurance_toolkit.io_utils import sha256_bytes
from assurance_toolkit.terminal import preflight


DEFAULT_AUTHORITY = "PROJECT_AUTHORITY"


class TerminalFixtureMixin:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.target = self.root / "target.bin"
        self.data = b"proposed bytes"

    def tearDown(self):
        self.temp.cleanup()

    def state(self, **updates):
        value = {
            "schema_version": "task-state/v1",
            "task_id": "task-1",
            "terminal_state": "OPEN",
            "terminal_hash": "a" * 64,
            "new_attempt_identity": "attempt-2",
            "authorized_executor": "writer-1",
            "single_writer": True,
            "prerequisites": {"authorization_scope_matches": True, "recovery_path_ready": True},
            "target": {"proposed_sha256": sha256_bytes(self.data)},
        }
        value.update(updates)
        return value

    def receipt(self, **updates):
        value = {
            "current_terminal_hash": "a" * 64,
            "new_attempt_identity": "attempt-2",
            "proposed_target_sha256": sha256_bytes(self.data),
            "authorized_executor": "writer-1",
            "authorized_object": "task-1",
            "authorization_state": "AUTHORIZED",
            "decider": DEFAULT_AUTHORITY,
        }
        value.update(updates)
        return value


class TerminalGuardTests(TerminalFixtureMixin, unittest.TestCase):

    def test_open_absent_returns_create_plan(self):
        result = preflight(self.state(), self.target, "writer-1").to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual("CREATE_NEW_ATOMICALLY", result["plan"])
        self.assertTrue(result["allow_write"])

    def test_guard_never_creates_absent_target(self):
        preflight(self.state(), self.target, "writer-1")
        self.assertFalse(self.target.exists())

    def test_closed_valid_reopen_passes(self):
        result = preflight(self.state(terminal_state="CLOSED"), self.target, "writer-1", self.receipt(), authority_identity=DEFAULT_AUTHORITY).to_dict()
        self.assertEqual("CREATE_NEW_ATOMICALLY", result["plan"])

    def test_reopen_receipt_requires_out_of_band_authority(self):
        result = preflight(self.state(terminal_state="CLOSED"), self.target, "writer-1", self.receipt()).to_dict()
        self.assertEqual("DENY_CLOSED", result["plan"])
        self.assertIn("TG04_REOPEN_RECEIPT_MISMATCH", [item["code"] for item in result["findings"]])

    def test_reopen_receipt_authority_mismatch_holds(self):
        result = preflight(self.state(terminal_state="CLOSED"), self.target, "writer-1", self.receipt(), authority_identity="OTHER_AUTHORITY").to_dict()
        self.assertEqual("DENY_CLOSED", result["plan"])

    def test_same_hash_is_untouched_noop(self):
        self.target.write_bytes(self.data)
        before = file_identity(self.target)
        result = preflight(self.state(), self.target, "writer-1").to_dict()
        after = file_identity(self.target)
        self.assertEqual("IDEMPOTENT_NOOP", result["plan"])
        self.assertEqual(before, after)

    def test_different_hash_collision_preserves_target(self):
        self.target.write_bytes(b"incumbent")
        before = file_identity(self.target)
        result = preflight(self.state(), self.target, "writer-1").to_dict()
        self.assertEqual("DENY_COLLISION", result["plan"])
        self.assertEqual(before, file_identity(self.target))

    def test_symlink_target_is_collision(self):
        incumbent = self.root / "incumbent"
        incumbent.write_bytes(b"incumbent")
        self.target.symlink_to(incumbent.name)
        result = preflight(self.state(), self.target, "writer-1").to_dict()
        self.assertEqual("DENY_COLLISION", result["plan"])
        self.assertEqual(b"incumbent", incumbent.read_bytes())

    def test_directory_target_is_collision(self):
        self.target.mkdir()
        self.assertEqual("DENY_COLLISION", preflight(self.state(), self.target, "writer-1").to_dict()["plan"])

    def test_task_state_input_unchanged(self):
        state = self.state()
        before = copy.deepcopy(state)
        preflight(state, self.target, "writer-1")
        self.assertEqual(before, state)

    def test_output_is_deterministic(self):
        first = json.dumps(preflight(self.state(terminal_state="CLOSED"), self.target, "writer-1").to_dict())
        second = json.dumps(preflight(self.state(terminal_state="CLOSED"), self.target, "writer-1").to_dict())
        self.assertEqual(first, second)

    def test_positive_predicate_names_are_pass_conditions(self):
        result = preflight(self.state(), self.target, "writer-1").to_dict()
        self.assertTrue(all("not_" not in item["name"] and "failed" not in item["name"] for item in result["positive_predicates"]))


def make_closed_state_test(state_name):
    def test(self):
        result = preflight(self.state(terminal_state=state_name), self.target, "writer-1").to_dict()
        self.assertEqual("DENY_CLOSED", result["plan"])
        self.assertIn("TG01_TERMINAL_CLOSED", [item["code"] for item in result["findings"]])
        self.assertFalse(self.target.exists())
    return test


for terminal_state in ("CLOSED", "ACCEPTED", "RETIRED"):
    setattr(TerminalGuardTests, f"test_{terminal_state.lower()}_without_reopen_denied", make_closed_state_test(terminal_state))


RECEIPT_MISMATCHES = (
    ("terminal_hash", {"current_terminal_hash": "b" * 64}),
    ("attempt", {"new_attempt_identity": "attempt-old"}),
    ("target_hash", {"proposed_target_sha256": "c" * 64}),
    ("executor", {"authorized_executor": "writer-2"}),
    ("object", {"authorized_object": "task-2"}),
    ("state", {"authorization_state": "RECOMMENDED"}),
    ("decider", {"decider": "MODEL"}),
)


def make_receipt_mismatch_test(updates):
    def test(self):
        result = preflight(self.state(terminal_state="CLOSED"), self.target, "writer-1", self.receipt(**updates), authority_identity=DEFAULT_AUTHORITY).to_dict()
        codes = [item["code"] for item in result["findings"]]
        self.assertEqual("DENY_CLOSED", result["plan"])
        self.assertIn("TG04_REOPEN_RECEIPT_MISMATCH", codes)
        self.assertFalse(self.target.exists())
    return test


for name, updates in RECEIPT_MISMATCHES:
    setattr(TerminalGuardTests, f"test_reopen_mismatch_{name}", make_receipt_mismatch_test(updates))


class TerminalPreconditionTests(TerminalFixtureMixin, unittest.TestCase):
    def test_wrong_executor_denied(self):
        result = preflight(self.state(), self.target, "writer-2").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])
        self.assertIn("TG02_EXECUTOR_PRECONDITION_FAILED", [item["code"] for item in result["findings"]])

    def test_second_writer_denied(self):
        result = preflight(self.state(single_writer=False), self.target, "writer-1").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])

    def test_false_prerequisite_denied(self):
        result = preflight(self.state(prerequisites={"authorization_scope_matches": False}), self.target, "writer-1").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])

    def test_malformed_prerequisites_denied(self):
        result = preflight(self.state(prerequisites=[]), self.target, "writer-1").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])

    def test_unsupported_terminal_state_denied(self):
        result = preflight(self.state(terminal_state="FUTURE"), self.target, "writer-1").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])
        self.assertIn("TG06_UNSUPPORTED_TERMINAL_STATE", [item["code"] for item in result["findings"]])

    def test_unsupported_schema_denied(self):
        result = preflight(self.state(schema_version="task-state/v99"), self.target, "writer-1").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])

    def test_non_object_task_state_denied(self):
        result = preflight([], self.target, "writer-1").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])
        self.assertIn("IN01_PARSE_ERROR", [item["code"] for item in result["findings"]])

    def test_target_dict_public_interface(self):
        result = preflight(self.state(), {"path": str(self.target), "proposed_sha256": sha256_bytes(self.data)}, "writer-1").to_dict()
        self.assertEqual("CREATE_NEW_ATOMICALLY", result["plan"])

    def test_missing_proposed_hash_collides_existing(self):
        self.target.write_bytes(self.data)
        state = self.state(target={})
        self.assertEqual("DENY_COLLISION", preflight(state, self.target, "writer-1").to_dict()["plan"])

    def test_toctou_ceiling_is_explicit(self):
        result = preflight(self.state(), self.target, "writer-1").to_dict()
        self.assertIn("WRITER_MUST_RECHECK", result["toctou_ceiling"])

    def test_parent_symlink_path_ambiguity_denied(self):
        real = self.root / "real"
        real.mkdir()
        link = self.root / "link"
        link.symlink_to(real.name)
        result = preflight(self.state(), link / "target", "writer-1").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])
        self.assertIn("TG07_TARGET_PATH_AMBIGUITY", [item["code"] for item in result["findings"]])

    def test_dotdot_path_ambiguity_denied(self):
        ambiguous = self.root / "child" / ".." / "target"
        result = preflight(self.state(), ambiguous, "writer-1").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])


if __name__ == "__main__":
    unittest.main()
