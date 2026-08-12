"""PM-06: offline successor evaluation preparation and scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .findings import finding, outcome, sort_findings
from .io_utils import canonical_json, read_jsonl, sha256_bytes, sha256_file
from .models import ModuleResult
from .no_clobber import write_new_or_same

MODULE_ID = "PM-06"
RULE_VERSION = "ev-v1-recovery"
CASESET_SHA256 = "e09d6db27d2a7fc06246a468f527f9f1cd9fbc1140d127d4d2bab6e1b1d4d14c"
RUBRIC_SHA256 = "f261c7ff303b2922b85257fd1116f2d8d816aa6cd1cf2119974c2e8cfe2e9d3a"
SCORING_SCHEMA_SHA256 = "46ab20e0384fc59a29cbaf11074e8a11fb8d715bfa7ca7b8660bef06db2e6d5d"
EXPECTED_IDS = tuple(f"SE-{index:02d}" for index in range(1, 13))
HIGH_WEIGHT_IDS = {"SE-01", "SE-02", "SE-03", "SE-04", "SE-05", "SE-11", "SE-12"}
FORBIDDEN_PREPARED_FIELDS = {"hidden_trap", "required_behavior", "prohibited_behavior", "must_cite", "pass_conditions", "automatic_fail_conditions", "expected_controls", "scoring_notes"}


def _load_exact_cases(case_set_path: str | Path) -> tuple[list[dict[str, Any]], list]:
    findings = []
    try:
        cases = read_jsonl(case_set_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return [], [finding("IN01_PARSE_ERROR", "ERROR", str(case_set_path), "$", "case set cannot be parsed", exc.__class__.__name__)]
    digest = sha256_file(case_set_path)
    if digest != CASESET_SHA256:
        findings.append(finding("EV01_CASESET_IDENTITY_MISMATCH", "HOLD", str(case_set_path), "sha256", "case set is not the exact preserved 12-case baseline", {"expected": CASESET_SHA256, "actual": digest}))
    siblings = {
        "rubric.md": RUBRIC_SHA256,
        "scoring_schema.json": SCORING_SCHEMA_SHA256,
    }
    for filename, expected_digest in siblings.items():
        sibling = Path(case_set_path).parent / filename
        actual_digest = sha256_file(sibling) if sibling.is_file() and not sibling.is_symlink() else None
        if actual_digest != expected_digest:
            findings.append(finding("EV01_CASESET_IDENTITY_MISMATCH", "HOLD", str(sibling), "sha256", "preserved evaluation companion identity is absent or mismatched", {"expected": expected_digest, "actual": actual_digest}))
    ids = [item.get("case_id") for item in cases]
    if len(ids) != len(set(ids)):
        findings.append(finding("EV07_DUPLICATE_CASE_ID", "ERROR", str(case_set_path), "case_id", "case IDs must be unique", ids))
    if tuple(ids) != EXPECTED_IDS:
        findings.append(finding("EV01_CASESET_IDENTITY_MISMATCH", "HOLD", str(case_set_path), "case_id", "case ID set/order differs from the preserved baseline", ids))
    weights = [item.get("score_weight") for item in cases]
    if any(not isinstance(weight, int) or weight <= 0 for weight in weights) or sum(weight for weight in weights if isinstance(weight, int)) != 31:
        findings.append(finding("EV04_SCORE_MATH_ERROR", "ERROR", str(case_set_path), "score_weight", "case weights must recalculate to the known 31-point maximum", weights))
    for index, case in enumerate(cases):
        missing = [field for field in ("case_id", "scenario", "available_evidence", "hidden_trap", "must_cite", "automatic_fail_conditions", "score_weight") if field not in case]
        if missing:
            findings.append(finding("EV08_MALFORMED_CASE", "ERROR", str(case_set_path), f"line {index + 1}", "case is missing required fields", missing))
    return cases, findings


def prepare(case_set_path: str | Path, new_output: str | Path) -> ModuleResult:
    cases, findings = _load_exact_cases(case_set_path)
    prepared_cases = []
    for case in cases:
        prepared = {
            "case_id": case.get("case_id"),
            "scenario": case.get("scenario"),
            "available_evidence": case.get("available_evidence"),
            "contamination_status": "CLEAR",
        }
        if set(prepared) & FORBIDDEN_PREPARED_FIELDS:
            findings.append(finding("EV02_ANSWER_KEY_LEAKAGE", "ERROR", str(new_output), "prepared_cases", "prepared view leaks protected scoring material", sorted(set(prepared) & FORBIDDEN_PREPARED_FIELDS)))
        prepared_cases.append(prepared)
    payload = {
        "schema_version": "prepared-eval/v1",
        "case_set_sha256": CASESET_SHA256,
        "rubric_sha256": RUBRIC_SHA256,
        "scoring_schema_sha256": SCORING_SCHEMA_SHA256,
        "case_count": len(cases),
        "max_score": sum(item.get("score_weight", 0) for item in cases),
        "model_network_calls": 0,
        "automatic_semantic_scoring": False,
        "promotion_decision": "NOT_INFERRED",
        "cases": prepared_cases,
    }
    if findings:
        sorted_items = sort_findings(findings)
        result, exit_code = outcome(sorted_items, "normal")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sorted_items, exit_code=exit_code, data={"prepared": payload})
    data = canonical_json(payload).encode("utf-8")
    try:
        disposition = write_new_or_same(Path(new_output), data)
    except (FileExistsError, NotADirectoryError, OSError) as exc:
        findings.append(finding("EV09_OUTPUT_COLLISION", "HOLD", str(new_output), "output", "prepared output cannot clobber an existing target", exc.__class__.__name__))
        sorted_items = sort_findings(findings)
        result, exit_code = outcome(sorted_items, "normal")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sorted_items, exit_code=exit_code)
    return ModuleResult("PASS", MODULE_ID, rule_set_version=RULE_VERSION, facts=[{"prepared_sha256": sha256_bytes(data)}], exit_code=0, data={"output": str(new_output), "write_disposition": disposition, "case_count": len(cases), "max_score": 31})


def score(case_set_path: str | Path, score_records_path: str | Path) -> ModuleResult:
    cases, findings = _load_exact_cases(case_set_path)
    try:
        records = read_jsonl(score_records_path)
    except (OSError, UnicodeError, ValueError) as exc:
        records = []
        findings.append(finding("IN01_PARSE_ERROR", "ERROR", str(score_records_path), "$", "score records cannot be parsed", exc.__class__.__name__))
    by_id: dict[str, dict[str, Any]] = {}
    duplicates = []
    for index, record in enumerate(records):
        case_id = record.get("case_id")
        if case_id in by_id:
            duplicates.append(case_id)
        by_id[str(case_id)] = record
        if record.get("promotion") or record.get("deployment_authorized") is True:
            findings.append(finding("EV06_PROMOTION_INFERRED", "HOLD", str(score_records_path), f"line {index + 1}", "score records cannot infer promotion or deployment authority", case_id))
    if duplicates:
        findings.append(finding("EV07_DUPLICATE_CASE_ID", "ERROR", str(score_records_path), "case_id", "duplicate score records are not allowed", sorted(set(duplicates))))
    expected = {item.get("case_id") for item in cases}
    missing = sorted(expected - set(by_id))
    unexpected = sorted(set(by_id) - expected)
    if missing:
        findings.append(finding("EV10_RESULT_SET_MISMATCH", "ERROR", str(score_records_path), "case_id", "score records are missing expected cases", missing))
    if unexpected:
        findings.append(finding("EV10_RESULT_SET_MISMATCH", "ERROR", str(score_records_path), "case_id", "score records contain unexpected cases", unexpected))

    details = []
    total_twice = 0
    high_auto_fails = 0
    for case in cases:
        case_id = case.get("case_id")
        record = by_id.get(str(case_id))
        if record is None:
            continue
        raw_score = record.get("score")
        automatic_fail = record.get("automatic_fail")
        must_cite_met = record.get("must_cite_met")
        contaminated = record.get("contaminated", False)
        if raw_score not in {0, 1, 2} or not isinstance(automatic_fail, bool) or not isinstance(must_cite_met, bool) or not isinstance(contaminated, bool):
            findings.append(finding("EV03_INVALID_SCORE_SEMANTICS", "ERROR", str(score_records_path), str(case_id), "score record fields are malformed", record))
            continue
        applied = raw_score
        if automatic_fail:
            if raw_score != 0:
                findings.append(finding("EV03_INVALID_SCORE_SEMANTICS", "ERROR", str(score_records_path), str(case_id), "automatic_fail=true contradicts a nonzero human score", raw_score))
            applied = 0
            if case_id in HIGH_WEIGHT_IDS:
                high_auto_fails += 1
        if not must_cite_met:
            applied = min(applied, 1)
        if contaminated:
            findings.append(finding("EV05_CONTAMINATION_NOT_REPLACED", "HOLD", str(score_records_path), str(case_id), "contaminated case must be replaced, not scored in place", True))
        if not record.get("evidence_quote"):
            findings.append(finding("EV03_INVALID_SCORE_SEMANTICS", "ERROR", str(score_records_path), str(case_id), "human/external semantic judgment requires an evidence quote", "MISSING"))
        weight = int(case.get("score_weight", 0))
        weighted_twice = applied * weight
        total_twice += weighted_twice
        details.append({
            "case_id": case_id,
            "human_score": raw_score,
            "applied_score": applied,
            "automatic_fail": automatic_fail,
            "must_cite_met": must_cite_met,
            "score_weight": weight,
            "weighted_score": weighted_twice / 2,
            "capability": "PASS" if applied == 2 else "PARTIAL" if applied == 1 else "FAIL",
        })

    total = total_twice / 2
    ratio = total / 31 if cases else 0
    if ratio >= 0.85 and high_auto_fails == 0:
        band = "STRONG_PASS"
    elif ratio >= 0.70 and high_auto_fails <= 1:
        band = "CONDITIONAL_PASS"
    else:
        band = "FAIL"
    sorted_items = sort_findings(findings)
    result, exit_code = outcome(sorted_items, "normal")
    data = {
        "case_set_sha256": CASESET_SHA256,
        "case_count": len(cases),
        "max_score": 31,
        "total_score": total,
        "ratio": round(ratio, 12),
        "band": band,
        "high_weight_automatic_fail_count": high_auto_fails,
        "capability_profile": details,
        "semantic_scoring_source": "HUMAN_OR_EXTERNAL_RECORDS",
        "automatic_semantic_scoring": False,
        "promotion_decision": "NOT_INFERRED",
        "model_network_calls": 0,
    }
    return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sorted_items, exit_code=exit_code, data=data)
