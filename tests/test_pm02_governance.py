import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from assurance_toolkit.governance import check
from assurance_toolkit.io_utils import sha256_bytes, sha256_file


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "evidence.txt"
        self.source.write_text("alpha\nload-bearing anchor\nomega\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def pack(self):
        return {
            "pack_version": "governance-pack/v1",
            "claims": [{
                "id": "C1", "text": "synthetic claim", "load_bearing": True,
                "verification": "VERIFIED",
                "source_identity": {"path": str(self.source), "sha256": sha256_file(self.source)},
                "location": "load-bearing anchor", "conflict": "NONE",
            }],
            "decisions": [{
                "id": "D1", "subject": "object-a", "state": "AUTHORIZED",
                "decider": "ZRN", "object_identity": "object-a@sha256",
            }],
            "actions": [{
                "id": "A1", "executed": True, "mutates": True,
                "authorization_ref": "D1", "object_identity": "object-a@sha256",
            }],
            "task": {"stop_conditions": ["identity drift"]},
            "result": "PASS_SYNTHETIC",
        }

    def assert_code(self, pack, code, profile="normal"):
        result = check(pack, profile).to_dict()
        self.assertIn(code, [item["code"] for item in result["findings"]])
        self.assertNotEqual("PASS", result["result"])

    def test_valid_pack_passes(self):
        result = check(self.pack()).to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual(0, result["exit_code"])

    def test_input_is_not_mutated(self):
        pack = self.pack()
        before = copy.deepcopy(pack)
        check(pack)
        self.assertEqual(before, pack)

    def test_results_are_deterministic(self):
        pack = self.pack()
        pack["claims"][0]["verification"] = "UNVERIFIED"
        first = json.dumps(check(pack).to_dict(), ensure_ascii=False)
        second = json.dumps(check(pack).to_dict(), ensure_ascii=False)
        self.assertEqual(first, second)

    def test_business_truth_not_adjudicated(self):
        result = check(self.pack()).to_dict()
        self.assertIn({"business_truth_adjudicated": False}, result["facts"])

    def test_exact_json_pointer_source_passes(self):
        source = self.root / "source.json"
        source.write_text('{"nested":{"value":"ok"}}\n', encoding="utf-8")
        pack = self.pack()
        pack["claims"][0]["source_identity"] = {"path": str(source), "sha256": sha256_file(source)}
        pack["claims"][0]["location"] = {"json_pointer": "/nested/value", "expected": "ok"}
        self.assertEqual("PASS", check(pack).to_dict()["result"])

    def test_exact_zip_member_source_passes(self):
        archive = self.root / "evidence.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("member.txt", "member anchor")
        pack = self.pack()
        pack["claims"][0]["source_identity"] = {"path": str(archive), "archive_member": "member.txt", "sha256": sha256_bytes(b"member anchor")}
        pack["claims"][0]["location"] = "member anchor"
        self.assertEqual("PASS", check(pack).to_dict()["result"])

    def test_finding_schema_complete(self):
        pack = self.pack()
        pack["claims"][0].pop("source_identity")
        item = check(pack).to_dict()["findings"][0]
        self.assertEqual({"code", "severity", "path", "location", "message", "rule_version", "evidence"}, set(item))


def _mutation(name):
    def mutate(pack, test):
        claim = pack["claims"][0]
        decision = pack["decisions"][0]
        action = pack["actions"][0]
        if name == "missing_identity":
            claim.pop("source_identity")
        elif name == "missing_location":
            claim.pop("location")
        elif name == "unverified":
            claim["verification"] = "UNVERIFIED"
        elif name == "missing_verification":
            claim.pop("verification")
        elif name == "absent_source":
            claim["source_identity"]["path"] = str(test.root / "absent")
        elif name == "wrong_hash":
            claim["source_identity"]["sha256"] = "0" * 64
        elif name == "missing_anchor":
            claim["location"] = "not in source"
        elif name == "bad_line_range":
            claim["location"] = {"anchor": "load-bearing anchor", "line_start": 99, "line_end": 100}
        elif name == "claim_conflict":
            claim["conflict"] = "UNRESOLVED"
        elif name == "no_auth_ref":
            action.pop("authorization_ref")
        elif name == "missing_auth_decision":
            action["authorization_ref"] = "missing"
        elif name == "recommended":
            decision["state"] = "RECOMMENDED"
        elif name == "not_authorized":
            decision["state"] = "NOT_AUTHORIZED"
        elif name == "rejected":
            decision["state"] = "REJECTED"
        elif name == "wrong_decider":
            decision["decider"] = "MODEL"
        elif name == "wrong_object":
            decision["object_identity"] = "other-object"
        elif name == "missing_action_object":
            action.pop("object_identity")
        elif name == "accepted_not_authorization":
            decision["state"] = "ACCEPTED"
        elif name == "live_conflict":
            pack["decisions"].append({"id": "D2", "subject": "object-a", "state": "NOT_AUTHORIZED", "decider": "ZRN", "object_identity": "object-a@sha256"})
        elif name == "false_pass":
            claim["verification"] = "UNVERIFIED"
        elif name == "unsupported_version":
            pack["pack_version"] = "governance-pack/v99"
        elif name == "claims_not_list":
            pack["claims"] = {}
        elif name == "decisions_not_list":
            pack["decisions"] = {}
        elif name == "actions_not_list":
            pack["actions"] = {}
        elif name == "task_not_object":
            pack["task"] = []
        elif name == "claim_not_object":
            pack["claims"] = ["claim"]
        elif name == "decision_not_object":
            pack["decisions"] = ["decision"]
        elif name == "action_not_object":
            pack["actions"] = ["action"]
    return mutate


CASES = [
    ("missing_identity", "GP01_MISSING_EVIDENCE"),
    ("missing_location", "GP01_MISSING_EVIDENCE"),
    ("unverified", "GP02_UNVERIFIED_LOAD_BEARING_CLAIM"),
    ("missing_verification", "GP02_UNVERIFIED_LOAD_BEARING_CLAIM"),
    ("absent_source", "GP05_BROKEN_EVIDENCE_REFERENCE"),
    ("wrong_hash", "GP05_BROKEN_EVIDENCE_REFERENCE"),
    ("missing_anchor", "GP05_BROKEN_EVIDENCE_REFERENCE"),
    ("bad_line_range", "GP05_BROKEN_EVIDENCE_REFERENCE"),
    ("claim_conflict", "GP04_UNRESOLVED_AUTHORITY_CONFLICT"),
    ("no_auth_ref", "GP03_UNAUTHORIZED_ACTION"),
    ("missing_auth_decision", "GP03_UNAUTHORIZED_ACTION"),
    ("recommended", "GP03_UNAUTHORIZED_ACTION"),
    ("not_authorized", "GP03_UNAUTHORIZED_ACTION"),
    ("rejected", "GP03_UNAUTHORIZED_ACTION"),
    ("wrong_decider", "GP03_UNAUTHORIZED_ACTION"),
    ("wrong_object", "GP03_UNAUTHORIZED_ACTION"),
    ("missing_action_object", "GP03_UNAUTHORIZED_ACTION"),
    ("accepted_not_authorization", "GP03_UNAUTHORIZED_ACTION"),
    ("live_conflict", "GP04_UNRESOLVED_AUTHORITY_CONFLICT"),
    ("false_pass", "GP06_FALSE_PASS_ASSERTION"),
    ("unsupported_version", "IN02_UNSUPPORTED_VERSION"),
    ("claims_not_list", "IN01_PARSE_ERROR"),
    ("decisions_not_list", "IN01_PARSE_ERROR"),
    ("actions_not_list", "IN01_PARSE_ERROR"),
    ("task_not_object", "IN01_PARSE_ERROR"),
    ("claim_not_object", "IN01_PARSE_ERROR"),
    ("decision_not_object", "IN01_PARSE_ERROR"),
    ("action_not_object", "IN01_PARSE_ERROR"),
]


def make_case(name, expected):
    def test(self):
        pack = self.pack()
        _mutation(name)(pack, self)
        self.assert_code(pack, expected)
    return test


for name, expected in CASES:
    setattr(GovernanceTests, f"test_negative_{name}", make_case(name, expected))


class GovernanceInputTests(unittest.TestCase):
    def test_non_object_root(self):
        self.assertIn("IN01_PARSE_ERROR", [item["code"] for item in check([]).to_dict()["findings"]])

    def test_strict_profile_keeps_contract_semantics(self):
        result = check({"pack_version": "governance-pack/v1", "claims": [], "decisions": [], "actions": [], "task": {}}, "strict").to_dict()
        self.assertEqual("PASS", result["result"])

    def test_unknown_profile_is_input_error(self):
        result = check({}, "extreme").to_dict()
        self.assertIn("IN02_UNSUPPORTED_VERSION", [item["code"] for item in result["findings"]])


if __name__ == "__main__":
    unittest.main()
