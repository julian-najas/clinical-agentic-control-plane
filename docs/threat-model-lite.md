
# Threat Model (Lite)

**Note:** This threat model applies when `clinical-agentic-control-plane` is deployed standalone. In layered deployments, most boundary controls are enforced by `casf-core`.

## Scope

Security and compliance enforcement boundary only. This is a lightweight model
for due diligence and engineering prioritization.

## Top Threats and Current Controls

### 1. Forged webhook event triggers unauthorized execution

- Threat: attacker sends fake GitHub/Twilio callbacks.
- Current controls:
  - GitHub HMAC verification in `src/cacp/api/routes/webhook_github.py`
  - Twilio signature verification in `src/cacp/api/routes/webhook_twilio.py`
- Residual risk: secret handling and rotation maturity.

### 2. Policy bypass due to evaluation failure

- Threat: policy engine unavailable and request still allowed.
- Current controls:
  - Fail-closed OPA error handling in `src/cacp/policy/opa_client.py`
  - Compliance deny path in `src/cacp/orchestration/agents/compliance_agent.py`
- Residual risk: policy version traceability is not yet explicit end-to-end.

### 3. Replay/duplicate execution

- Threat: repeated deliveries or duplicate actions execute multiple times.
- Current controls:
  - Webhook idempotency key with Redis in `src/cacp/api/routes/webhook_github.py`
  - Action dedup rail in `src/cacp/workers/worker.py`
- Residual risk: configuration drift in TTL settings.

### 4. Abuse via excessive message execution

- Threat: high-frequency execution degrades system and violates communication policy.
- Current controls:
  - Rate-limit rail in `src/cacp/workers/worker.py`
  - Quiet-hours and consent rails in `src/cacp/workers/worker.py`
- Residual risk: no single canonical reason-code taxonomy enforced yet.

### 5. Audit trail weakening

- Threat: decisions cannot be reliably reconstructed.
- Current controls:
  - Event append model in `src/cacp/storage/event_store.py`
  - Correlation ID propagation baseline in `src/cacp/logging.py` and `src/cacp/api/app.py`
- Residual risk: runtime deployments may still use in-memory event store.

TODO: verify in `infra/` where production event-store backend is enforced.

## Priority Actions

- Standardize reason codes and error payloads.
- Enforce key rotation evidence.
- Expand CODEOWNERS to multi-maintainer model.
