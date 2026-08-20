# Architecture

The toolkit exposes one deterministic CLI over exactly six deep product
modules. Shared parsing, exact-source resolution, finding sorting, identity,
positive-predicate, and no-clobber utilities are internal mechanics rather than
a seventh product module.

All six core modules are in-process Python standard-library code. The explicitly
invoked synthetic Pilot B uses the local Git executable as its repository test
subject with hooks/config disabled; C2 uses short-lived local worker processes
to exercise real races. Neither is a background service or normal-task
dependency. There is no network path, daemon, database, Web UI, installed
plugin/hook, background service, automatic model call, semantic auto-score,
automatic project mutation, or canonical promotion path.

PM-03 is a read-only advisory preflight. C2 consumes its result, rechecks state
at the write seam, and uses `link(temp, target)` as a same-filesystem atomic
no-replace primitive. C2 is private to the synthetic pilot command.

PM-04 freeze records the canonical PM-04 rule generation in the manifest
header. Verify rejects a different rule generation and validates summary
counts against the manifest records and current special-file skips. When the
caller supplies `--accepted-manifest-sha256`, verify hashes the raw manifest
bytes before semantic JSONL parsing and retains byte-identity evidence even if
semantic parsing also fails. The accepted hash binds the exact scope-bearing
manifest bytes, not the completeness or authority of that scope.

The normative public output and exit description lives at
`contracts/schemas/CLI_OUTPUT_CONTRACT.json`. Contract tests consume that
artifact as authority and compare it with actual process output; the contract
is not generated from source during the test. It covers ModuleResult JSON, the
distinct CLI parse-failure JSON shape, non-JSON argparse and help/version
paths, and the existing synthetic-pilot JSON shape. No runtime result
`schema_version` field is added by this contract.

This contract closes the current output/exit side only. A complete
current-generation input contract for independently reauthoring preserved A1
cases is not published. A1 remains predecessor-generation evidence and is not
a current compatibility, adoption, or release-gate authority.
