# Machine-consumer example

Run this example from a clean repository checkout:

```sh
python3 examples/machine-consumer/run.py
```

This example runs the checkout source, not the installed distribution.

The script creates a temporary one-file source set, uses `corpus freeze` to
record its bounded baseline, adds one new source file, and runs:

```text
software-evidence-controls corpus verify MANIFEST --detect-new --format json
```

When the exact manifest bytes are intended to be a trust root, also use
`--accepted-manifest-sha256` with a digest obtained from a trusted,
out-of-band source or a prior accepted workflow state. Do not calculate that
digest from the same untrusted manifest immediately before verification. This
runnable example demonstrates structured finding consumption; by itself, it
is not an attacker-resistant manifest-custody system.

The normal profile reports `CI10_NEW_SOURCE_DETECTED` as a `WARN` and exits
`0`. The consumer therefore parses the structured JSON, reads its findings, and
chooses `REVIEW_NEW_SOURCE` instead of treating exit `0` as permission to
continue automatically.

The script prints normalized decision markers rather than temporary paths or
raw manifests, so its observable result is deterministic. It uses no network
services, removes its temporary workspace automatically, and is exercised by a
repository test.

For another repository, the portable pattern is to call the installed CLI,
parse `findings[]`, and route the structured result:

```python
import json
import subprocess
import sys
completed = subprocess.run(["software-evidence-controls", "corpus", "verify", sys.argv[1], "--detect-new", "--format", "json"], capture_output=True, text=True, check=False)
payload = json.loads(completed.stdout) if completed.stdout else {"findings": []}
findings = payload["findings"]
blocking = completed.returncode != 0 or any(item["severity"] in {"ERROR", "HOLD"} for item in findings)
route = "BLOCK" if blocking else ("REVIEW" if findings else "CONTINUE")
print(route)
```

The review branch is still only evidence for a maintainer. It does not approve
the new source, authorize a change, or replace a human decision.
