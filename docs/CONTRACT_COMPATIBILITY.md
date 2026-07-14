# Contract compatibility

- Review Kernel v1.0-core is referenced by exact SHA-256 and is not modified.
- Direct Carrier A and Skill Candidate Carrier B are dispatched by exact fixed
  identities. Their content is not copied or modified and no third carrier is
  created.
- PM-05 handoff mode is observation and structural/authority lint only. It
  never declares receiver readiness, semantic completeness, or full
  self-containment.
- PM-05 closeout mode performs deterministic validation.
- The exact preserved 12-case evaluation baseline has maximum score 31.
- Unknown schema, carrier, and future-contract identities fail closed.
