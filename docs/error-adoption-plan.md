# Error Adoption Plan

This document maps current runtime behavior to the target error contract in
`docs/error-model.md` and `specs/contracts/error.schema.json`.

## Adoption Matrix

| Surface | Current behavior | Target behavior | Gap |
|---------|------------------|-----------------|-----|
| `POST /ingest` | Validation errors handled by framework defaults | `INVALID_REQUEST` payload contract | Add centralized exception mapping |
| `POST /webhook/github` | Mixed custom responses (`401`, `400`, `503`, `202`) | Contractual error payload for error statuses | Normalize response body for error statuses |
| `POST /webhook/twilio-status` | Returns `403` with `{ "error": "invalid_signature" }` | `SIGNATURE_INVALID` payload contract | Align response schema |
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

TODO: verify in `tests/` where API error contract tests should be anchored.
