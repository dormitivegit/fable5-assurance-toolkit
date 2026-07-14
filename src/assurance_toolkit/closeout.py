"""PM-05 deterministic closeout validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .findings import finding, outcome, sort_findings
from .io_utils import read_json
from .models import ModuleResult

MODULE_ID = "PM-05"
RULE_VERSION = "hc-v1-recovery"
FINAL_RESULT = re.compile(r"^(PASS|FAIL|HOLD)_[A-Z0-9_]+$")
TERMINAL_STATES = {"CLOSED", "ACCEPTED", "RETIRED", "HOLD", "OPEN"}


def validate_closeout(path: str | Path, profile: str = "normal", guard_receipt: str | Path | dict[str, Any] | None = None) -> ModuleResult:
    findings = []
    try:
        document = read_json(path)
    except (OSError, UnicodeError, ValueError) as exc:
        findings.append(finding("IN01_PARSE_ERROR", "ERROR", str(path), "$", "closeout cannot be parsed", exc.__class__.__name__))
        result, exit_code = outcome(findings, profile)
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sort_findings(findings), exit_code=exit_code)
    if not isinstance(document, dict):
        findings.append(finding("IN01_PARSE_ERROR", "ERROR", str(path), "$", "closeout must be an object", type(document).__name__))
        document = {}
    if document.get("schema_version") != "closeout/v1":
        findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", str(path), "schema_version", "unsupported closeout version", document.get("schema_version")))
    final_result = str(document.get("final_result", ""))
    if not FINAL_RESULT.fullmatch(final_result) or any(word in final_result for word in ("PARTIAL", "MOSTLY", "LIKELY", "GENERALLY")):
        findings.append(finding("HC20_AMBIGUOUS_RESULT", "ERROR", str(path), "final_result", "final result must use a closed unambiguous PASS/FAIL/HOLD vocabulary", final_result))
    terminal_state = str(document.get("terminal_state", "")).upper()
    if terminal_state not in TERMINAL_STATES:
        findings.append(finding("HC20_AMBIGUOUS_RESULT", "ERROR", str(path), "terminal_state", "unsupported or missing terminal state", terminal_state))
    assertions = document.get("expected_assertions")
    if not isinstance(assertions, dict) or not assertions or any(value is not True for value in assertions.values()):
        findings.append(finding("HC21_TARGET_ASSERTION_MISSING", "ERROR", str(path), "expected_assertions", "target-level positive assertions must all pass", assertions))
    actions = document.get("actions", [])
    executed_mutations = sum(1 for action in actions if isinstance(action, dict) and action.get("executed") is True and action.get("mutates") is True)
    mutation_count = document.get("source_mutation_count")
    if not isinstance(mutation_count, int) or mutation_count < 0 or mutation_count != executed_mutations:
        findings.append(finding("HC22_MUTATION_MISMATCH", "ERROR", str(path), "source_mutation_count", "declared source mutation count must match executed mutation actions", {"declared": mutation_count, "observed": executed_mutations}))
    authorizations = {item.get("id"): item for item in document.get("authorizations", []) if isinstance(item, dict)}
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or not action.get("executed") or not action.get("mutates"):
            continue
        auth = authorizations.get(action.get("authorization_ref"))
        if not auth or auth.get("state") != "AUTHORIZED" or auth.get("decider") != "ZRN" or auth.get("object_identity") != action.get("object_identity"):
            findings.append(finding("HC22_MUTATION_MISMATCH", "HOLD", str(path), f"actions[{index}]", "mutation does not reconcile to exact ZRN authorization", action.get("authorization_ref")))
    if document.get("source_pre_post_match") != "YES":
        findings.append(finding("HC23_SOURCE_INTEGRITY_UNPROVEN", "ERROR", str(path), "source_pre_post_match", "source pre/post identity is not proven", document.get("source_pre_post_match")))
    if document.get("output_self_ingestion_count") != 0:
        findings.append(finding("HC23_SOURCE_INTEGRITY_UNPROVEN", "ERROR", str(path), "output_self_ingestion_count", "output self-ingestion must be zero", document.get("output_self_ingestion_count")))
    if not document.get("stop_conditions"):
        findings.append(finding("HC25_STOP_CONDITION_MISSING", "ERROR", str(path), "stop_conditions", "closeout must record stop conditions", document.get("stop_conditions")))
    artifact = document.get("artifact_identity")
    if not isinstance(artifact, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256", ""))):
        findings.append(finding("HC21_TARGET_ASSERTION_MISSING", "ERROR", str(path), "artifact_identity", "artifact identity requires a full SHA-256", artifact))

    if guard_receipt is not None:
        try:
            receipt = read_json(guard_receipt) if not isinstance(guard_receipt, dict) else guard_receipt
        except (OSError, UnicodeError, ValueError) as exc:
            receipt = None
            findings.append(finding("HC24_GUARD_CONFLICT", "HOLD", str(path), "guard_receipt", "guard receipt cannot be parsed", exc.__class__.__name__))
        if not isinstance(receipt, dict) or receipt.get("plan") not in {"CREATE_NEW_ATOMICALLY", "IDEMPOTENT_NOOP"} or receipt.get("target_sha256") != (artifact or {}).get("sha256"):
            findings.append(finding("HC24_GUARD_CONFLICT", "HOLD", str(path), "guard_receipt", "guard receipt does not authorize the exact target identity", receipt))
    elif document.get("collision_or_rerun_possible") is True:
        findings.append(finding("HC24_GUARD_CONFLICT", "HOLD", str(path), "collision_or_rerun_possible", "collision/rerun risk requires an exact guard receipt", True))

    sorted_items = sort_findings(findings)
    result, exit_code = outcome(sorted_items, profile)
    return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sorted_items, facts=[{"deterministic_validation": True}], exit_code=exit_code)
