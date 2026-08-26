import json
import tempfile
import unittest
from pathlib import Path

from software_evidence_controls.evaluation import CASESET_SHA256, prepare, score
from software_evidence_controls.identities import file_identity
from software_evidence_controls.io_utils import read_jsonl, sha256_file


REPOSITORY = Path(__file__).resolve().parents[1]
CASES = REPOSITORY / "contracts" / "successor-eval" / "cases.jsonl"


class EvaluationFixtureMixin:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write_scores(self, overrides=None, omit=None, extra=None):
        overrides = overrides or {}
        omit = set(omit or [])
        records = []
        for index in range(1, 13):
            case_id = f"SE-{index:02d}"
            if case_id in omit:
                continue
            record = {
                "case_id": case_id,
                "score": 2,
                "automatic_fail": False,
                "must_cite_met": True,
                "evidence_quote": f"synthetic evidence quote {case_id}",
                "contaminated": False,
            }
            record.update(overrides.get(case_id, {}))
            records.append(record)
        records.extend(extra or [])
        path = self.root / f"scores-{len(list(self.root.glob('scores-*')))}.jsonl"
        path.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in records), encoding="utf-8")
        return path


class EvaluationPrepareTests(EvaluationFixtureMixin, unittest.TestCase):
    def test_preserved_case_set_hash(self):
        self.assertEqual(CASESET_SHA256, sha256_file(CASES))

    def test_prepare_positive(self):
        output = self.root / "prepared.json"
        result = prepare(CASES, output).to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual(12, result["case_count"])
        self.assertEqual(31, result["max_score"])

    def test_prepare_answer_key_isolation(self):
        output = self.root / "prepared.json"
        prepare(CASES, output)
        value = json.loads(output.read_text(encoding="utf-8"))
        forbidden = {"hidden_trap", "required_behavior", "prohibited_behavior", "must_cite", "pass_conditions", "automatic_fail_conditions", "expected_controls", "scoring_notes"}
        self.assertTrue(all(not (set(item) & forbidden) for item in value["cases"]))

    def test_prepare_freezes_contract_identities(self):
        output = self.root / "prepared.json"
        prepare(CASES, output)
        value = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(CASESET_SHA256, value["case_set_sha256"])
        self.assertEqual(64, len(value["rubric_sha256"]))
        self.assertEqual(64, len(value["scoring_schema_sha256"]))

    def test_prepare_is_byte_deterministic(self):
        first = self.root / "first.json"
        second = self.root / "second.json"
        prepare(CASES, first)
        prepare(CASES, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_prepare_same_hash_noop_untouched(self):
        output = self.root / "prepared.json"
        prepare(CASES, output)
        before = file_identity(output)
        result = prepare(CASES, output).to_dict()
        self.assertEqual("IDEMPOTENT_NOOP", result["write_disposition"])
        self.assertEqual(before, file_identity(output))

    def test_prepare_different_output_collision_holds(self):
        output = self.root / "prepared.json"
        output.write_text("incumbent", encoding="utf-8")
        before = file_identity(output)
        result = prepare(CASES, output).to_dict()
        self.assertIn("EV09_OUTPUT_COLLISION", [item["code"] for item in result["findings"]])
        self.assertEqual(before, file_identity(output))

    def test_prepare_preserves_case_set_bytes(self):
        before = file_identity(CASES)
        prepare(CASES, self.root / "prepared.json")
        self.assertEqual(before, file_identity(CASES))

    def test_duplicate_case_id_rejected(self):
        records = read_jsonl(CASES)
        records[-1]["case_id"] = "SE-01"
        path = self.root / "duplicate.jsonl"
        path.write_text("".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in records), encoding="utf-8")
        result = prepare(path, self.root / "out.json").to_dict()
        self.assertIn("EV07_DUPLICATE_CASE_ID", [item["code"] for item in result["findings"]])

    def test_known_30_point_weight_regression_rejected(self):
        records = read_jsonl(CASES)
        records[0]["score_weight"] = 2
        path = self.root / "weight30.jsonl"
        path.write_text("".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in records), encoding="utf-8")
        result = prepare(path, self.root / "out.json").to_dict()
        self.assertIn("EV04_SCORE_MATH_ERROR", [item["code"] for item in result["findings"]])

    def test_missing_case_field_rejected(self):
        records = read_jsonl(CASES)
        records[0].pop("must_cite")
        path = self.root / "malformed.jsonl"
        path.write_text("".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in records), encoding="utf-8")
        result = prepare(path, self.root / "out.json").to_dict()
        self.assertIn("EV08_MALFORMED_CASE", [item["code"] for item in result["findings"]])

    def test_case_set_byte_drift_holds(self):
        path = self.root / "drift.jsonl"
        path.write_bytes(CASES.read_bytes() + b"\n")
        result = prepare(path, self.root / "out.json").to_dict()
        self.assertIn("EV01_CASESET_IDENTITY_MISMATCH", [item["code"] for item in result["findings"]])

    def test_rubric_byte_drift_holds(self):
        case_path = self.root / "cases.jsonl"
        rubric = self.root / "rubric.md"
        schema = self.root / "scoring_schema.json"
        case_path.write_bytes(CASES.read_bytes())
        rubric.write_text("wrong rubric", encoding="utf-8")
        schema.write_bytes((CASES.parent / "scoring_schema.json").read_bytes())
        result = prepare(case_path, self.root / "out.json").to_dict()
        self.assertIn("EV01_CASESET_IDENTITY_MISMATCH", [item["code"] for item in result["findings"]])


