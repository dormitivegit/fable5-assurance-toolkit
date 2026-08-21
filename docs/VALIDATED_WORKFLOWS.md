# Validated maintainer-controlled workflows

These two cases summarize real downstream engineering work in privacy-safe
terms. They show where deterministic FABLE5 evidence was useful alongside
ordinary engineering tools and maintainer review.

**These are maintainer-controlled downstream engineering workflows. They are
not third-party adoption or broad compatibility evidence.**

## Classifier semantic edge correction

**Problem.** A classifier had a semantic edge case whose previous behavior did
not match the intended classification.

**Ordinary-tool observation.** The ordinary semantic test for the edge case
first failed and then passed after the focused correction.

**Deterministic FABLE5 role.** FABLE5 separately preserved the bounded
source-and-integrity boundary and emitted machine-consumable evidence for the
review record. It did not decide whether the semantic correction was correct.

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

**Deterministic FABLE5 role.** FABLE5 provided deterministic acceptance
evidence that qualified the evidence available to the eventual maintainer merge
decision; it did not make that decision.

**Action taken.** The maintainer required the stronger workspace execution,
reviewed its result and the deterministic evidence, and retained human ownership
of the merge decision.

**What this proves.** Deterministic evidence can make an incomplete initial
test invocation visible and support a bounded, reviewable maintenance workflow.

**What this does not prove.** It does not prove all mixed-language workspaces
are covered, third-party adoption, broad compatibility, or automatic merge
authority.
