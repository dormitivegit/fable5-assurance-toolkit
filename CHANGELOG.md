# Changelog

## 0.3.0-recovery.6

- Added a repeatable `--expected-root ROOT` option to `corpus verify`. Each
  supplied root is an assertion compared by index against the manifest
  header's declared root sequence before recorded-source verification; a
  count, lexical, real-path, or ordering mismatch returns a blocking
  `CI13_EXPECTED_ROOT_MISMATCH` integrity HOLD.
- The option never relocates or rebinds file reads: verification still reads
  the absolute paths recorded in the manifest, and omitting `--expected-root`
  preserves the legacy no-flag behavior without binding verification to the
  caller's working directory, Git metadata, or environment.
- Refreshed package, runtime, normative CLI output contract, README, and
  security-status version surfaces to the recovery.6 / 0.3.0rc6 candidate
  identity.

This remains a prerelease full-functional recovery candidate. Local
prepublication validation does not imply production readiness, broad
compatibility, external adoption, or human acceptance.

Post-publication note (2026-08-24): `v0.3.0-recovery.6` is published as a
GitHub prerelease and `fable5-assurance-toolkit==0.3.0rc6` is published on
PyPI. This publication does not imply production readiness, broad
compatibility, third-party adoption, or automatic acceptance. The subsequent
informational dogfood maintenance correction consumes rc6 and supplies an
explicit expected-root subject assertion.

## 0.3.0-recovery.5

- Made checkout-first onboarding explicit, added a progressive command map,
  and added a runnable machine-consumer example that inspects structured WARN
  findings even when the process exits successfully.
- Added privacy-safe summaries of two maintainer-controlled downstream
  engineering workflows, with explicit boundaries against adoption and broad
  compatibility claims.
- Added minimal PEP 517 build metadata, source-layout configuration, README,
  license, and supported-Python package metadata in preparation for a future
  authorized distribution upload.

This remains a full-functional recovery candidate. These source changes do not
publish a package, create a release, establish third-party adoption, or replace
maintainer review.

Post-publication note (2026-08-23): The `v0.3.0-recovery.5` GitHub release is
published as a prerelease, and `fable5-assurance-toolkit==0.3.0rc5` is available
from PyPI. This records publication only; it does not claim production
readiness, broad compatibility, third-party adoption, canonical promotion, or
external validation.

## 0.3.0-recovery.4

- Published the accepted-manifest and machine-readable CLI contract hardening
  already established by the preceding exact commits.
- Corrected the exact PM-04 malformed accepted-manifest SHA decision semantics
  while preserving ordinary PM-04 integrity HOLD behavior.
- Added consumer guidance for manifest path binding and non-relocatability,
  manifest path/hash disclosure, prefix exclusion semantics, and CI10 WARN
  behavior.
- Recorded that the relevant contract/runtime correction received bounded
  independent review, without claiming comprehensive review, external
  validation, production readiness, or ecosystem adoption.

This remains a full-functional recovery candidate.

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
