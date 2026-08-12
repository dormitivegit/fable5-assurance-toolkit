# Security Policy

## Report a vulnerability privately

Use this repository's
[GitHub private security advisories](https://github.com/dormitivegit/fable5-assurance-toolkit/security/advisories/new):

1. Open the repository's **Security** tab.
2. Select **Advisories** and then **Report a vulnerability**.
3. Include the affected version or commit, impact, reproduction steps, and any
   suggested mitigation that can be shared safely.

Do not open a public issue, discussion, or pull request for an undisclosed
vulnerability. Do not post credentials, tokens, private data, working exploit
details, or sensitive environment information publicly. If a credential may
have been exposed, revoke or rotate it through its provider; do not include its
value in the report.

The maintainer will use the private advisory to assess the report, coordinate a
fix where appropriate, and discuss disclosure timing. The project currently
publishes no guaranteed response or remediation SLA.

## Current security-support status

FABLE5 `0.3.0-recovery.3` has
`STATUS=full-functional-recovery-candidate`. Its implemented public interface
has mechanical test coverage, but the candidate is not independently reviewed,
user accepted, externally validated, canonical, deployed, or production ready.
Reports concerning the current `main` branch and the recovery candidate
are welcome, but this status must not be interpreted as a production-support
commitment.

The toolkit is designed to run locally without network access or
non-standard-library Python runtime dependencies. Synthetic Pilot B invokes a
local Git executable as a controlled test subject. These design properties
reduce some exposure, but they are not a guarantee that the software is free of
vulnerabilities.
