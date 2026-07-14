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
