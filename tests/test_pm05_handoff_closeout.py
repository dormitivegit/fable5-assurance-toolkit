import copy
import json
import tempfile
import unittest
from pathlib import Path

from assurance_toolkit.closeout import validate_closeout
from assurance_toolkit.handoff import (
    DIRECT_CARRIER_SHA256,
    SKILL_PACKAGE_SHA256,
    SKILL_RUNTIME_SHA256,
    validate_handoff,
)


class DocumentFixtureMixin:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def handoff(self, **updates):
        value = {
            "schema_version": "handoff-observation/v1",
            "carrier_identity": "direct-v1-ax1-ax2",
            "carrier_sha256": DIRECT_CARRIER_SHA256,
            "dimensions": {
                "summary": "summary", "technical": "technical", "state": "state",
                "task": "task", "development": "development", "facts_evidence": "facts and evidence",
            },
            "evidence_cross_cutting": True,
            "authority_states": ["ADJUDICATED", "AUTHORIZED", "NOT_AUTHORIZED", "REJECTED"],
            "artifact_status": "RECOVERY_CANDIDATE",
            "source_references": [],
            "direct_evidence_conflict": False,
        }
        value.update(updates)
        return value

    def closeout(self, **updates):
        value = {
            "schema_version": "closeout/v1",
            "final_result": "PASS_SYNTHETIC_COMPLETE",
            "terminal_state": "CLOSED",
            "expected_assertions": {"target_absent": True, "source_unchanged": True},
            "actions": [], "authorizations": [], "source_mutation_count": 0,
            "source_pre_post_match": "YES", "output_self_ingestion_count": 0,
            "stop_conditions": ["identity drift"],
            "artifact_identity": {"role": "closeout", "sha256": "a" * 64},
            "collision_or_rerun_possible": False,
        }
        value.update(updates)
        return value


