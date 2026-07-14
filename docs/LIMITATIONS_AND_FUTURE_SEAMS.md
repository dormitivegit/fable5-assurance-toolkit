# Limitations and future seams

- Hashes prove byte identity, not semantic truth or provenance.
- PM-02 does not judge business truth; source anchors may still need human
  interpretation.
- PM-03 preflight alone cannot solve TOCTOU. Only C2 demonstrates a bounded
  atomic writer seam, and no general writer integration exists.
- Handoff observations cannot establish receiver understanding.
- PM-06 depends on human/external semantic judgments and cannot remove rater
  variance or contamination risk.
- Atomic hard-link installation fails closed where same-filesystem link
  semantics are unsupported. Parent-fsync failure leaves a complete installed
  file with durability status held rather than silently claiming success.
