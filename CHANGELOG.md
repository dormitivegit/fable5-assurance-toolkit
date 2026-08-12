# Changelog

## 0.3.0-recovery.3

- Replaced the maintainer-specific authorization identity with an explicit,
  caller-supplied expected authority for governance mutations, terminal
  reopens, and closeout mutations. Validated documents cannot override that
  out-of-band expectation.
- Preserved fail-closed state, exact authority/object matching, evidence,
  collision, and terminal-state predicates while allowing ordinary read-only
  validation to run without an authority identity.
- Added an English entry point for the preserved multilingual successor
  evaluation contract and kept human/external scoring separate from
  deterministic preparation.
- Verified and documented standard installation in an isolated local virtual
  environment and the `assurance` console entry point.

This remains a full-functional recovery candidate. It is not independently
reviewed, externally validated, production ready, or evidence of ecosystem
adoption.

## 0.3.0-recovery.2

- Restructured the public README around deterministic assurance and
  conformance controls for AI-assisted software engineering while preserving
  the recovery-candidate status and provenance boundaries.
- Identified the primary maintainer and documented public issue, pull request,
  release, security-response, project-direction, and behavioral-contract
  responsibilities.
- Added focused contribution guidance covering tests, deterministic and
  reproducible behavior, network independence, and human responsibility for
  AI-assisted contributions.
- Added private vulnerability-reporting guidance through GitHub security
  advisories.
- Added GitHub Actions CI across Python 3.11, 3.12, 3.13, and 3.14.
- Adopted the Apache License 2.0 for the public repository and surfaced it in
  the README.

This remains a full-functional recovery candidate. It is not independently
reviewed, externally validated, production ready, or evidence of ecosystem
adoption.

## 0.3.0-recovery.1

- Reconstructed PM-01 through PM-06 under a new cryptographic lineage.
- Restored the deterministic public CLI and complete public-interface suite.
- Restored Pilot A, B, C1 and pilot-local atomic no-clobber C2.
- Preserved Review Kernel and dual Session Handoff contracts by exact identity.
- Preserved the exact 12-case, 31-point successor evaluation baseline.

This is a full-functional recovery candidate. It is not independently reviewed,
user accepted, validated, canonical, installed, production ready, or historical
byte recovery.