class HandoffTests(DocumentFixtureMixin, unittest.TestCase):
    def test_direct_carrier_positive(self):
        path = self.write("handoff.json", self.handoff())
        result = validate_handoff(path, "direct-v1-ax1-ax2").to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual("NOT_MACHINE_DETERMINED", result["receiver_ready"])

    def test_skill_carrier_positive(self):
        value = self.handoff(
            carrier_identity="skill-v1-candidate-ax1-ax2",
            carrier_sha256=SKILL_PACKAGE_SHA256,
            runtime_sha256=SKILL_RUNTIME_SHA256,
        )
        result = validate_handoff(self.write("skill.json", value), "skill-v1-candidate-ax1-ax2").to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual(SKILL_PACKAGE_SHA256, result["carrier_sha256"])

    def test_unknown_carrier_holds(self):
        path = self.write("handoff.json", self.handoff())
        result = validate_handoff(path, "future-v2").to_dict()
        self.assertIn("HC01_UNKNOWN_CARRIER", [item["code"] for item in result["findings"]])

    def test_wrong_declared_carrier_holds(self):
        path = self.write("handoff.json", self.handoff(carrier_identity="skill-v1-candidate-ax1-ax2"))
        self.assertIn("HC06_CARRIER_IDENTITY_MISMATCH", [item["code"] for item in validate_handoff(path, "direct-v1-ax1-ax2").to_dict()["findings"]])

    def test_wrong_direct_hash_holds(self):
        path = self.write("handoff.json", self.handoff(carrier_sha256="0" * 64))
        self.assertIn("HC06_CARRIER_IDENTITY_MISMATCH", [item["code"] for item in validate_handoff(path, "direct-v1-ax1-ax2").to_dict()["findings"]])

    def test_wrong_skill_runtime_hash_holds(self):
        value = self.handoff(carrier_identity="skill-v1-candidate-ax1-ax2", carrier_sha256=SKILL_PACKAGE_SHA256, runtime_sha256="0" * 64)
        path = self.write("skill.json", value)
        self.assertIn("HC06_CARRIER_IDENTITY_MISMATCH", [item["code"] for item in validate_handoff(path, "skill-v1-candidate-ax1-ax2").to_dict()["findings"]])

    def test_legacy_eight_field_holds(self):
        value = {"schema_version": "legacy-eight-field/v1", "handoff_id": "1", "sot": "x", "current_route": "x", "latest_delta": "x", "rejected": [], "next_action": "x", "evidence": []}
        result = validate_handoff(self.write("legacy.json", value), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("HC01_UNKNOWN_CARRIER", [item["code"] for item in result["findings"]])

    def test_unverified_future_version_holds(self):
        result = validate_handoff(self.write("future.json", self.handoff(schema_version="handoff-observation/v2")), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("IN02_UNSUPPORTED_VERSION", [item["code"] for item in result["findings"]])

    def test_missing_dimension_warns_normal(self):
        value = self.handoff()
        value["dimensions"]["development"] = ""
        result = validate_handoff(self.write("missing.json", value), "direct-v1-ax1-ax2").to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertIn("HC02_MATERIAL_DIMENSION_ABSENT", [item["code"] for item in result["findings"]])

    def test_missing_dimension_blocks_strict_only(self):
        value = self.handoff(dimensions={})
        result = validate_handoff(self.write("missing.json", value), "direct-v1-ax1-ax2", "strict").to_dict()
        self.assertEqual("FAIL", result["result"])

    def test_evidence_not_cross_cutting_warns(self):
        result = validate_handoff(self.write("evidence.json", self.handoff(evidence_cross_cutting=False)), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("HC03_EVIDENCE_NOT_CROSS_CUTTING", [item["code"] for item in result["findings"]])

    def test_authority_layer_missing_holds(self):
        result = validate_handoff(self.write("authority.json", self.handoff(authority_states=["AUTHORIZED"])), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("HC05_AUTHORITY_LAYER_MISSING", [item["code"] for item in result["findings"]])

    def test_unknown_authority_state_holds(self):
        states = ["ADJUDICATED", "AUTHORIZED", "NOT_AUTHORIZED", "REJECTED", "MAYBE"]
        result = validate_handoff(self.write("authority.json", self.handoff(authority_states=states)), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("HC05_AUTHORITY_LAYER_MISSING", [item["code"] for item in result["findings"]])

    def test_candidate_cannot_claim_canonical(self):
        states = ["ADJUDICATED", "AUTHORIZED", "NOT_AUTHORIZED", "REJECTED", "CANONICAL"]
        result = validate_handoff(self.write("canonical.json", self.handoff(authority_states=states, artifact_status="CANDIDATE")), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("HC05_AUTHORITY_LAYER_MISSING", [item["code"] for item in result["findings"]])

    def test_direct_evidence_conflict_holds(self):
        result = validate_handoff(self.write("conflict.json", self.handoff(direct_evidence_conflict=True)), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("HC07_DUAL_CARRIER_PARITY_REGRESSION", [item["code"] for item in result["findings"]])

    def test_invalid_load_bearing_source_holds(self):
        reference = {"load_bearing": True, "identity": {"path": str(self.root / "missing")}, "location": "anchor"}
        result = validate_handoff(self.write("source.json", self.handoff(source_references=[reference])), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("HC03_EVIDENCE_NOT_CROSS_CUTTING", [item["code"] for item in result["findings"]])

    def test_context_dependency_warns(self):
        value = self.handoff()
        value["dimensions"]["task"] = "see previous discussion"
        result = validate_handoff(self.write("context.json", value), "direct-v1-ax1-ax2").to_dict()
        self.assertIn("HC04_NON_SELF_CONTAINED", [item["code"] for item in result["findings"]])

    def test_markdown_structural_observation(self):
        path = self.root / "handoff.md"
        path.write_text("# Summary\nTechnical architecture evidence.\nState and task.\nDevelopment future.\nFacts evidence.\nADJUDICATED AUTHORIZED NOT_AUTHORIZED REJECTED\n", encoding="utf-8")
        result = validate_handoff(path, "direct-v1-ax1-ax2").to_dict()
        self.assertEqual("PASS", result["result"])

    def test_machine_claim_boundaries_always_explicit(self):
        result = validate_handoff(self.write("handoff.json", self.handoff()), "direct-v1-ax1-ax2").to_dict()
        self.assertEqual("NOT_MACHINE_DETERMINED", result["semantically_complete"])
        self.assertEqual("NOT_MACHINE_DETERMINED", result["fully_self_contained"])

    def test_output_is_deterministic(self):
        path = self.write("handoff.json", self.handoff(authority_states=[]))
        first = json.dumps(validate_handoff(path, "direct-v1-ax1-ax2").to_dict())
        second = json.dumps(validate_handoff(path, "direct-v1-ax1-ax2").to_dict())
        self.assertEqual(first, second)


class CloseoutTests(DocumentFixtureMixin, unittest.TestCase):
    def codes(self, value, receipt=None):
        path = self.write("closeout.json", value)
        return validate_closeout(path, guard_receipt=receipt).to_dict()

    def test_valid_closeout_passes(self):
        self.assertEqual("PASS", self.codes(self.closeout())["result"])

    def test_ambiguous_result_rejected(self):
        result = self.codes(self.closeout(final_result="PARTIAL_PASS"))
        self.assertIn("HC20_AMBIGUOUS_RESULT", [item["code"] for item in result["findings"]])

    def test_unknown_terminal_state_rejected(self):
        result = self.codes(self.closeout(terminal_state="FUTURE"))
        self.assertIn("HC20_AMBIGUOUS_RESULT", [item["code"] for item in result["findings"]])

    def test_missing_assertions_rejected(self):
        result = self.codes(self.closeout(expected_assertions={}))
        self.assertIn("HC21_TARGET_ASSERTION_MISSING", [item["code"] for item in result["findings"]])

    def test_false_positive_assertion_rejected(self):
        result = self.codes(self.closeout(expected_assertions={"source_unchanged": False}))
        self.assertIn("HC21_TARGET_ASSERTION_MISSING", [item["code"] for item in result["findings"]])

    def test_mutation_count_mismatch_rejected(self):
        result = self.codes(self.closeout(source_mutation_count=1))
        self.assertIn("HC22_MUTATION_MISMATCH", [item["code"] for item in result["findings"]])

    def test_mutation_without_authorization_holds(self):
        action = {"id": "A", "executed": True, "mutates": True, "authorization_ref": "D", "object_identity": "obj"}
        result = self.codes(self.closeout(actions=[action], source_mutation_count=1))
        self.assertIn("HC22_MUTATION_MISMATCH", [item["code"] for item in result["findings"]])

    def test_exact_mutation_authorization_passes(self):
        action = {"id": "A", "executed": True, "mutates": True, "authorization_ref": "D", "object_identity": "obj"}
        auth = {"id": "D", "state": "AUTHORIZED", "decider": "ZRN", "object_identity": "obj"}
        result = self.codes(self.closeout(actions=[action], authorizations=[auth], source_mutation_count=1))
        self.assertEqual("PASS", result["result"])

    def test_source_integrity_unproven_rejected(self):
        result = self.codes(self.closeout(source_pre_post_match="NO"))
        self.assertIn("HC23_SOURCE_INTEGRITY_UNPROVEN", [item["code"] for item in result["findings"]])

    def test_self_ingestion_rejected(self):
        result = self.codes(self.closeout(output_self_ingestion_count=1))
        self.assertIn("HC23_SOURCE_INTEGRITY_UNPROVEN", [item["code"] for item in result["findings"]])

    def test_missing_stop_condition_rejected(self):
        result = self.codes(self.closeout(stop_conditions=[]))
        self.assertIn("HC25_STOP_CONDITION_MISSING", [item["code"] for item in result["findings"]])

    def test_bad_artifact_hash_rejected(self):
        result = self.codes(self.closeout(artifact_identity={"role": "x", "sha256": "short"}))
        self.assertIn("HC21_TARGET_ASSERTION_MISSING", [item["code"] for item in result["findings"]])

    def test_collision_risk_without_receipt_holds(self):
        result = self.codes(self.closeout(collision_or_rerun_possible=True))
        self.assertIn("HC24_GUARD_CONFLICT", [item["code"] for item in result["findings"]])

    def test_matching_guard_receipt_passes(self):
        receipt = {"plan": "CREATE_NEW_ATOMICALLY", "target_sha256": "a" * 64}
        self.assertEqual("PASS", self.codes(self.closeout(), receipt)["result"])

    def test_mismatched_guard_receipt_holds(self):
        receipt = {"plan": "DENY_COLLISION", "target_sha256": "b" * 64}
        result = self.codes(self.closeout(), receipt)
        self.assertIn("HC24_GUARD_CONFLICT", [item["code"] for item in result["findings"]])

    def test_unsupported_closeout_version_rejected(self):
        result = self.codes(self.closeout(schema_version="closeout/v99"))
        self.assertIn("IN02_UNSUPPORTED_VERSION", [item["code"] for item in result["findings"]])

    def test_non_object_closeout_rejected(self):
        path = self.write("closeout.json", [])
        result = validate_closeout(path).to_dict()
        self.assertIn("IN01_PARSE_ERROR", [item["code"] for item in result["findings"]])

    def test_closeout_output_deterministic(self):
        path = self.write("closeout.json", self.closeout(final_result="PARTIAL"))
        self.assertEqual(json.dumps(validate_closeout(path).to_dict()), json.dumps(validate_closeout(path).to_dict()))


if __name__ == "__main__":
    unittest.main()
