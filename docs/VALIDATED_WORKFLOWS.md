# Validated maintainer-controlled workflows

These two cases summarize real downstream engineering work in privacy-safe
terms. They show where deterministic evidence from Software Evidence Controls
was useful alongside ordinary engineering tools and maintainer review.

**These are maintainer-controlled downstream engineering workflows. They are
not third-party adoption or broad compatibility evidence.**

## Classifier semantic edge correction

**Problem.** A classifier had a semantic edge case whose previous behavior did
not match the intended classification.

**Ordinary-tool observation.** The ordinary semantic test for the edge case
first failed and then passed after the focused correction.

**Deterministic Software Evidence Controls role.** Software Evidence Controls
separately preserved the bounded source-and-integrity boundary and emitted
machine-consumable evidence for the review record. It did not decide whether
the semantic correction was correct.

**Action taken.** The maintainer used the semantic RED-to-GREEN result together
with the bounded evidence, then made the human-owned correction decision.

**What this proves.** A focused semantic test and deterministic integrity
evidence can be used together without turning either into an automatic
acceptance authority.

**What this does not prove.** It does not prove classifier correctness beyond
the exercised edge case, third-party adoption, broad compatibility, or
production readiness.

## Mixed Rust and Swift workspace coverage

**Problem.** A change in a mixed Rust and Swift workspace was not fully covered
by the initial ordinary Rust test invocation.

**Ordinary-tool observation.** Stronger workspace execution was required to
cover the changed workspace before the result could be relied on.

**Deterministic Software Evidence Controls role.** Software Evidence Controls
provided deterministic acceptance evidence that qualified the evidence
available to the eventual maintainer merge decision; it did not make that
decision.

**Action taken.** The maintainer required the stronger workspace execution,
reviewed its result and the deterministic evidence, and retained human ownership
of the merge decision.

**What this proves.** Ordinary execution evidence can expose an incomplete test
invocation; Software Evidence Controls can separately provide deterministic
acceptance evidence that helps qualify a bounded maintainer decision.

**What this does not prove.** It does not prove all mixed-language workspaces
are covered, third-party adoption, broad compatibility, or automatic merge
authority.

## External-subject falsification experiment — not adoption

This maintainer-executed experiment used the public `pypa/packaging`
repository, base `4840c3a6817fbd0831f7e520c9a55367472a4a08`, and head
`55cbf1b9426f44455fa1a9e0836f1fc082cc8452`. GitHub comparison showed the head
one commit ahead, with changed paths `src/packaging/_ranges.py` and
`tests/test_ranges.py`; the accepted source change was
`src/packaging/_ranges.py`.

At both exact revisions, ordinary `pytest` passed. Software Evidence Controls returned `PASS/0` at
the base and `HOLD/4/CI03_SOURCE_CHANGED` at the head. A wrong-tree
expected-root control returned `HOLD/4/CI13_EXPECTED_ROOT_MISMATCH`, while the
legacy no-flag observation returned `PASS/0` using recorded-path semantics.
Thus ordinary pytest remained green while Software Evidence Controls independently observed the
accepted source delta, structured evidence routed the change to human review,
the wrong-tree assertion failed closed, and legacy no-flag behavior remained
unchanged.

This was executed by the Software Evidence Controls maintainer against a public third-party
repository subject. The `pypa/packaging` project did not adopt, integrate,
endorse, or request Software Evidence Controls as part of this experiment. It makes no claim of
PyPA adoption, broad compatibility, benchmark superiority, production
readiness, or automated human acceptance.
