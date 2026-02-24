# Error Adoption Plan

This document maps current runtime behavior to the target error contract in
`docs/error-model.md` and `specs/contracts/error.schema.json`.

## Enforced Today vs Target Standard

### Enforced today

- Global handlers in `src/cacp/api/app.py` normalize:
  - `RequestValidationError` -> `INVALID_REQUEST` (422)
  - generic `HTTPException` -> mapped `error_code` by status
  - unhandled exceptions -> `INTERNAL_ERROR` (500)
- Payload shape enforced by code in those handlers:
  - `error_code`
  - `message`
  - `request_id`
  - optional `details`
- Webhook signature failures use `HTTPException` and now conform to the same
  machine-readable payload contract.

### Target standard

- All explicit route-level error responses should use the same contract payload
  without exceptions.
- Error payloads should validate against `specs/contracts/error.schema.json`
  across 422, 4xx, and 5xx classes.
- Stable reason-code taxonomy should be consistently populated where applicable.

## Adoption Matrix

| Surface | Current behavior | Target behavior | Gap |
|---------|------------------|-----------------|-----|
| `POST /ingest` | Validation errors normalized by global handler | `INVALID_REQUEST` payload contract | Keep covered by contract tests |
| `POST /webhook/github` | Error statuses normalized via `HTTPException` handlers | Contractual error payload for error statuses | Keep route-level custom error responses out |
| `POST /webhook/twilio-status` | Signature errors normalized via `HTTPException` handlers | `SIGNATURE_INVALID` payload contract | Keep route-level custom error responses out |
| Worker rails (`rate_limited`, `no_consent`, `quiet_hours`) | Block reason stored in events/logs | Stable reason codes + optional API exposure if surfaced | Map reasons to canonical codes |

## Sequencing

1. Introduce global API exception handlers with `error_code` and `request_id`.
2. Normalize explicit webhook error responses to the same schema.
3. Map worker block reasons to canonical reason codes in logs/events.
4. Add contract tests validating `error.schema.json` for representative error responses.

## Constraints

- No endpoint additions.
- No contract-breaking changes to success responses.
- Keep backward compatibility during migration window.

TODO: verify in `tests/` where full API error contract tests should be anchored long term.
