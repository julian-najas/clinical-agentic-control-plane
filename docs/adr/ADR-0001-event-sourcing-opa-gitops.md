# ADR-0001: Event Sourcing + OPA + GitOps

## Status

Accepted

## Date

2026-02-16

## Context

The clinical no-show control system needs to:

1. **Audit every decision** — regulatory and operational requirement.
2. **Enforce policies** before any patient-facing action.
3. **Separate approval from execution** — no automated action without review.

We evaluated three approaches:
- A) Traditional CRUD + manual approval workflow
- B) CQRS + event sourcing + embedded policy engine
- C) Event sourcing + external OPA + GitOps PR-first governance

## Decision

We adopt **approach C**: event sourcing + OPA + GitOps.

### Event sourcing
- All state changes are captured as immutable events in PostgreSQL.
- Enables full replay, audit trail, and temporal queries.
- The event store is append-only — no updates or deletes.

### OPA for policy evaluation
- Policies are externalised in Rego (deny-by-default).
- The control-plane sends OPA input and receives allow/deny decisions.
- Policy changes are versioned in `clinic-gitops-config`.

### GitOps PR-first governance
- The control-plane never executes actions directly.
- It creates HMAC-signed PRs in the gitops-config repo.
- Actions are only executed after PR merge (manual or automerge).
- This provides a natural audit trail via git history.

## Consequences

### Positive
- Full auditability — every decision is traceable.
- Separation of concerns — policy, approval, and execution are decoupled.
- Extensible — new policies or approval rules don't require code changes.

### Negative
- Latency — PR-merge-execute adds delay vs. direct execution.
- Complexity — three repos to manage instead of one.
- Learning curve — team must understand OPA/Rego and GitOps workflows.

### Mitigations
- Automerge for low-risk, HMAC-verified proposals in dev.
- Break-glass override for urgent situations.
- Comprehensive runbooks and documentation.
