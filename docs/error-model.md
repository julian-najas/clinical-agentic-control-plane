# Error Model

## Purpose

Define a stable, machine-readable error contract for the control boundary.
This document does not change current code behavior; it defines the target
contract for consistent client handling.

## Conceptual Error Hierarchy

- `PolicyViolation`
- `RateLimitExceeded`
- `InvalidRequest`
- `SignatureInvalid`
- `InternalError`

## Canonical Mapping

| Conceptual Type | http_status | error_code |
|-----------------|------------:|------------|
| `PolicyViolation` | `403` | `POLICY_VIOLATION` |
| `RateLimitExceeded` | `429` | `RATE_LIMIT_EXCEEDED` |
| `InvalidRequest` | `400` | `INVALID_REQUEST` |
| `SignatureInvalid` | `401` | `SIGNATURE_INVALID` |
| `InternalError` | `500` | `INTERNAL_ERROR` |

## Machine-Readable Error Payload

All API errors should conform to:

```json
{
  "error_code": "POLICY_VIOLATION",
  "message": "Policy denied action execute_plan",
  "request_id": "5f9c1e4d-1515-4d6f-b2ef-ec10e8f9bb74"
}
```

Recommended optional fields:

- `reason_code` (stable sub-classification)
- `details` (object with non-sensitive context)

Normative schema location:

- `specs/contracts/error.schema.json`

## Error-Type Guidance

### PolicyViolation

- Trigger: compliance checks or OPA decision deny.
- Response: `403 POLICY_VIOLATION`.

### RateLimitExceeded

- Trigger: execution rail returns `rate_limited`.
- Response: `429 RATE_LIMIT_EXCEEDED`.

### InvalidRequest

- Trigger: malformed JSON, schema/body validation failure, unsupported input.
- Response: `400 INVALID_REQUEST`.

### SignatureInvalid

- Trigger: invalid GitHub/Twilio signature or missing required signature in strict mode.
- Response: `401 SIGNATURE_INVALID`.

### InternalError

- Trigger: unexpected system failure (dependency error, unhandled exception).
- Response: `500 INTERNAL_ERROR`.

## Repository Alignment Notes

Current code already surfaces parts of this model in:

- Request validation: `src/cacp/api/routes/ingest.py`
- Signature verification: `src/cacp/api/routes/webhook_github.py`, `src/cacp/api/routes/webhook_twilio.py`
- Rate-limit rail reason: `src/cacp/workers/worker.py`
- OPA/policy denial path: `src/cacp/orchestration/agents/compliance_agent.py`

TODO: verify in `src/cacp/api/` where centralized exception-to-error-code mapping will be enforced.
TODO: verify in `src/cacp/api/app.py` whether global exception handlers should be standardized per this contract.
