# Repository agent guide

Start with `README.md`, then read `CONTRIBUTING.md`, `SECURITY.md`, and
`MAINTAINERS.md` before proposing a change.

Architecture and boundaries are in `docs/ARCHITECTURE.md`,
`docs/MODULE_SCOPE_AND_NON_GOALS.md`, and
`docs/LIMITATIONS_AND_FUTURE_SEAMS.md`. Public machine-readable contracts are
under `contracts/`, including `contracts/schemas/CLI_OUTPUT_CONTRACT.json`.

Run the complete local suite exactly as follows:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 -m unittest discover -s tests -v
```

Behavioral changes require reproducible source or execution evidence, a
regression test, compatibility and security impact, and any public
contract/documentation delta. Roots, exclusions, and scope are behavioral
contract surfaces. See `CONTRIBUTING.md` for the full evidence requirements.

AI-produced output is evidence or review input only. It is never authority to
merge, release, promote, or make an adoption claim.
