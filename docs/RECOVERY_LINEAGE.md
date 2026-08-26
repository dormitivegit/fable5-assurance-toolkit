# Recovery lineage

```text
LINEAGE_ID=FABLE5-ASSURANCE-TOOLKIT-FULL-FUNCTIONAL-RECOVERY-20260713
HISTORICAL_LINEAGE_CONTINUITY_CLAIM=NO
FUNCTIONAL_CONTRACT_CONTINUITY=YES
```

The historical repository bytes, candidate.5 worktree, Git commits, and tags
were unavailable. This repository is a clean-room functional reconstruction
from accepted architecture, contracts, sanitized fixtures, tests, and pilot
requirements. Historical object identities are records only and were not
synthesized.

## Project status and provenance

```text
PRODUCT_VERSION=0.3.0-recovery.6
PYTHON_DISTRIBUTION_VERSION=0.3.0rc6
STATUS=full-functional-recovery-candidate
LINEAGE_ID=FABLE5-ASSURANCE-TOOLKIT-FULL-FUNCTIONAL-RECOVERY-20260713
```

This repository is a clean-room functional reconstruction under a new Git
lineage, based on accepted architecture, contracts, sanitized fixtures, tests,
and pilot requirements. It claims continuity of the accepted functional
contract, not recovery of historical source bytes, commits, or tags. The
`v0.3.0-recovery.1` tag identifies the first recovery candidate in the
reconstructed lineage; `v0.3.0-recovery.2` records the subsequent public
open-source surface hardening; `v0.3.0-recovery.3` generalizes the public
authorization contract for external maintainers; and `v0.3.0-recovery.4`
publishes the current contract hardening and consumer guidance. The published
`v0.3.0-recovery.5` prerelease adds first-run navigation, validated
maintainer-controlled workflow summaries, a runnable machine-consumer path,
and PEP 517 distribution metadata. Its Python distribution is available from
PyPI as `fable5-assurance-toolkit==0.3.0rc5`. The `0.3.0-recovery.6`
candidate adds the explicit expected-root subject assertion to
`corpus verify`: a caller can require the manifest-declared root sequence
before recorded-source verification. Omitting `--expected-root` preserves
legacy behavior, and manifests remain bound to the absolute paths recorded at
freeze time; they are not portable or rebindable. The current published
prerelease is `fable5-assurance-toolkit==0.3.0rc6`; the recovery.5 publication
remains historical context rather than the current PyPI subject.

The current status means the six modules and public interface have been
reconstructed and mechanically tested. Bounded independent review exists for
the current contract/runtime correction; this is not a claim of comprehensive
independent review, user acceptance, external validation, canonical promotion,
production readiness, or ecosystem adoption. See
[status semantics](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/STATUS_SEMANTICS.md) and
[recovery lineage](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/RECOVERY_LINEAGE.md) for the precise claims.
