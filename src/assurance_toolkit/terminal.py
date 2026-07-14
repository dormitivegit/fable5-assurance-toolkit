"""PM-03: read-only terminal-state and artifact preflight."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .findings import finding, outcome, sort_findings
from .io_utils import sha256_file
from .models import ModuleResult, PredicateResult

MODULE_ID = "PM-03"
RULE_VERSION = "tg-v1-recovery"
TERMINAL_STATES = {"CLOSED", "ACCEPTED", "RETIRED"}
SUPPORTED_STATES = TERMINAL_STATES | {"OPEN", "HOLD", "IN_PROGRESS"}
PLANS = {"CREATE_NEW_ATOMICALLY", "IDEMPOTENT_NOOP", "DENY_CLOSED", "DENY_COLLISION", "DENY_PRECONDITION"}


def _valid_reopen(state: dict[str, Any], proposed: dict[str, Any], executor: str, receipt: Any) -> bool:
    if not isinstance(receipt, dict):
        return False
    required = {
        "current_terminal_hash": state.get("terminal_hash"),
        "new_attempt_identity": state.get("new_attempt_identity"),
        "proposed_target_sha256": proposed.get("proposed_sha256"),
        "authorized_executor": executor,
        "authorized_object": state.get("task_id"),
        "authorization_state": "AUTHORIZED",
        "decider": "ZRN",
    }
    return all(receipt.get(key) == value and value not in {None, ""} for key, value in required.items())


def preflight(
    task_state: Any,
    target_identity: str | Path | dict[str, Any],
    executor: str | None = None,
    reopen_receipt: Any = None,
) -> ModuleResult:
    findings = []
    if not isinstance(task_state, dict):
        findings.append(finding("IN01_PARSE_ERROR", "ERROR", "$", "$", "task state must be an object", type(task_state).__name__))
        result, exit_code = outcome(findings, "normal", family="terminal")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sort_findings(findings), exit_code=exit_code, data={"allow_write": False, "plan": "DENY_PRECONDITION"})
    version = task_state.get("schema_version", "task-state/v1")
    if version != "task-state/v1":
        findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", "$", "schema_version", "unsupported task state version", version))

    if isinstance(target_identity, dict):
        target_path = Path(str(target_identity.get("path", "")))
        proposed = dict(target_identity)
    else:
        target_path = Path(target_identity)
        proposed = dict(task_state.get("target") or {})
        proposed["path"] = str(target_path)
    proposed_hash = proposed.get("proposed_sha256") or task_state.get("proposed_target_sha256")
    proposed["proposed_sha256"] = proposed_hash
    executor = executor or str(task_state.get("executor") or "")
    state_name = str(task_state.get("terminal_state", "")).upper()
    plan = "CREATE_NEW_ATOMICALLY"
    allow_write = True

    path_ambiguous = not str(target_path) or ".." in target_path.parts or target_path.parent.is_symlink()
    if path_ambiguous:
        allow_write, plan = False, "DENY_PRECONDITION"
        findings.append(finding("TG07_TARGET_PATH_AMBIGUITY", "HOLD", str(target_path), "target", "target path contains traversal or a symlinked parent", "AMBIGUOUS_PATH"))

    predicates: list[PredicateResult] = [
        PredicateResult("schema_supported", version == "task-state/v1", version),
        PredicateResult("executor_matches", bool(executor) and executor == task_state.get("authorized_executor"), {"executor": executor, "authorized": task_state.get("authorized_executor")}),
        PredicateResult("single_writer_confirmed", task_state.get("single_writer") is True, task_state.get("single_writer")),
    ]
    prerequisites = task_state.get("prerequisites", {})
    if not isinstance(prerequisites, dict):
        prerequisites = {}
        findings.append(finding("TG02_EXECUTOR_PRECONDITION_FAILED", "HOLD", "$", "prerequisites", "prerequisites must be positive named Boolean conditions", type(task_state.get("prerequisites")).__name__))
        predicates.append(PredicateResult("prerequisite_structure_valid", False, type(task_state.get("prerequisites")).__name__))
    for name, passed in sorted(prerequisites.items()):
        predicates.append(PredicateResult(str(name), passed is True, passed))

    if state_name not in SUPPORTED_STATES:
        findings.append(finding("TG06_UNSUPPORTED_TERMINAL_STATE", "HOLD", "$", "terminal_state", "unsupported terminal state", state_name))
        allow_write, plan = False, "DENY_PRECONDITION"

    exact_reopen = _valid_reopen(task_state, proposed, executor, reopen_receipt)
    if state_name in TERMINAL_STATES and not exact_reopen:
        allow_write, plan = False, "DENY_CLOSED"
        findings.append(finding("TG01_TERMINAL_CLOSED", "HOLD", "$", "terminal_state", "terminal task cannot be reopened without an exact receipt", state_name))
        if reopen_receipt is not None:
            findings.append(finding("TG04_REOPEN_RECEIPT_MISMATCH", "HOLD", "$", "reopen_receipt", "reopen receipt does not bind terminal, attempt, target, executor, object and ZRN authorization", {"terminal_hash": task_state.get("terminal_hash"), "attempt": task_state.get("new_attempt_identity"), "target_sha256": proposed_hash}))

    failed_predicates = [item for item in predicates if not item.passed]
    if failed_predicates:
        allow_write, plan = False, "DENY_PRECONDITION"
        findings.append(finding("TG02_EXECUTOR_PRECONDITION_FAILED", "HOLD", "$", "preconditions", "one or more positive executor prerequisites failed", [{"name": item.name, "passed": item.passed, "evidence": item.evidence} for item in failed_predicates]))

    if path_ambiguous:
        pass
    elif target_path.is_symlink():
        allow_write, plan = False, "DENY_COLLISION"
        findings.append(finding("TG03_TARGET_COLLISION", "HOLD", str(target_path), "target", "symlink targets are ambiguous and fail closed", "SYMLINK"))
    elif target_path.exists():
        if target_path.is_file() and proposed_hash and sha256_file(target_path) == proposed_hash:
            if allow_write:
                allow_write, plan = False, "IDEMPOTENT_NOOP"
            findings.append(finding("TG05_IDENTICAL_TARGET_NOOP", "INFO", str(target_path), "target", "existing target has identical content; no bytes or metadata may be touched", proposed_hash))
        else:
            allow_write, plan = False, "DENY_COLLISION"
            findings.append(finding("TG03_TARGET_COLLISION", "HOLD", str(target_path), "target", "existing target has a different or ambiguous proposed identity", {"proposed_sha256": proposed_hash, "target_type": "file" if target_path.is_file() else "other"}))

    sorted_items = sort_findings(findings)
    result, exit_code = outcome(sorted_items, "normal", family="terminal")
    if plan in {"CREATE_NEW_ATOMICALLY", "IDEMPOTENT_NOOP"} and not any(item.severity in {"ERROR", "HOLD"} for item in sorted_items):
        result, exit_code = "PASS", 0
    data = {
        "allow_write": allow_write,
        "plan": plan,
        "required_human_action": "PROVIDE_EXACT_REOPEN_OR_NEW_VERSIONED_TARGET" if result == "HOLD" else "NONE",
        "positive_predicates": [{"name": item.name, "passed": item.passed, "evidence": item.evidence} for item in predicates],
        "guard_is_read_only": True,
        "toctou_ceiling": "PREFLIGHT_ONLY; WRITER_MUST_RECHECK_AT_ATOMIC_NO_REPLACE_SEAM",
    }
    return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sorted_items, exit_code=exit_code, data=data)
