# FABLE5 Assurance Toolkit

```text
PRODUCT_VERSION=0.3.0-recovery.1
PYTHON_DISTRIBUTION_VERSION=0.3.0rc1
STATUS=full-functional-recovery-candidate
LINEAGE_ID=FABLE5-ASSURANCE-TOOLKIT-FULL-FUNCTIONAL-RECOVERY-20260713
```

This repository reconstructs the complete accepted functional contract of the
FABLE5 Assurance Toolkit under a new Git lineage. It does not claim recovery of
historical source bytes, commits, or tags.

The product is local-first, CLI-first, deterministic, network-free, and has no
non-standard-library Python runtime dependency. Pilot B invokes the already
available local Git executable solely as the synthetic repository system under
test; it disables hooks and all user/system Git configuration and never contacts
a remote. It has six top-level product modules:

1. PM-01 Risk Router
2. PM-02 Governance Pack Validator
3. PM-03 Terminal State and Artifact Guard
4. PM-04 Corpus Integrity Guard
5. PM-05 Handoff and Closeout Validator
6. PM-06 Successor Evaluation Harness

Run without installation:

```sh
PYTHONPATH=src python3 -m assurance_toolkit --version
PYTHONPATH=src python3 -m assurance_toolkit --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The `pilot` command writes only inside a newly supplied disposable root. PM-03
itself remains a read-only advisory guard; C2 is a pilot-local synthetic writer
and is not reachable from ordinary project workflows.

Passing tests do not imply independent review, acceptance, validation,
canonical promotion, installation, production readiness, or authorization.
