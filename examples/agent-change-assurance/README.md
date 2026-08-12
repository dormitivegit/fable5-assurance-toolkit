# Agent Change Assurance Example

## What this demonstrates

An upstream coding agent can generate a change, but its output alone does not
provide an independent record of the task boundary, the previous file identity,
or whether its handoff is structurally reviewable. This example uses FABLE5 to
produce deterministic evidence around those selected contracts. A human still
decides whether the change is correct and acceptable.

The change is simulated locally and deterministically. No AI model is invoked
or required.

## Run it

From the repository root:

```sh
./examples/agent-change-assurance/run.sh
```

The script requires Bash and Python 3.11 or newer. It uses only the Python
standard library, makes no network calls, creates a disposable temporary
workspace, and removes that workspace on exit.

Temporary absolute paths and manifest hashes vary with each workspace. The
asserted results, findings, counts, modes, and final summary remain the same.

## Expected flow

```text
bounded task
  → FABLE5 risk classification
  → frozen baseline and positive verification
  → simulated upstream agent change
  → deterministic change detection
  → verified post-change evidence
  → handoff structural observation
  → human review
```

## What to look for

- PM-01 reports `tier=T1` and `classification_is_authorization=false` for the
  reversible repository edit.
- PM-04 first reports a matching one-file baseline.
- Verifying that baseline after the simulated change returns the expected exit
  code `4`, `result=HOLD`, and finding `CI03_SOURCE_CHANGED`.
- A new post-change manifest verifies with one matching file; this records the
  new bytes but does not judge their correctness.
- The generated handoff binds the post-change manifest by exact path, SHA-256,
  and text anchor. PM-05 resolves that reference, then reports
  `mode=OBSERVATION_AND_STRUCTURAL_LINT_ONLY` and
  `receiver_ready=NOT_MACHINE_DETERMINED`, preserving the human decision gate.

The handoff template lists the authority-state vocabulary that the current
observation contract requires it to distinguish. The list does not declare the
simulated change authorized.

The script asserts each of these outcomes and exits nonzero if actual FABLE5
behavior differs.

## What this does not prove

This example does not prove production readiness, independent validation,
AI-model correctness, authorization, or external adoption. It demonstrates
only the deterministic contracts exercised by the commands shown.
