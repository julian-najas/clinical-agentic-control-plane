# Audit Model

## Purpose

Define the mandatory structured logging and traceability contract for decisions
at the security boundary. This is a formal standard document, not an
implementation change.

## Mandatory Structured Log Fields

Every auditable decision log entry MUST include:

- `event_id`
- `request_id`
- `actor`
- `action`
- `policy_version`
- `decision`
- `reason_code`
- `rate_limit_status`

Field intent:

- `event_id`: immutable identifier for the emitted audit event.
- `request_id`: request-scoped identifier propagated across services.
- `actor`: caller principal or system component initiating the action.
- `action`: normalized action identifier under evaluation/execution.
- `policy_version`: immutable version string of active policy set.
- `decision`: terminal decision value (`ALLOW`, `DENY`, `BLOCKED`, `ERROR`).
- `reason_code`: stable machine code explaining the decision.
- `rate_limit_status`: `passed`, `rate_limited`, or `not_applicable`.

## JSON Format Example

```json
{
  "timestamp": "2026-02-22T14:21:03.511Z",
  "event_id": "b4dd3e2e-2a84-4a4f-bbdf-2f8e6c36e4fd",
  "request_id": "5f9c1e4d-1515-4d6f-b2ef-ec10e8f9bb74",
  "correlation_id": "5f9c1e4d-1515-4d6f-b2ef-ec10e8f9bb74",
  "actor": "system:orchestrator",
  "action": "execute_plan",
  "policy_version": "opa:sha256:7f5c...",
  "decision": "DENY",
  "reason_code": "POLICY_VIOLATION",
  "rate_limit_status": "not_applicable"
}
```

## Controlled Vocabularies

### `action`

Minimum normalized values:

- `ingest_appointment`
- `evaluate_policy`
- `sign_proposal`
- `verify_github_webhook`
- `verify_twilio_webhook`
- `execute_plan`

TODO: verify in `src/cacp/storage/event_store.py` whether event_type and action should be mapped 1:1.

### `reason_code`

Minimum stable values:

- `POLICY_VIOLATION`
- `RATE_LIMIT_EXCEEDED`
- `NO_CONSENT`
- `QUIET_HOURS`
- `DUPLICATE_ACTION`
- `SIGNATURE_INVALID`
- `INVALID_REQUEST`
- `OPA_UNAVAILABLE`
- `INTERNAL_ERROR`

### `rate_limit_status`

Allowed values:

- `passed`
- `rate_limited`
- `not_applicable`

## Traceability Model (Correlation ID)

- Inbound clients may provide `x-correlation-id`; otherwise the API generates one.
- That ID is returned in response headers and reused as `request_id` for logs.
- Downstream events should persist this identifier for cross-component joins.
- `event_id` and `request_id` together provide decision-level and request-level traceability.

Current repository anchors:

- Correlation generation: `src/cacp/logging.py` (`new_correlation_id`).
- Correlation propagation header: `src/cacp/api/app.py` (`ObservabilityMiddleware`).
- Event identifiers: `src/cacp/storage/event_store.py` (`event_id`).

TODO: verify in `src/cacp/api/app.py` whether correlation ID is explicitly bound into all structured log records.

## Data Redaction Policy (Mandatory)

Structured logs MUST NOT include raw sensitive fields:

- Raw phone numbers
- Full message contents
- Secret material (`hmac_secret`, webhook secrets, API tokens)
- Full patient identifiers when hashed/tokenized form is available

Redaction strategy:

- Hash phone or external IDs when needed for correlation.
- Truncate opaque IDs to non-sensitive prefixes in human-readable logs.
- Keep full values only in explicitly protected stores, never in operational logs.

## Compliance Expectation

Any new endpoint, worker path, or adapter integration must emit records meeting
this minimum field contract before being considered production-grade.
