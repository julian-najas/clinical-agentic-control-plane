**In production, these endpoints are expected to be exposed behind an external security boundary (`casf-core`).**

# clinical-agentic-control-plane (Núcleo)

> Public-by-design repository. No secrets, credentials, or PHI must be committed.

## Mission

This repository implements the **internal control plane** for agentic workflows and compliance orchestration.
It is not a security boundary. In production deployments, an external boundary layer (see `casf-core`) is expected to protect this surface.

## Architectural Role

`clinical-agentic-control-plane` is the orchestrator and compliance engine for internal workflows, event recording, and policy enforcement.
It does not embed business-domain logic or act as a zero-trust boundary.

## Core Guarantees

- Deterministic policy evaluation
- Fail-closed enforcement
- Signed and auditable decision path
- Rate-limiting and deduplication rails

## Non-goals

- Security boundary (handled by `casf-core` in layered deployments)
- Vertical-specific domain logic
- Product workflow orchestration outside compliance/policy scope
- Vendor lock-in at contract level

## Deployment Note

**In production, these endpoints are expected to be exposed behind an external security boundary (`casf-core`).**

## Repository Scope (Current)

Current implementation paths:

- API: `src/cacp/api/`
- Policy input and OPA client: `src/cacp/policy/`
- Compliance gates: `src/cacp/orchestration/agents/compliance_agent.py`
- Signing: `src/cacp/signing/`
- Audit event store: `src/cacp/storage/event_store.py`
- Execution rails (consent, quiet-hours, rate limit, dedup): `src/cacp/workers/worker.py`

Historical namespace note: `cacp` is retained in code paths for backward compatibility while this repository is positioned as `casf-core` security boundary.

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

## Legacy Scope Note

Legacy clinical/demo artifacts exist in this repository (`src/cacp/demo/` and
`/demo/*` endpoints). They are not part of the security-boundary product claim
and should be treated as optional demonstration surface.

TODO: verify in `infra/` how `/demo/*` exposure is disabled by default in production deployments.

## Governance and Contracts

- Policy governance model: `docs/policy-model.md`
- Policy change checklist: `docs/policy-change-checklist.md`
- Audit/logging standard: `docs/audit-model.md`
- Error contract: `docs/error-model.md`
- Error schema: `specs/contracts/error.schema.json`
- Error adoption plan: `docs/error-adoption-plan.md`
- Threat model (lite): `docs/threat-model-lite.md`
- Key rotation policy: `docs/key-rotation-policy.md`
- Support policy: `SUPPORT.md`
- Contract/versioning baseline: `CONTRACTS.md`
- JSON Schemas: `specs/contracts/`

## CI/CD

CI workflows are present in `.github/workflows/` and should remain mandatory for
policy, schema, and security checks on every merge.

## License

[Apache-2.0](LICENSE)
