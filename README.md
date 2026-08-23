# FABLE5 Assurance Toolkit

FABLE5 is a local, deterministic command-line toolkit for applying assurance
and conformance controls to AI-assisted software-engineering workflows. It
turns structured task inputs, governance packs, terminal states, corpus
manifests, handoffs, closeouts, and evaluation records into reproducible
findings that humans and automation can inspect.

AI-assisted changes can move faster than the evidence needed to review them.
FABLE5 makes selected behavioral contracts explicit and repeatable without a
hosted service, background agent, network call, or model invocation. It
complements tests and human review; it does not replace either or make release
decisions.

## Quick start

FABLE5 requires Python 3.11 or newer and has no non-standard-library Python
runtime dependencies. Install the published prerelease in an isolated
environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install fable5-assurance-toolkit==0.3.0rc5
assurance --version
assurance --help
```

For a source checkout, run commands from the repository root. To install the
checkout for development instead of the published prerelease, use:

```sh
python -m pip install .
```

Run a deterministic governance-pack check against the included fixture:

```sh
assurance check fixtures/governance/valid-pack.json --format json
```

For authorization-bearing `check`, `guard`, and `closeout` inputs, the caller
supplies the expected identity with `--authority-id <IDENTITY>`. Leading and
trailing whitespace is ignored; the remaining identifier is compared exactly
and case-sensitively. This is an out-of-band caller input; the document being
validated cannot set or override it. Read-only validation does not require an
authority ID.

For repository-only development without installation, use:

```sh
PYTHONPATH=src python3 -m assurance_toolkit --version
PYTHONPATH=src python3 -m assurance_toolkit --help
```

Run the complete test suite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m unittest discover -s tests -v
```

Use `--format json` when another tool or AI agent will consume the result. Run
`python3 -m assurance_toolkit <command> --help` for command-specific options.

## Start here: choose a command

| If you need to… | Start with |
| --- | --- |
| assess the risk and required controls for a bounded proposed action | `assurance classify fixtures/classify/read-local-document.json --format json` |
| validate a structured governance document before relying on it | `assurance check PACK.json --format json` |
| inspect a terminal state or target collision without changing either | `assurance guard STATE.json TARGET --executor NAME --format json` |
| freeze or verify the exact bytes of a bounded source set | `assurance corpus freeze ROOT --manifest MANIFEST --format json` or `assurance corpus verify MANIFEST --format json` |
| structurally inspect a handoff or closeout record | `assurance handoff HANDOFF.json --carrier CARRIER --format json` or `assurance closeout CLOSEOUT.json --format json` |
| prepare preserved evaluation cases or score supplied judgments | `assurance eval prepare CASES.jsonl --out PREPARED.json --format json` or `assurance eval score CASES.jsonl SCORES.jsonl --format json` |

The commands report bounded evidence. They do not authorize a change, decide a
merge, or replace human review.

For an already accepted corpus manifest, bind verification to its exact raw
bytes as well as its semantic records:

```sh
assurance corpus verify MANIFEST \
  --accepted-manifest-sha256 SHA256 \
  --format json
```

The accepted SHA-256 is caller supplied. It anchors the exact manifest bytes
and therefore the recorded scope declaration; it does not prove that the
chosen roots or exclusions are complete, optimal, or authorized.

Corpus manifests bind sources to the absolute filesystem paths recorded at
freeze time. Verification expects those paths to keep identifying the intended
sources; a manifest is not a portable "freeze on one machine, verify under a
different layout" artifact. Manifests also disclose absolute paths and
per-file hashes, so do not publish sensitive manifests verbatim or freeze
credential-bearing roots.

`--exclude` uses path containment/prefix semantics, not shell glob matching.
With `--detect-new`, current normal verification reports
`CI10_NEW_SOURCE_DETECTED` as `WARN`; when it is the only finding, the process
still exits `0`. Consumers that need new-file gating must inspect structured
findings as well as the process exit status.

## CLI output and exit contract

The normative, machine-readable contract is
[`contracts/schemas/CLI_OUTPUT_CONTRACT.json`](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/contracts/schemas/CLI_OUTPUT_CONTRACT.json).
It distinguishes ModuleResult JSON, CLI parse-failure JSON, argparse usage
text, help/version text, and the existing synthetic-pilot JSON shape. In
particular, parse-failure JSON uses the command string as `module_id` and
`recovery-1` as `rule_set_version`; argparse usage failures emit no JSON.

| Exit | Meaning |
| --- | --- |
| 0 | PASS or successful non-error command |
| 1 | generic FAIL |
| 2 | input/invocation-class FAIL |
| 3 | generic HOLD |
| 4 | integrity-family HOLD |
| 5 | terminal/target-family HOLD |

For structured module outcomes, finding severity first determines whether the
outcome is blocking: `ERROR` and `HOLD` block, while `WARN` and `INFO` do not
block under the normal profile. `--profile strict` can promote `WARN` to
effective blocking for the final decision without changing the serialized
finding's severity label. A non-blocking finding does not select a nonzero exit
solely because its prefix belongs to an exit family.

For effectively blocking module outcomes, PM-03 normally applies the
terminal-family exit floor/pin and PM-04 normally applies the integrity-family
exit floor/pin, subject to explicit decision exceptions published in the
normative CLI contract. This module-selected effective exit family is distinct
from the family suggested by an individual finding prefix. After severity,
profile promotion, any module floor/pin, and any exact exception are resolved,
precedence remains
`terminal(5) > integrity(4) > HOLD-severity(3) > input-class(2) > generic(1)`.
The table above is a summary; consumers that need exact decision behavior must
use the normative JSON contract.

