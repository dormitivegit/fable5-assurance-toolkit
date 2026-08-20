# Contributing to FABLE5

Thank you for helping improve FABLE5. Contributions should keep the toolkit
small, inspectable, deterministic, and useful to both human reviewers and
AI-assisted engineering workflows.

## Before opening a pull request

1. Read the [README](README.md),
   [architecture](docs/ARCHITECTURE.md), and
   [module scope and non-goals](docs/MODULE_SCOPE_AND_NON_GOALS.md).
2. Keep the change focused on one problem. Separate unrelated refactors,
   formatting changes, and behavioral changes into different pull requests.
3. Explain the problem, the chosen approach, and any compatibility or security
   impact in the pull request description.

For vulnerability reports, do not open a public issue or pull request. Follow
[SECURITY.md](SECURITY.md).

## Development and tests

FABLE5 requires Python 3.11 or newer and has no non-standard-library Python
runtime dependencies. Run the public CLI directly from the checkout:

```sh
PYTHONPATH=src python3 -m assurance_toolkit --version
```

Run the complete test suite before submitting:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m unittest discover -s tests -v
```

Pull requests that change behavior must include or update tests that exercise
the new behavior and relevant failure paths. Documentation-only changes should
still leave the complete suite passing.

## Evidence for behavioral changes

For each behavioral claim or change:

- provide reproducible source or execution evidence for the claim;
- add a regression test that exercises the changed behavior and its relevant
  failure path;
- state compatibility and security impact, including any migration cost;
- update the public contract and documentation when observable behavior
  changes;
- report the exact CI/test command and result with a bounded claim;
- treat roots, exclusions, and scope changes as behavioral-contract changes
  requiring the same evidence; and
- distinguish static inspection from execution evidence whenever the claim is
  executable.

Claims that an external harness or consumer provides compatibility coverage
must include an execution receipt against the exact subject and generation.
A baseline execution receipt must exist before that harness or consumer can be
proposed as a release gate. Static inspection or reviewer agreement is not a
substitute for that execution.

## Behavioral expectations

- Preserve deterministic, reproducible results. Tests must not depend on wall
  clock timing, unordered output, local user configuration, or mutable external
  state.
- Do not introduce hidden network dependencies. Core behavior and tests must
  not require remote services, downloads, telemetry, or credentials.
- Keep inputs, outputs, side effects, and failure modes explicit. Malformed or
  incomplete inputs should fail closed with reviewable evidence.
- Preserve existing behavioral contracts unless the pull request clearly
  identifies an intentional contract change, updates the relevant tests and
  documentation, and explains migration or compatibility effects.
- Use only sanitized fixtures. Never commit credentials, tokens, private user
  data, production configuration, or exploit details.

## AI-assisted contributions

AI-assisted contributions are allowed. The human submitter remains responsible
for understanding every submitted change, reviewing generated code and text,
confirming that it can be contributed under the project's license, removing
sensitive information, and running the required tests. AI output or a passing
check is evidence for review, not a substitute for human accountability.

## Licensing

Unless explicitly stated otherwise, contributions intentionally submitted to
this project are provided under the [Apache License 2.0](LICENSE), consistent
with the license's contribution terms.
