"""Finding construction, stable sorting, and result precedence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import Finding

SEVERITY_ORDER = {"HOLD": 0, "ERROR": 1, "WARN": 2, "INFO": 3}


def finding(
    code: str,
    severity: str,
    path: str,
    location: str,
    message: str,
    evidence: Any,
    *,
    rule_version: str = "recovery-1",
) -> Finding:
    if severity not in SEVERITY_ORDER:
        raise ValueError(f"unsupported finding severity: {severity}")
    return Finding(code, severity, path, location, message, rule_version, evidence)


def sort_findings(items: Iterable[Finding]) -> list[Finding]:
    return sorted(
        items,
        key=lambda f: (
            SEVERITY_ORDER[f.severity],
            f.code,
            f.path,
            f.location,
            f.message,
        ),
    )


def outcome(items: Iterable[Finding], profile: str, *, family: str = "") -> tuple[str, int]:
    findings = list(items)
    blocking = [f for f in findings if f.severity in {"ERROR", "HOLD"}]
    if profile == "strict":
        blocking.extend(f for f in findings if f.severity == "WARN")
    if not blocking:
        return "PASS", 0
    if any(f.code.startswith("TG") for f in blocking) or family == "terminal":
        return "HOLD", 5
    if any(f.code.startswith("CI") for f in blocking) or family == "integrity":
        return "HOLD", 4
    if any(f.severity == "HOLD" for f in blocking):
        return "HOLD", 3
    if any(f.code.startswith("IN") for f in blocking):
        return "FAIL", 2
    return "FAIL", 1
