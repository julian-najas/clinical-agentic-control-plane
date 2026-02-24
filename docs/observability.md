# Observability Baseline

## Logging Standard (Structured JSON)

Every log entry SHOULD contain:

- event_id
- request_id
- actor
- action
- decision
- policy_result
- signature_status

Optional:
- tenant_id (if provided by integrator)

## Error Model

All errors should map to stable machine-readable codes:

Example:

```json
{
  "error_code": "CONTRACT_INVALID",
  "message": "Unsupported contract_version"
}
```

## Auditability

* All state transitions are event-recorded.
* Decisions are signed or validated when applicable.
* No decision occurs without trace.
