"""PM-01: deterministic effect-based risk routing."""

from __future__ import annotations

from typing import Any

from .findings import finding, outcome, sort_findings
from .models import ModuleResult

MODULE_ID = "PM-01"
RULE_VERSION = "rr-v1-recovery"
TIERS = ("T0", "T1", "T2", "T3", "T4")

ALLOWED_ACTIONS = {
    "read",
    "analyze",
    "summarize",
    "edit",
    "create",
    "delete",
    "replace",
    "rotate",
    "expose",
    "reopen",
    "supersede",
    "overturn",
    "permission_change",
    "deploy",
    "execute",
}
ALLOWED_TARGETS = {
    "local_document",
    "repository",
    "artifact",
    "corpus",
    "production",
    "credential",
    "identity",
    "canonical_authority",
    "user_data",
}
ALLOWED_REVERSIBILITY = {"reversible", "irreversible", "unknown", "not_applicable"}

CONTROLS = {
    "T0": ["confirm_target"],
    "T1": ["review_diff", "run_relevant_tests", "retain_revert_path"],
    "T2": ["enumerate_affected_objects", "record_pre_post_assertions", "prove_recovery_path"],
    "T3": [
        "exact_object_allowlist",
        "preserve_before_mutation",
        "close_all_preconditions",
        "object_bound_zrn_authorization",
        "single_writer",
        "independent_review",
        "closeout",
    ],
    "T4": [
        "freeze_corpus",
        "bind_old_and_new_identities",
        "independent_review",
        "zrn_own_voice_object_bound_approval",
        "append_only_supersession",
    ],
}
UNNECESSARY = {
    "T0": ["hash_ledger", "corpus_manifest", "dry_run", "closeout", "independent_review"],
    "T1": ["corpus_freeze", "preservation_bundle", "object_bound_authorization", "cold_review"],
    "T2": ["full_parent_chain_proof", "full_preservation_bundle"],
    "T3": ["web_ui", "daemon", "whole_machine_scan", "unrelated_governance_layer"],
    "T4": ["in_place_authority_rewrite", "automatic_promotion"],
}


def _normalize_effect(value: Any) -> str:
    if value is True:
        return "modify"
    if value is False or value is None:
        return "none"
    return str(value).strip().lower()


def _tier_max(first: str, second: str) -> str:
    return TIERS[max(TIERS.index(first), TIERS.index(second))]


