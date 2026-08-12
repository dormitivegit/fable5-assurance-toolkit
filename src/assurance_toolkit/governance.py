"""PM-02: governance pack validation without business-truth adjudication."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .findings import finding, outcome, sort_findings
from .identities import normalize_authority_identity
from .io_utils import exact_source_resolves
from .models import ModuleResult

MODULE_ID = "PM-02"
RULE_VERSION = "gp-v1-recovery"
SUPPORTED_VERSIONS = {"governance-pack/v1", "1.0"}
AUTH_STATES = {"AUTHORIZED", "USER_AUTHORIZATION"}
NON_AUTH_STATES = {"RECOMMENDED", "PROPOSED", "PROPOSED_PENDING_APPROVAL", "NOT_AUTHORIZED", "REJECTED", "SUPERSEDED"}


def _claim_id(claim: dict[str, Any], index: int) -> str:
    return str(claim.get("id") or claim.get("claim_id") or f"claim[{index}]")


def _decision_id(decision: dict[str, Any], index: int) -> str:
    return str(decision.get("id") or decision.get("decision_id") or f"decision[{index}]")


def _action_id(action: dict[str, Any], index: int) -> str:
    return str(action.get("id") or action.get("action_id") or f"action[{index}]")


def check(
    pack: Any,
    profile: str = "normal",
    source_resolver=exact_source_resolves,
    authority_identity: str | None = None,
) -> ModuleResult:
    findings = []
    expected_authority = normalize_authority_identity(authority_identity)
    if profile not in {"normal", "strict"}:
        findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", "$", "profile", "unsupported profile", profile))
        profile = "normal"
    if not isinstance(pack, dict):
        findings.append(finding("IN01_PARSE_ERROR", "ERROR", "$", "$", "governance pack must be an object", type(pack).__name__))
        result, exit_code = outcome(findings, profile)
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sort_findings(findings), exit_code=exit_code)
    version = pack.get("pack_version") or pack.get("schema_version")
    if version not in SUPPORTED_VERSIONS:
        findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", "$", "pack_version", "unsupported governance pack version", version))

    claims = pack.get("claims", [])
    decisions = pack.get("decisions", [])
    actions = pack.get("actions", [])
    task = pack.get("task", {})
    for name, value in (("claims", claims), ("decisions", decisions), ("actions", actions)):
        if not isinstance(value, list):
            findings.append(finding("IN01_PARSE_ERROR", "ERROR", "$", name, f"{name} must be a list", type(value).__name__))
    if not isinstance(task, dict):
        findings.append(finding("IN01_PARSE_ERROR", "ERROR", "$", "task", "task must be an object", type(task).__name__))
    if any(not isinstance(value, list) for value in (claims, decisions, actions)) or not isinstance(task, dict):
        result, exit_code = outcome(findings, profile)
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sort_findings(findings), exit_code=exit_code)

    load_bearing_problem = False
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            findings.append(finding("IN01_PARSE_ERROR", "ERROR", "$", f"claims[{index}]", "claim must be an object", type(claim).__name__))
            continue
        cid = _claim_id(claim, index)
        load_bearing = bool(claim.get("load_bearing"))
        verification = str(claim.get("verification") or claim.get("evidence_class") or "").upper()
        identity = claim.get("source_identity")
        if identity is None and claim.get("source_path"):
            identity = {"path": claim.get("source_path"), "sha256": claim.get("source_sha256")}
        location = claim.get("location") or claim.get("location_anchor")
        if load_bearing and verification in {"VERIFIED", "VERIFIED_FACT", "USER_ADJUDICATION", "USER_DECISION", "USER_AUTHORIZATION"}:
            if not identity or not location:
                load_bearing_problem = True
                findings.append(finding("GP01_MISSING_EVIDENCE", "ERROR", cid, "source", "verified load-bearing claim needs exact source identity and location", {"identity_present": bool(identity), "location_present": bool(location)}))
            else:
                resolved, evidence = source_resolver(identity, location)
                if not resolved:
                    load_bearing_problem = True
                    findings.append(finding("GP05_BROKEN_EVIDENCE_REFERENCE", "ERROR", cid, "source", "load-bearing evidence reference does not resolve", evidence))
        elif load_bearing and verification in {"", "UNVERIFIED", "UNKNOWN"}:
            load_bearing_problem = True
            findings.append(finding("GP02_UNVERIFIED_LOAD_BEARING_CLAIM", "ERROR", cid, "verification", "load-bearing claim is unverified", verification or "MISSING"))
        if str(claim.get("conflict", claim.get("conflict_state", "NONE"))).upper() == "UNRESOLVED":
            load_bearing_problem = True
            findings.append(finding("GP04_UNRESOLVED_AUTHORITY_CONFLICT", "HOLD", cid, "conflict", "claim has an unresolved load-bearing conflict", "UNRESOLVED"))

    decision_by_id: dict[str, dict[str, Any]] = {}
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            findings.append(finding("IN01_PARSE_ERROR", "ERROR", "$", f"decisions[{index}]", "decision must be an object", type(decision).__name__))
            continue
        did = _decision_id(decision, index)
        decision_by_id[did] = decision
        subject = str(decision.get("subject") or decision.get("subject_key") or "")
        by_subject[subject].append(decision)
    for subject, group in sorted(by_subject.items()):
        superseded = {str(item.get("supersedes")) for item in group if item.get("supersedes")}
        live = [item for item in group if _decision_id(item, 0) not in superseded and str(item.get("state", "")).upper() != "SUPERSEDED"]
        states = {str(item.get("state", "")).upper() for item in live}
        positive = bool(states & {"AUTHORIZED", "USER_AUTHORIZATION", "ACCEPTED", "ADJUDICATED", "CANONICAL"})
        negative = bool(states & {"NOT_AUTHORIZED", "REJECTED"})
        if positive and negative:
            load_bearing_problem = True
            findings.append(finding("GP04_UNRESOLVED_AUTHORITY_CONFLICT", "HOLD", subject or "<missing-subject>", "decisions", "mutually exclusive live authority states lack resolvable supersession", sorted(states)))

    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            findings.append(finding("IN01_PARSE_ERROR", "ERROR", "$", f"actions[{index}]", "action must be an object", type(action).__name__))
            continue
        aid = _action_id(action, index)
        executed = bool(action.get("executed"))
        mutates = bool(action.get("mutates", action.get("mutates_source", False)))
        if executed and mutates:
            ref = action.get("authorization_ref")
            decision = decision_by_id.get(str(ref)) if ref is not None else None
            state = str((decision or {}).get("state", "")).upper()
            decider = normalize_authority_identity((decision or {}).get("decider") or (decision or {}).get("decided_by"))
            authorized_object = (decision or {}).get("object_identity")
            action_object = action.get("object_identity")
            if decision is None or state not in AUTH_STATES or not expected_authority or decider != expected_authority or not action_object or authorized_object != action_object:
                load_bearing_problem = True
                findings.append(finding("GP03_UNAUTHORIZED_ACTION", "HOLD", aid, "authorization_ref", "executed mutation lacks exact expected-authority authorization bound to the same object", {"authorization_resolved": decision is not None, "state": state, "decider": decider, "expected_authority_supplied": bool(expected_authority), "authority_matches": bool(expected_authority and decider == expected_authority), "object_matches": bool(action_object and authorized_object == action_object)}))

    declared_result = str(pack.get("result") or task.get("result") or "")
    if declared_result.startswith("PASS") and load_bearing_problem:
        findings.append(finding("GP06_FALSE_PASS_ASSERTION", "ERROR", "$", "result", "PASS cannot coexist with unresolved load-bearing findings", declared_result))

    sorted_items = sort_findings(findings)
    result, exit_code = outcome(sorted_items, profile)
    facts = [
        {"claims_checked": len(claims)},
        {"decisions_checked": len(decisions)},
        {"actions_checked": len(actions)},
        {"business_truth_adjudicated": False},
        {"source_resolution_mode": "EXACT_REFERENCE_ONLY"},
    ]
    return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sorted_items, facts=facts, exit_code=exit_code)
