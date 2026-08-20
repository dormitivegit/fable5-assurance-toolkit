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
runtime dependencies. Install it from a repository checkout in an isolated
environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
assurance --version
assurance --help
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

## CLI output and exit contract

The normative, machine-readable contract is
[`contracts/schemas/CLI_OUTPUT_CONTRACT.json`](contracts/schemas/CLI_OUTPUT_CONTRACT.json).
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
human reviewer. See the [example guide](examples/agent-change-assurance/README.md)
for the expected flow and claim boundaries.

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

See [Architecture](docs/ARCHITECTURE.md),
[module scope and non-goals](docs/MODULE_SCOPE_AND_NON_GOALS.md), and
[known limitations](docs/LIMITATIONS_AND_FUTURE_SEAMS.md) for the detailed
boundaries.

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
PRODUCT_VERSION=0.3.0-recovery.3
PYTHON_DISTRIBUTION_VERSION=0.3.0rc3
STATUS=full-functional-recovery-candidate
LINEAGE_ID=FABLE5-ASSURANCE-TOOLKIT-FULL-FUNCTIONAL-RECOVERY-20260713
```

This repository is a clean-room functional reconstruction under a new Git
lineage, based on accepted architecture, contracts, sanitized fixtures, tests,
and pilot requirements. It claims continuity of the accepted functional
contract, not recovery of historical source bytes, commits, or tags. The
`v0.3.0-recovery.1` tag identifies the first recovery candidate in the
reconstructed lineage; `v0.3.0-recovery.2` records the subsequent public
open-source surface hardening; and `v0.3.0-recovery.3` generalizes the public
authorization contract for external maintainers.

The current status means the six modules and public interface have been
reconstructed and mechanically tested. It does **not** claim independent
review, user acceptance, external validation, canonical promotion, production
readiness, or ecosystem adoption. See
[status semantics](docs/STATUS_SEMANTICS.md) and
[recovery lineage](docs/RECOVERY_LINEAGE.md) for the precise claims.

## Contributing

Focused issues and pull requests are welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for test, determinism, and AI-assisted
contribution expectations. Maintainer roles are documented in
[MAINTAINERS.md](MAINTAINERS.md).

## Security

Do not report vulnerabilities or exploit details in a public issue. Follow the
private reporting process in [SECURITY.md](SECURITY.md).

## License

Licensed under the [Apache License 2.0](LICENSE).
