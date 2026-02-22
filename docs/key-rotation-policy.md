# Key Rotation Policy

## Scope

Applies to secrets used for integrity and authentication at the security
boundary.

Covered keys/secrets:

- Proposal signing secret (`CACP_HMAC_SECRET`)
- GitHub webhook secret (`CACP_GITHUB_WEBHOOK_SECRET`)
- Twilio auth token (`CACP_TWILIO_AUTH_TOKEN`)

## Rotation Cadence

- Standard maximum age: 90 days
- High-risk or incident-driven rotation: immediate (within 24 hours)
- Emergency compromise response: rotate, revoke, validate replay protections

TODO: verify in `infra/` whether production policy requires a stricter cadence.

## Rotation Procedure (Minimal)

1. Generate new secret in approved secret manager.
2. Deploy configuration update using staged rollout.
3. Validate signature verification and request flow health.
4. Revoke previous secret after validation window.
5. Record rotation evidence (timestamp, owner, affected systems).

## Evidence Requirements

Each rotation record must include:

- Secret identifier (not secret value)
- Rotation date/time (UTC)
- Operator/approver
- Change reference (PR, ticket, or release)
- Post-rotation validation result

## Prohibited Practices

- Hardcoding secrets in source code.
- Sharing secrets via issue comments or logs.
- Storing cleartext secrets in repository files.
