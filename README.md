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
runtime dependencies. Install the prerelease in an isolated environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install fable5-assurance-toolkit==0.3.0rc6
assurance --version
assurance --help
```

### Minimal PyPI-only corpus demo

This demo needs only the installed package. It creates a disposable source
directory, freezes a manifest outside that source root, changes one source
file, and confirms that verification reports the expected source-change HOLD.
The freeze JSON already reports the manifest digest in `facts[].manifest_sha256`.
The snippet independently recomputes it from the manifest bytes so the
acceptance anchor does not rely only on the freeze operation's self-report.

```sh
demo_dir="$(mktemp -d)"
source_dir="$demo_dir/source"
manifest="$demo_dir/accepted-manifest.jsonl"
mkdir -p "$source_dir"
printf '%s\n' 'value = 1' > "$source_dir/example.py"
assurance corpus freeze "$source_dir" --manifest "$manifest" --format json
manifest_sha256="$(python - "$manifest" <<'PY'
import hashlib
import pathlib
import sys

print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
printf '%s\n' 'value = 2' > "$source_dir/example.py"
if assurance corpus verify "$manifest" \
    --accepted-manifest-sha256 "$manifest_sha256" \
    --expected-root "$source_dir" \
    --format json; then
  demo_exit=0
else
  demo_exit=$?
fi
test "$demo_exit" -eq 4  # CI03_SOURCE_CHANGED integrity HOLD
rm -rf "$demo_dir"
```

The JSON finding is the decision input: the expected `CI03_SOURCE_CHANGED`
HOLD is not an authorization to accept or reject the change.

The PyPI install above provides the `assurance` CLI. The fixture-backed examples
below use files from a source checkout; those repository fixtures are not
included in the wheel. For this prerelease, clone the matching release tag and
enter the repository root:

```sh
git clone --branch v0.3.0-recovery.6 --depth 1 \
  https://github.com/dormitivegit/fable5-assurance-toolkit.git
cd fable5-assurance-toolkit
```

Run a deterministic governance-pack check against the checkout fixture:

```sh
assurance check fixtures/governance/valid-pack.json --format json
```

To install the checkout for development instead of the published prerelease,
use:

```sh
python -m pip install .
```

For authorization-bearing `check`, `guard`, and `closeout` inputs, the caller
supplies the expected identity with `--authority-id <IDENTITY>`. Leading and
trailing whitespace is ignored; the remaining identifier is compared exactly
and case-sensitively. This is an out-of-band caller input; the document being
validated cannot set or override it. Read-only validation does not require an
authority ID.

The normative embedded-source reference base for `check` is defined in
[`contracts/schemas/PM02_SOURCE_REFERENCE_CONTRACT.json`](contracts/schemas/PM02_SOURCE_REFERENCE_CONTRACT.json).
File-backed packs resolve relative source paths from the pack's directory;
stdin packs require absolute source paths.

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

For `guard`, `--executor` must match the state/input's authorized executor
when that predicate applies. Guard target paths fail closed when traversal or
a symlinked parent makes their identity ambiguous. For `handoff`, the current
carrier values are `direct-v1-ax1-ax2` and `skill-v1-candidate-ax1-ax2`.

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

When a caller needs to assert the specific recorded subject before source
verification, it can repeat `--expected-root ROOT` in manifest-root order:

```sh
assurance corpus verify MANIFEST --expected-root ROOT [--expected-root ROOT ...]
```

Each supplied root is normalized with the same lexical and real-path identity
model used by PM-04, then compared by index with the manifest header's recorded
`roots` and `real_roots`. A count, lexical, real-path, or ordering mismatch
returns `CI13_EXPECTED_ROOT_MISMATCH` as an integrity-family `HOLD` (exit `4`)
before PM-04 reads recorded source paths. Omitting the option preserves legacy
recorded-path verification; the CLI never infers expected roots from CWD, Git,
or the manifest location.

Corpus manifests bind sources to the absolute filesystem paths recorded at
freeze time. Verification expects those paths to keep identifying the intended
sources; a manifest is not a portable "freeze on one machine, verify under a
different layout" artifact. Manifests also disclose absolute paths and
per-file hashes, so do not publish sensitive manifests verbatim or freeze
credential-bearing roots.

Manifest bytes and hashes are not authority by themselves. A caller-supplied
`--expected-root` is a subject assertion, not portable rebinding or
authorization, and human acceptance remains separate. See
[Architecture](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/ARCHITECTURE.md)
and [limitations](https://github.com/dormitivegit/fable5-assurance-toolkit/blob/main/docs/LIMITATIONS_AND_FUTURE_SEAMS.md)
for the trust boundaries.

`--exclude` uses path containment/prefix semantics, not shell glob matching.
With `--detect-new`, current normal verification reports
`CI10_NEW_SOURCE_DETECTED` as `WARN`; when it is the only finding, the process
still exits `0`. Consumers that need new-file gating must inspect structured
findings as well as the process exit status.

Profiles are exposed only by `classify`, `check`, `handoff`, and `closeout`.
`--profile strict` is not available for `corpus verify`, which always reports
the current normal-profile corpus decision semantics.

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

For structured module outcomes from commands that expose a `--profile` option,
finding severity first determines whether the outcome is blocking: `ERROR` and
`HOLD` block, while `WARN` and `INFO` do not block under the normal profile.
`--profile strict` can promote `WARN` to effective blocking for the final
decision without changing the serialized finding's severity label. A
non-blocking finding does not select a nonzero exit solely because its prefix
belongs to an exit family.

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

## Minimal CI and agent decision pattern

Use ordinary tests and tools first, then run the bounded FABLE5 deterministic
check, parse its structured findings and exit semantics, route the result to
CI, an agent, or a reviewer, and retain human acceptance as the final step.
Exit status alone is insufficient when nonblocking `WARN` findings are present.
`result` is `PASS` whenever no finding is effectively blocking; `WARN`
findings do not change `result`. Iterate `findings[]`.

On exit `2`, stdout may be empty; treat empty stdout on exit `2` as an
invocation error, not a finding.

## Comparison boundary

| Tool or role | Answers |
| --- | --- |
| ordinary tests | behavior under the exercised test suite |
| `git diff` | revision-tracked changed paths and lines |
| FABLE5 | bounded contract and accepted-subject evidence |
| human review | intent, admissibility, authorization, and acceptance |

These are complementary scopes; none replaces the others.

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

See [recovery lineage](docs/RECOVERY_LINEAGE.md) for status, provenance, and claim boundaries.

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