def classify(task_descriptor: Any, profile: str = "normal") -> ModuleResult:
    findings = []
    if profile not in {"normal", "strict"}:
        findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", "$", "profile", "unsupported profile", profile))
        result, exit_code = outcome(findings, "normal")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sort_findings(findings), exit_code=exit_code)
    if not isinstance(task_descriptor, dict):
        findings.append(finding("RR05_MALFORMED_DESCRIPTOR", "ERROR", "$", "$", "descriptor must be an object", type(task_descriptor).__name__))
        result, exit_code = outcome(findings, profile)
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sort_findings(findings), exit_code=exit_code)
    schema = task_descriptor.get("schema_version", "risk-descriptor/v1")
    if schema != "risk-descriptor/v1":
        findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", "$", "schema_version", "unsupported risk descriptor version", schema))

    required = (
        "task_id",
        "action_class",
        "target_class",
        "mutation_requested",
        "production_effect",
        "credential_or_identity_effect",
        "authority_effect",
        "recovery_path",
    )
    missing = [name for name in required if name not in task_descriptor]
    if missing:
        findings.append(finding("RR05_MALFORMED_DESCRIPTOR", "ERROR", "$", "required", "required descriptor fields are missing", missing))

    action = str(task_descriptor.get("action_class", "")).strip().lower()
    target = str(task_descriptor.get("target_class", "")).strip().lower()
    reversibility_raw = task_descriptor.get("reversibility")
    reversibility = str(reversibility_raw).strip().lower() if reversibility_raw is not None else ""
    if action and action not in ALLOWED_ACTIONS:
        findings.append(finding("RR02_UNKNOWN_ENUM", "ERROR", "$", "action_class", "unknown action class", action))
    if target and target not in ALLOWED_TARGETS:
        findings.append(finding("RR02_UNKNOWN_ENUM", "ERROR", "$", "target_class", "unknown target class", target))
    if reversibility and reversibility not in ALLOWED_REVERSIBILITY:
        findings.append(finding("RR02_UNKNOWN_ENUM", "ERROR", "$", "reversibility", "unknown reversibility", reversibility))

    mutation = task_descriptor.get("mutation_requested")
    if not isinstance(mutation, bool):
        findings.append(finding("RR05_MALFORMED_DESCRIPTOR", "ERROR", "$", "mutation_requested", "mutation_requested must be Boolean", mutation))
        mutation = bool(mutation)

    modifying_action = action in {
        "edit", "create", "delete", "replace", "rotate", "expose", "reopen",
        "supersede", "overturn", "permission_change", "deploy", "execute",
    }
    if modifying_action and not mutation:
        findings.append(finding("RR03_CONTRADICTORY_DESCRIPTOR", "HOLD", "$", "mutation_requested", "action effect contradicts mutation_requested=false", action))

    tier = "T0"
    base_reason = "read-only or local reversible work with no protected effect"
    triggers: list[str] = []
    deescalation: list[str] = []

    if mutation:
        if target == "repository" and reversibility == "reversible":
            tier, base_reason = "T1", "version-controlled reversible repository mutation"
        else:
            tier, base_reason = "T2", "bounded mutation requiring pre/post and recovery controls"

    credential_effect = _normalize_effect(task_descriptor.get("credential_or_identity_effect"))
    authority_effect = _normalize_effect(task_descriptor.get("authority_effect"))
    production_effect = _normalize_effect(task_descriptor.get("production_effect"))

    credential_mutations = {"modify", "write", "expose", "rotate", "delete", "revoke", "create"}
    authority_mutations = {"replace", "supersede", "reopen", "overturn", "promote", "retire"}
    production_mutations = {"modify", "write", "deploy", "delete", "restart", "execute"}
    read_effects = {"none", "read", "describe", "document", "summarize", "inspect"}

    if credential_effect not in read_effects | credential_mutations:
        findings.append(finding("RR02_UNKNOWN_ENUM", "ERROR", "$", "credential_or_identity_effect", "unknown credential/identity effect", credential_effect))
    if authority_effect not in read_effects | authority_mutations:
        findings.append(finding("RR02_UNKNOWN_ENUM", "ERROR", "$", "authority_effect", "unknown authority effect", authority_effect))
    if production_effect not in read_effects | production_mutations:
        findings.append(finding("RR02_UNKNOWN_ENUM", "ERROR", "$", "production_effect", "unknown production effect", production_effect))

    if credential_effect in credential_mutations:
        tier = _tier_max(tier, "T3")
        triggers.append("LIVE_CREDENTIAL_OR_IDENTITY_MUTATION")
        base_reason = "live credential or identity effect has a T3 mechanical floor"
    if production_effect in production_mutations:
        tier = _tier_max(tier, "T3")
        triggers.append("PRODUCTION_MUTATION")
        base_reason = "production mutation has a T3 mechanical floor"
    if authority_effect in authority_mutations:
        tier = "T4"
        triggers.append("CANONICAL_AUTHORITY_OR_REOPEN_EFFECT")
        base_reason = "canonical authority change or reopen has a T4 mechanical floor"
    if reversibility == "irreversible" and mutation:
        tier = _tier_max(tier, "T3")
        triggers.append("IRREVERSIBLE_MUTATION")
        base_reason = "irreversible mutation has a T3 mechanical floor"
    if mutation and reversibility in {"", "unknown"}:
        tier = _tier_max(tier, "T2")
        severity = "HOLD" if profile == "strict" else "WARN"
        findings.append(finding("RR01_MISSING_REVERSIBILITY", severity, "$", "reversibility", "mutation reversibility is not established", reversibility or "MISSING"))
    if not mutation and reversibility in {"reversible", "not_applicable", ""}:
        deescalation.append("NO_MUTATION_EFFECT")
    if credential_effect in read_effects:
        deescalation.append("CREDENTIAL_REFERENCE_IS_READ_ONLY")
    if authority_effect in read_effects:
        deescalation.append("AUTHORITY_REFERENCE_IS_READ_ONLY")

    supplied = task_descriptor.get("supplied_tier")
    if supplied is not None:
        supplied = str(supplied).upper()
        if supplied not in TIERS:
            findings.append(finding("RR02_UNKNOWN_ENUM", "ERROR", "$", "supplied_tier", "unknown supplied tier", supplied))
        elif TIERS.index(supplied) < TIERS.index(tier):
            findings.append(finding("RR04_TIER_FLOOR_OVERRIDE", "WARN", "$", "supplied_tier", "supplied tier cannot lower the mechanical floor", {"supplied": supplied, "floor": tier}))
        else:
            tier = supplied
            triggers.append("USER_SUPPLIED_HIGHER_TIER")

    sorted_items = sort_findings(findings)
    result, exit_code = outcome(sorted_items, profile)
    data = {
        "tier": tier,
        "base_reason": base_reason,
        "escalation_triggers": sorted(set(triggers)),
        "deescalation_evidence": sorted(set(deescalation)),
        "required_controls": CONTROLS[tier],
        "explicitly_unnecessary": UNNECESSARY[tier],
        "human_decision_required": tier in {"T3", "T4"},
        "classification_is_authorization": False,
    }
    return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sorted_items, exit_code=exit_code, data=data)
