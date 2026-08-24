"""Small stable public result types shared by the six product modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    path: str
    location: str
    message: str
    rule_version: str
    evidence: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PredicateResult:
    """A readiness input whose name and value are both positive pass conditions."""

    name: str
    passed: bool
    evidence: Any


@dataclass
class ModuleResult:
    result: str
    module_id: str
    module_version: str = "0.3.0-recovery.6"
    rule_set_version: str = "recovery-1"
    profile: str = "normal"
    findings: list[Finding] = field(default_factory=list)
    facts: list[Any] = field(default_factory=list)
    exit_code: int = 0
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "result": self.result,
            "module_id": self.module_id,
            "module_version": self.module_version,
            "rule_set_version": self.rule_set_version,
            "profile": self.profile,
            "findings": [finding.to_dict() for finding in self.findings],
            "facts": self.facts,
            "exit_code": self.exit_code,
        }
        payload.update(self.data)
        return payload
