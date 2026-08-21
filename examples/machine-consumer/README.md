# Machine-consumer example

Run this example from a clean repository checkout:

```sh
python3 examples/machine-consumer/run.py
```

The script creates a temporary one-file source set, uses `corpus freeze` to
record its bounded baseline, adds one new source file, and runs:

```text
assurance corpus verify MANIFEST --detect-new --format json
```

The normal profile reports `CI10_NEW_SOURCE_DETECTED` as a `WARN` and exits
`0`. The consumer therefore parses the structured JSON, reads its findings, and
chooses `REVIEW_NEW_SOURCE` instead of treating exit `0` as permission to
continue automatically.

The script prints normalized decision markers rather than temporary paths or
raw manifests, so its observable result is deterministic. It uses no network
services, removes its temporary workspace automatically, and is exercised by a
repository test.

The review branch is still only evidence for a maintainer. It does not approve
the new source, authorize a change, or replace a human decision.
