# Successor evaluation contract

This directory preserves FABLE5's offline successor-evaluation baseline. It is
a bounded behavioral contract for examining whether an agent handles evidence,
authorization, terminal state, scope, and recovery constraints. It is not a
model integration or a release-approval mechanism.

## Files

- `cases.jsonl` contains the 12 preserved scenarios, evidence prompts, hidden
  scoring material, and weights.
- `rubric.md` records the human administration and scoring procedure.
- `scoring_schema.json` defines per-case scoring, weighted aggregation, and
  result bands.
- `expected_controls.jsonl` maps each case to the capability and safeguards it
  is intended to examine.

The preserved material is mostly Chinese, and that multilingual content is
intentional. It remains part of the hash-bound evaluation baseline rather than
being silently translated or rewritten.

`assurance eval prepare` validates the preserved contract identities and writes
a no-clobber participant view that excludes hidden scoring fields. It does not
invoke a model. `assurance eval score` validates externally supplied score
records and calculates the deterministic totals and bands. A human or external
evaluator still performs the semantic judgment and supplies evidence quotes;
FABLE5 does not infer those judgments.

The current scope excludes hosted benchmarking, automatic semantic scoring,
model calls, deployment authorization, and automatic promotion. Evaluation
results are review evidence, not project-authority decisions.
