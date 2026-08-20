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
- An accepted manifest SHA-256 binds the exact manifest bytes and their
  recorded scope declaration. It does not prove that every relevant source was
  included or that the selected roots and exclusions were authorized.
- Exact recorded scope is not the same as complete scope. A mechanically valid
  but overly broad scope can also saturate results with operational noise and
  hide useful signal.
- PM-04 integrity does not establish freshness, semantic admissibility,
  effective date, or lineage. Any future `as_of`, freshness, or policy context
  must be supplied by a caller or trusted context; an artifact cannot authorize
  itself by recording those values.
- This build publishes the current public output/exit contract and mechanically
  binds it to process behavior. The complete current-generation input contract
  needed for independent A1 reauthoring is not published.
- A1 is preserved as predecessor-generation evidence only. It does not provide
  a current release gate, compatibility claim, or adoption claim.
