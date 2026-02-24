# Security Policy

## Scope

This repository is a security and policy-enforcement boundary. Security reports
must prioritize vulnerabilities that could allow policy bypass, signature
forgery, unauthorized execution, or audit tampering.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes |

## Reporting a Vulnerability

- Do not disclose vulnerabilities publicly.
- Use GitHub Security Advisories for private disclosure when possible.
- Include reproduction steps, impact, and affected paths.
- Expected acknowledgment window: within 72 hours.

TODO: verify in `SECURITY.md` the primary security contact channel if a private advisory cannot be opened.

## Triage Priorities

1. Signature verification bypass (`webhook` or proposal signing paths).
2. Policy enforcement bypass (orchestrator/worker rails).
3. Privilege or authorization bypass at API boundary.
4. Event/audit integrity compromise.
5. Dependency vulnerabilities with reachable exploit path.

## Disclosure and Fix Process

- Every accepted issue gets a tracked fix and changelog note.
- Security-impacting behavior changes require review from CODEOWNERS.
- Backports are evaluated for all supported versions.