class EvaluationScoreTests(EvaluationFixtureMixin, unittest.TestCase):
    def test_all_pass_scores_31_strong(self):
        result = score(CASES, self.write_scores()).to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual(31, result["total_score"])
        self.assertEqual("STRONG_PASS", result["band"])

    def test_all_fail_scores_zero(self):
        overrides = {f"SE-{index:02d}": {"score": 0} for index in range(1, 13)}
        result = score(CASES, self.write_scores(overrides)).to_dict()
        self.assertEqual(0, result["total_score"])
        self.assertEqual("FAIL", result["band"])

    def test_must_cite_cap_is_enforced(self):
        result = score(CASES, self.write_scores({"SE-01": {"must_cite_met": False}})).to_dict()
        first = result["capability_profile"][0]
        self.assertEqual(1, first["applied_score"])
        self.assertEqual(29.5, result["total_score"])

    def test_automatic_fail_forces_zero(self):
        result = score(CASES, self.write_scores({"SE-01": {"score": 0, "automatic_fail": True}})).to_dict()
        self.assertEqual(28, result["total_score"])
        self.assertEqual(1, result["high_weight_automatic_fail_count"])

    def test_automatic_fail_nonzero_is_contradictory(self):
        result = score(CASES, self.write_scores({"SE-01": {"automatic_fail": True}})).to_dict()
        self.assertIn("EV03_INVALID_SCORE_SEMANTICS", [item["code"] for item in result["findings"]])

    def test_missing_case_rejected(self):
        result = score(CASES, self.write_scores(omit=["SE-12"])).to_dict()
        self.assertIn("EV10_RESULT_SET_MISMATCH", [item["code"] for item in result["findings"]])

    def test_duplicate_score_rejected(self):
        duplicate = {"case_id": "SE-01", "score": 2, "automatic_fail": False, "must_cite_met": True, "evidence_quote": "duplicate", "contaminated": False}
        result = score(CASES, self.write_scores(extra=[duplicate])).to_dict()
        self.assertIn("EV07_DUPLICATE_CASE_ID", [item["code"] for item in result["findings"]])

    def test_unexpected_case_rejected(self):
        extra = {"case_id": "SE-99", "score": 2, "automatic_fail": False, "must_cite_met": True, "evidence_quote": "unexpected", "contaminated": False}
        result = score(CASES, self.write_scores(extra=[extra])).to_dict()
        self.assertIn("EV10_RESULT_SET_MISMATCH", [item["code"] for item in result["findings"]])

    def test_malformed_score_rejected(self):
        result = score(CASES, self.write_scores({"SE-01": {"score": 3}})).to_dict()
        self.assertIn("EV03_INVALID_SCORE_SEMANTICS", [item["code"] for item in result["findings"]])

    def test_missing_evidence_quote_rejected(self):
        result = score(CASES, self.write_scores({"SE-01": {"evidence_quote": ""}})).to_dict()
        self.assertIn("EV03_INVALID_SCORE_SEMANTICS", [item["code"] for item in result["findings"]])

    def test_contamination_holds(self):
        result = score(CASES, self.write_scores({"SE-01": {"contaminated": True}})).to_dict()
        self.assertIn("EV05_CONTAMINATION_NOT_REPLACED", [item["code"] for item in result["findings"]])

    def test_promotion_inference_holds(self):
        result = score(CASES, self.write_scores({"SE-01": {"promotion": "CANONICAL"}})).to_dict()
        self.assertIn("EV06_PROMOTION_INFERRED", [item["code"] for item in result["findings"]])

    def test_score_output_is_deterministic(self):
        path = self.write_scores({"SE-03": {"score": 1}})
        self.assertEqual(json.dumps(score(CASES, path).to_dict()), json.dumps(score(CASES, path).to_dict()))

    def test_capability_profile_has_all_twelve(self):
        result = score(CASES, self.write_scores()).to_dict()
        self.assertEqual(12, len(result["capability_profile"]))

    def test_no_model_or_promotion_decision(self):
        result = score(CASES, self.write_scores()).to_dict()
        self.assertEqual(0, result["model_network_calls"])
        self.assertFalse(result["automatic_semantic_scoring"])
        self.assertEqual("NOT_INFERRED", result["promotion_decision"])


if __name__ == "__main__":
    unittest.main()
