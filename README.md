# casf-core

> Public-by-design repository. No secrets, credentials, or PHI must be committed.

## Mission

Provide a security and compliance enforcement layer that acts as a zero-trust
boundary for inbound requests before control-plane actions are proposed or
executed.

## Architectural Role

`casf-core` is the control boundary between external actors and the internal
control plane. It validates, evaluates policy, enforces security rails, and
emits auditable decisions without embedding business-domain logic.

## Core Guarantees

- Deterministic policy evaluation.
- Fail-closed enforcement.
- Signed and auditable decision path.
- Rate-limiting boundary at execution rails.

## Non-goals

- Vertical-specific domain logic.
- Product workflow orchestration outside security/policy scope.
- Bypassing policy/signature gates with direct execution paths.
- Vendor lock-in at contract level.

## Boundary Diagram

```text
External Actors (API clients, webhooks)
                |
                v
      +---------------------------+
      |        casf-core          |
      | validation + policy + sig |
      | audit + rate-limit rails  |
      +-------------+-------------+
                    |
                    v
   Internal Control Plane / workers / adapters
```

## Repository Scope (Current)

Current implementation paths:

- API boundary: `src/cacp/api/`
- Policy input and OPA client: `src/cacp/policy/`
- Compliance gates: `src/cacp/orchestration/agents/compliance_agent.py`
- Signing: `src/cacp/signing/`
- Audit event store: `src/cacp/storage/event_store.py`
- Execution rails (consent, quiet-hours, rate limit, dedup): `src/cacp/workers/worker.py`

TODO: verify in `src/cacp/` whether module naming will be normalized from `cacp` to `casf_core`.

## Runtime Endpoints (Existing Surface)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/ingest` | Inbound request intake into orchestration pipeline |
| `POST` | `/webhook/github` | Signed merge-event intake (execution trigger) |
| `POST` | `/webhook/twilio-status` | Provider callback intake |
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/ready` | Dependency readiness probe |
| `GET`  | `/metrics` | Prometheus text metrics |

Additional non-core demo endpoints currently exist under `/demo/*`.

## Governance and Contracts

- Policy governance model: `docs/policy-model.md`
- Audit/logging standard: `docs/audit-model.md`
- Error contract: `docs/error-model.md`
- Contract/versioning baseline: `CONTRACTS.md`
- JSON Schemas: `specs/contracts/`

## CI/CD

CI workflows are present in `.github/workflows/` and should remain mandatory for
policy, schema, and security checks on every merge.

## License

[Apache-2.0](LICENSE)
