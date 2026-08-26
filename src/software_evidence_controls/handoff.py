"""PM-05 handoff structural/authority observations against exact carrier identities."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .findings import finding, outcome, sort_findings
from .io_utils import exact_source_resolves
from .models import ModuleResult

MODULE_ID = "PM-05"
RULE_VERSION = "hc-v1-recovery"
REVIEW_KERNEL_SHA256 = "49bc4a1c9b64ec22802210fe5d2e017c950f7c703c6d03776326f6f989aac842"
DIRECT_CARRIER_SHA256 = "d3d88db56c9ed8c6957a323780d53daff9383215492358f7e74f4865d0a2aa49"
SKILL_PACKAGE_SHA256 = "83c6b4895f0d4867b85e6efc6c9e0b54da2602b49f6a7d8bf50dc8ef8386e610"
SKILL_RUNTIME_SHA256 = "80b6735aa824d2a1976401c4ebcb1379f06bf40fbb005bac30239d03b80def52"
SUPPORTED_CARRIERS = {
    "direct-v1-ax1-ax2": {"carrier_sha256": DIRECT_CARRIER_SHA256},
    "skill-v1-candidate-ax1-ax2": {"carrier_sha256": SKILL_PACKAGE_SHA256, "runtime_sha256": SKILL_RUNTIME_SHA256},
}
AUTHORITY_VOCABULARY = {
    "ADJUDICATED", "AUTHORIZED", "NOT_AUTHORIZED", "REJECTED", "SUPERSEDED",
    "ACCEPTED", "VALIDATED", "CANONICAL", "INSTALLED",
}
CORE_AUTHORITY_STATES = {"ADJUDICATED", "AUTHORIZED", "NOT_AUTHORIZED", "REJECTED"}
DIMENSIONS = ("summary", "technical", "state", "task", "development", "facts_evidence")
CONTEXT_DEPENDENT = ("as above", "see previous", "same as before", "同上", "参考上文", "沿用前文")


def _load_document(path: str | Path) -> tuple[Any, str]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text), text
    except json.JSONDecodeError:
        return None, text


def _markdown_observation(text: str) -> dict[str, Any]:
    lower = text.lower()
    synonyms = {
        "summary": ("summary", "摘要", "概述", "receiver immediate brief"),
        "technical": ("technical", "技术", "architecture", "路线"),
        "state": ("state", "状态", "sot", "completed"),
        "task": ("task", "任务", "next action", "first actions"),
        "development": ("development", "future", "发展", "future direction"),
        "facts_evidence": ("evidence", "facts", "证据", "hash", "sha256"),
    }
    dimensions = {name: any(token in lower for token in tokens) for name, tokens in synonyms.items()}
    states = sorted(state for state in AUTHORITY_VOCABULARY if state.lower() in lower)
    metadata = {}
    for key in ("CARRIER_SHA256", "RUNTIME_SHA256", "CARRIER_IDENTITY"):
        match = re.search(rf"(?m)^\s*{key}\s*=\s*([^\s]+)\s*$", text)
        if match:
            metadata[key.lower()] = match.group(1)
    return {
        "schema_version": "handoff-observation/v1",
        "dimensions": dimensions,
        "authority_states": states,
        "evidence_cross_cutting": lower.count("evidence") + lower.count("证据") >= 2,
        "source_references": [],
        **metadata,
    }


def validate_handoff(path: str | Path, carrier_identity: str, profile: str = "normal") -> ModuleResult:
    findings = []
    if profile not in {"normal", "strict"}:
        findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", str(path), "profile", "unsupported profile", profile))
        profile = "normal"
    if carrier_identity not in SUPPORTED_CARRIERS:
        findings.append(finding("HC01_UNKNOWN_CARRIER", "HOLD", str(path), "carrier", "unsupported carrier identity", carrier_identity))
        result, exit_code = outcome(findings, profile)
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sort_findings(findings), exit_code=exit_code, data={"mode": "OBSERVATION_AND_STRUCTURAL_LINT_ONLY", "receiver_ready": "NOT_MACHINE_DETERMINED"})
    try:
        document, text = _load_document(path)
    except (OSError, UnicodeError) as exc:
        findings.append(finding("IN01_PARSE_ERROR", "ERROR", str(path), "$", "handoff cannot be read", exc.__class__.__name__))
        result, exit_code = outcome(findings, profile)
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sort_findings(findings), exit_code=exit_code)
    observed = _markdown_observation(text) if document is None else document
    if not isinstance(observed, dict):
        findings.append(finding("IN01_PARSE_ERROR", "ERROR", str(path), "$", "handoff must normalize to an object", type(observed).__name__))
        observed = {}
    schema = observed.get("schema_version", "handoff-observation/v1")
    if schema in {"handoff-contract/v0", "legacy-eight-field/v1"} or "next_action" in observed and len(observed) == 8:
        findings.append(finding("HC01_UNKNOWN_CARRIER", "HOLD", str(path), "schema_version", "legacy eight-field schema is not the current six-dimensional contract", schema))
    elif schema != "handoff-observation/v1":
        findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", str(path), "schema_version", "unsupported handoff observation version", schema))

    expected = SUPPORTED_CARRIERS[carrier_identity]
    declared_carrier = observed.get("carrier_identity")
    declared_hash = observed.get("carrier_sha256")
    runtime_hash = observed.get("runtime_sha256")
    if declared_carrier and declared_carrier != carrier_identity:
        findings.append(finding("HC06_CARRIER_IDENTITY_MISMATCH", "HOLD", str(path), "carrier_identity", "declared carrier does not match requested adapter", {"declared": declared_carrier, "requested": carrier_identity}))
    if declared_hash and declared_hash != expected["carrier_sha256"]:
        findings.append(finding("HC06_CARRIER_IDENTITY_MISMATCH", "HOLD", str(path), "carrier_sha256", "declared carrier SHA-256 is wrong", declared_hash))
    if "runtime_sha256" in expected and runtime_hash and runtime_hash != expected["runtime_sha256"]:
        findings.append(finding("HC06_CARRIER_IDENTITY_MISMATCH", "HOLD", str(path), "runtime_sha256", "declared Skill runtime SHA-256 is wrong", runtime_hash))

    dimensions = observed.get("dimensions", {})
    if not isinstance(dimensions, dict):
        dimensions = {}
    missing = [name for name in DIMENSIONS if not dimensions.get(name)]
    if missing:
        findings.append(finding("HC02_MATERIAL_DIMENSION_ABSENT", "WARN", str(path), "dimensions", "one or more six-dimensional content lenses are not observed", missing))
    if observed.get("evidence_cross_cutting") is not True:
        findings.append(finding("HC03_EVIDENCE_NOT_CROSS_CUTTING", "WARN", str(path), "evidence_cross_cutting", "evidence is not observed across load-bearing dimensions", observed.get("evidence_cross_cutting")))

    authority_states = observed.get("authority_states", [])
    if isinstance(observed.get("authority"), list):
        authority_states = [item.get("state") for item in observed["authority"] if isinstance(item, dict)]
    normalized_states = {str(item).upper() for item in authority_states}
    unknown_states = normalized_states - AUTHORITY_VOCABULARY
    if not CORE_AUTHORITY_STATES.issubset(normalized_states) or unknown_states:
        findings.append(finding("HC05_AUTHORITY_LAYER_MISSING", "HOLD", str(path), "authority_states", "handoff must distinguish adjudicated, authorized, not-authorized and rejected states using the accepted vocabulary", {"observed": sorted(normalized_states), "unknown": sorted(unknown_states)}))
    if "CANONICAL" in normalized_states and str(observed.get("artifact_status", "")).upper() == "CANDIDATE":
        findings.append(finding("HC05_AUTHORITY_LAYER_MISSING", "HOLD", str(path), "artifact_status", "candidate content cannot be represented as canonical", observed.get("artifact_status")))

    if any(phrase in text.lower() for phrase in CONTEXT_DEPENDENT):
        findings.append(finding("HC04_NON_SELF_CONTAINED", "WARN", str(path), "content", "context-dependent reference observed", "CONTEXT_DEPENDENT_PHRASE"))
    if observed.get("direct_evidence_conflict") is True:
        findings.append(finding("HC07_DUAL_CARRIER_PARITY_REGRESSION", "HOLD", str(path), "direct_evidence_conflict", "unresolved direct evidence conflict blocks the observation", True))
    for index, reference in enumerate(observed.get("source_references", []) or []):
        if not isinstance(reference, dict) or not reference.get("load_bearing"):
            continue
        resolved, evidence = exact_source_resolves(reference.get("identity"), reference.get("location"))
        if not resolved:
            findings.append(finding("HC03_EVIDENCE_NOT_CROSS_CUTTING", "ERROR", str(path), f"source_references[{index}]", "load-bearing source reference does not resolve", evidence))

    sorted_items = sort_findings(findings)
    result, exit_code = outcome(sorted_items, profile)
    data = {
        "mode": "OBSERVATION_AND_STRUCTURAL_LINT_ONLY",
        "carrier_identity": carrier_identity,
        "carrier_sha256": expected["carrier_sha256"],
        "dimensions_observed": {name: bool(dimensions.get(name)) for name in DIMENSIONS},
        "authority_vocabulary_supported": sorted(AUTHORITY_VOCABULARY),
        "receiver_ready": "NOT_MACHINE_DETERMINED",
        "semantically_complete": "NOT_MACHINE_DETERMINED",
        "fully_self_contained": "NOT_MACHINE_DETERMINED",
    }
    return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, profile=profile, findings=sorted_items, exit_code=exit_code, data=data)
