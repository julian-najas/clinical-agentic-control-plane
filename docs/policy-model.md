# Policy Model

## Scope

This document formalizes policy governance for the enforcement boundary
implemented in this repository.

Relevant runtime modules:

- `src/cacp/api/routes/ingest.py`
- `src/cacp/orchestration/orchestrator.py`
- `src/cacp/orchestration/agents/compliance_agent.py`
- `src/cacp/policy/input_builder.py`
- `src/cacp/policy/opa_client.py`
- `src/cacp/signing/hmac.py`
- `src/cacp/storage/event_store.py`
- `src/cacp/workers/worker.py`

## High-Level Evaluation Model

Policy evaluation is deterministic over explicit inputs and fixed rails:

- Request contract validation at API boundary (`pydantic` request models).
- Policy checks at proposal time (`ComplianceAgent` + OPA when configured).
- Security rails at execution time (consent, quiet-hours, rate limit, dedup in worker).
- Signature gates for proposal/webhook integrity.

No permissive fallback is allowed for failed security controls.

## Evaluation Flow

1. Request intake.
   Entry point: `POST /ingest` in `src/cacp/api/routes/ingest.py`.
2. Validation.
   Request body validated by `AppointmentIn` model.
3. Policy evaluation.
   `Orchestrator` calls `ComplianceAgent.validate(...)`.
   `ComplianceAgent` applies local limits and optional OPA decision (`OPAClient.evaluate`).
4. Decision.
   `ALLOW`: proposal continues to manifest + signature + PR path.
   `DENY`: proposal returned with `compliant=false` and violation reasons.
5. Audit/log path.
   Events are appended via `EventStoreProtocol.append(...)`.

## Policy Evolution Rules

- Policy input fields are contract-bound to `build_opa_input(...)` in
  `src/cacp/policy/input_builder.py`.
- Additive policy inputs are preferred; repurposing existing fields is forbidden.
- Removing or changing semantics of existing inputs requires a major policy version.
- New enforcement checks must preserve fail-closed behavior on evaluation errors.
- Any policy evolution must keep worker rails (`_apply_rails`) as non-bypass controls.

## Policy Versioning Strategy

Policy version must be externally traceable and loggable.

Minimum standard:

- `policy_version` value is attached to every decision log record.
- Value source should be immutable (OPA bundle digest, policy git SHA, or release tag).
- Rollbacks must be version-explicit; no silent in-place mutation.

TODO: verify in `infra/` where authoritative policy version metadata is injected at runtime.
TODO: verify in `src/cacp/policy/opa_client.py` whether OPA result payload exposes policy metadata directly.

## No-Bypass Guarantee

The repository enforces a no-bypass model through layered controls:

- Proposal path must pass compliance checks before signature and PR creation.
- Webhook-triggered execution requires signature verification on inbound GitHub events.
- Worker execution always passes compliance rails before adapter execution.
- Event append and structured logs provide post-fact traceability for allow/deny outcomes.

Any future endpoint or worker path that invokes adapters without these controls is
considered a policy bypass and must be rejected in review.
