import copy
import json
import unittest

from assurance_toolkit.pilots import NORMAL_VARIANTS, _descriptor
from assurance_toolkit.risk import classify


def base_descriptor(**updates):
    value = {
        "schema_version": "risk-descriptor/v1",
        "task_id": "risk-test",
        "action_class": "edit",
        "target_class": "repository",
        "reversibility": "reversible",
        "mutation_requested": True,
        "production_effect": "none",
        "credential_or_identity_effect": "none",
        "authority_effect": "none",
        "recovery_path": "git revert",
    }
    value.update(updates)
    return value


class RiskMatrixTests(unittest.TestCase):
    pass


def make_low_risk_test(row):
    def test(self):
        descriptor = _descriptor(row)
        before = copy.deepcopy(descriptor)
        result = classify(descriptor).to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertIn(result["tier"], {"T0", "T1"})
        self.assertTrue(result["explicitly_unnecessary"])
        self.assertFalse(result["classification_is_authorization"])
        self.assertEqual(before, descriptor)
    return test


for index, row in enumerate(NORMAL_VARIANTS):
    setattr(RiskMatrixTests, f"test_low_risk_{index:02d}_{row[0].replace('-', '_')}", make_low_risk_test(row))


ESCALATIONS = [
    ("credential_modify", {"credential_or_identity_effect": "modify"}, "T3"),
    ("credential_expose", {"credential_or_identity_effect": "expose"}, "T3"),
    ("credential_rotate", {"credential_or_identity_effect": "rotate"}, "T3"),
    ("credential_delete", {"credential_or_identity_effect": "delete"}, "T3"),
    ("identity_revoke", {"credential_or_identity_effect": "revoke"}, "T3"),
    ("production_deploy", {"production_effect": "deploy"}, "T3"),
    ("production_delete", {"production_effect": "delete"}, "T3"),
    ("authority_replace", {"authority_effect": "replace"}, "T4"),
    ("authority_supersede", {"authority_effect": "supersede"}, "T4"),
    ("authority_reopen", {"authority_effect": "reopen"}, "T4"),
    ("authority_overturn", {"authority_effect": "overturn"}, "T4"),
    ("authority_promote", {"authority_effect": "promote"}, "T4"),
    ("authority_retire", {"authority_effect": "retire"}, "T4"),
    ("irreversible_delete", {"action_class": "delete", "reversibility": "irreversible"}, "T3"),
]


def make_escalation_test(updates, expected):
    def test(self):
        result = classify(base_descriptor(**updates)).to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual(expected, result["tier"])
        self.assertTrue(result["human_decision_required"])
    return test


for name, updates, expected in ESCALATIONS:
    setattr(RiskMatrixTests, f"test_escalation_{name}", make_escalation_test(updates, expected))


class RiskBoundaryTests(unittest.TestCase):
    def test_reading_credential_documentation_not_t3(self):
        value = base_descriptor(action_class="read", target_class="local_document", reversibility="not_applicable", mutation_requested=False, credential_or_identity_effect="read")
        self.assertEqual("T0", classify(value).to_dict()["tier"])

    def test_summarizing_canonical_not_t4(self):
        value = base_descriptor(action_class="summarize", target_class="local_document", reversibility="not_applicable", mutation_requested=False, authority_effect="summarize")
        self.assertEqual("T0", classify(value).to_dict()["tier"])

    def test_supplied_low_tier_does_not_bypass_floor(self):
        value = base_descriptor(credential_or_identity_effect="rotate", supplied_tier="T0")
        result = classify(value).to_dict()
        self.assertEqual("T3", result["tier"])
        self.assertIn("RR04_TIER_FLOOR_OVERRIDE", [item["code"] for item in result["findings"]])

    def test_supplied_higher_tier_raises(self):
        self.assertEqual("T4", classify(base_descriptor(supplied_tier="T4")).to_dict()["tier"])

    def test_missing_reversibility_normal_warns_t2(self):
        value = base_descriptor()
        value.pop("reversibility")
        result = classify(value, "normal").to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual("T2", result["tier"])
        self.assertEqual("WARN", result["findings"][0]["severity"])

    def test_missing_reversibility_strict_holds(self):
        value = base_descriptor()
        value.pop("reversibility")
        result = classify(value, "strict").to_dict()
        self.assertEqual("HOLD", result["result"])

    def test_unknown_reversibility_normal_warns(self):
        result = classify(base_descriptor(reversibility="unknown"), "normal").to_dict()
        self.assertEqual("PASS", result["result"])

    def test_unknown_reversibility_strict_holds(self):
        result = classify(base_descriptor(reversibility="unknown"), "strict").to_dict()
        self.assertEqual("HOLD", result["result"])

    def test_alternate_casing_normalizes(self):
        result = classify(base_descriptor(action_class="EDIT", target_class="REPOSITORY", reversibility="REVERSIBLE")).to_dict()
        self.assertEqual("T1", result["tier"])

    def test_contradictory_descriptor_holds(self):
        result = classify(base_descriptor(mutation_requested=False)).to_dict()
        self.assertEqual("HOLD", result["result"])
        self.assertIn("RR03_CONTRADICTORY_DESCRIPTOR", [item["code"] for item in result["findings"]])

    def test_unknown_action_errors(self):
        self.assertIn("RR02_UNKNOWN_ENUM", [item["code"] for item in classify(base_descriptor(action_class="teleport")).to_dict()["findings"]])

    def test_unknown_target_errors(self):
        self.assertIn("RR02_UNKNOWN_ENUM", [item["code"] for item in classify(base_descriptor(target_class="moon")).to_dict()["findings"]])

    def test_unknown_effect_errors(self):
        self.assertIn("RR02_UNKNOWN_ENUM", [item["code"] for item in classify(base_descriptor(authority_effect="maybe")).to_dict()["findings"]])

    def test_unknown_version_errors(self):
        self.assertIn("IN02_UNSUPPORTED_VERSION", [item["code"] for item in classify(base_descriptor(schema_version="v99")).to_dict()["findings"]])

    def test_non_object_malformed(self):
        self.assertIn("RR05_MALFORMED_DESCRIPTOR", [item["code"] for item in classify([]).to_dict()["findings"]])

    def test_missing_required_fields(self):
        self.assertIn("RR05_MALFORMED_DESCRIPTOR", [item["code"] for item in classify({}).to_dict()["findings"]])

    def test_non_boolean_mutation(self):
        self.assertIn("RR05_MALFORMED_DESCRIPTOR", [item["code"] for item in classify(base_descriptor(mutation_requested="yes")).to_dict()["findings"]])

    def test_output_is_deterministic(self):
        first = json.dumps(classify(base_descriptor(authority_effect="replace")).to_dict(), ensure_ascii=False)
        second = json.dumps(classify(base_descriptor(authority_effect="replace")).to_dict(), ensure_ascii=False)
        self.assertEqual(first, second)

    def test_finding_schema_complete(self):
        result = classify(base_descriptor(action_class="unknown")).to_dict()
        self.assertEqual({"code", "severity", "path", "location", "message", "rule_version", "evidence"}, set(result["findings"][0]))

    def test_nested_unknown_structure_is_ignored(self):
        result = classify(base_descriptor(metadata={"credential": {"word_only": True}})).to_dict()
        self.assertEqual("T1", result["tier"])


if __name__ == "__main__":
    unittest.main()