This build publishes the current output/exit contract, not the complete
current-generation input contract needed to reauthor every preserved A1 case.
A1 remains predecessor-generation evidence only, not a current release gate,
compatibility claim, or adoption claim. Any future reactivation requires
sufficient normative input and output authority plus fresh execution and
discriminating-power evidence.

## Try the end-to-end example

Run a deterministic walkthrough that surrounds a simulated agent-generated
change with risk, integrity, and handoff evidence:

```sh
./examples/agent-change-assurance/run.sh
```

The example is local, network-free, self-cleaning, and leaves acceptance to a
human reviewer. See the [example guide](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/examples/agent-change-assurance/README.md)
for the expected flow and claim boundaries.

## Try a machine-consumer integration

From the repository root, run:

```sh
python3 examples/machine-consumer/run.py
```

This small, disposable example creates a bounded source set, consumes JSON
from `corpus verify --detect-new`, and takes a review branch when a nonblocking
`WARN` finding is present even though the process exit is `0`. It demonstrates
why a consumer must inspect structured findings rather than branch on exit
status alone. See the [machine-consumer guide](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/examples/machine-consumer/README.md).

## Modules

| Module | CLI surface | Purpose |
| --- | --- | --- |
| PM-01 Risk Router | `classify` | Classifies task risk from the effects of a proposed action. |
| PM-02 Governance Pack Validator | `check` | Validates structured claims, decisions, actions, and exact source references. |
| PM-03 Terminal State and Artifact Guard | `guard` | Performs a read-only preflight for terminal-state and target-collision conditions. |
| PM-04 Corpus Integrity Guard | `corpus freeze`, `corpus verify` | Creates and verifies bounded, hash-addressed corpus manifests. |
| PM-05 Handoff and Closeout Validator | `handoff`, `closeout` | Checks handoff carriers and closeout records against explicit contracts. |
| PM-06 Successor Evaluation Harness | `eval prepare`, `eval score` | Prepares preserved evaluation cases and scores externally supplied judgments. |

The `pilot run` surface provides four synthetic pilots (`A`, `B`, `C1`, and
`C2`) for exercising selected module interactions inside a newly supplied
disposable root. Pilot C2 is the only pilot-local writer that demonstrates an
atomic no-clobber seam; it is not reachable from ordinary project workflows.

## Design properties

- **Deterministic:** rules, findings, ordering, and output formats are designed
  for repeatable inspection from the same bounded inputs.
- **Local-first and network-free:** the core modules use only the Python
  standard library and do not contact remote services. Synthetic Pilot B uses
  an already installed local Git executable as its test subject with hooks and
  user/system configuration disabled.
- **Explicit contracts:** versioned schemas, identities, fixtures, and
  evaluation records keep behavioral expectations reviewable in the
  repository.
- **Fail-closed parsing:** malformed or incomplete inputs produce structured
  failure findings instead of implied success.
- **Bounded side effects:** validation and guard surfaces are read-only;
  artifact-producing commands require explicit destinations, and synthetic
  pilot writes are confined to a caller-supplied disposable root.
- **No hidden control plane:** there is no daemon, database, web UI, installed
  hook, automatic model call, semantic auto-score, or automatic promotion path.

See [Architecture](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/ARCHITECTURE.md),
[module scope and non-goals](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/MODULE_SCOPE_AND_NON_GOALS.md), and
[known limitations](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/LIMITATIONS_AND_FUTURE_SEAMS.md) for the detailed
boundaries. Read [validated workflows](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/VALIDATED_WORKFLOWS.md) for two
bounded, maintainer-controlled downstream cases and their claim limits.

## AI-agent and maintainer workflow

1. A human or automation supplies a bounded input and chooses the applicable
   FABLE5 command and profile.
2. An AI agent or CI job runs the command, preserves its structured output, and
   treats nonzero exit codes and findings as review evidence.
3. The submitter runs the test suite and explains any intentional behavioral
   contract change in the pull request.
4. A maintainer reviews the code, tests, deterministic output, compatibility,
   and security impact before deciding whether to merge or release.

FABLE5 reports on the contracts it implements. It does not establish business
truth, infer authorization, approve its own changes, or promote a candidate to
production. Those decisions remain with people responsible for the project.

## Project status and provenance

```text
PRODUCT_VERSION=0.3.0-recovery.5
PYTHON_DISTRIBUTION_VERSION=0.3.0rc5
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
PyPI as `fable5-assurance-toolkit==0.3.0rc5`.

The current status means the six modules and public interface have been
reconstructed and mechanically tested. Bounded independent review exists for
the current contract/runtime correction; this is not a claim of comprehensive
independent review, user acceptance, external validation, canonical promotion,
production readiness, or ecosystem adoption. See
[status semantics](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/STATUS_SEMANTICS.md) and
[recovery lineage](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/RECOVERY_LINEAGE.md) for the precise claims.

## Contributing

Focused issues and pull requests are welcome. Read
[CONTRIBUTING.md](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/CONTRIBUTING.md) for test, determinism, and AI-assisted
contribution expectations. Maintainer roles are documented in
[MAINTAINERS.md](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/MAINTAINERS.md).

## Security

Do not report vulnerabilities or exploit details in a public issue. Follow the
private reporting process in [SECURITY.md](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/SECURITY.md).

## License

Licensed under the [Apache License 2.0](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/LICENSE).
