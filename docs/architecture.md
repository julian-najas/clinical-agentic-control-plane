# Architecture — Clinical Agentic Control Plane

## Overview

The control-plane is a **FastAPI service** that orchestrates clinical no-show
reduction through a PR-first governance model. It never executes actions
without prior approval.

## Component diagram

```
                ┌─────────────────────────────────────────────────┐
                │            Control Plane (FastAPI)              │
                │                                                 │
  POST /ingest ─►  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
                │  │  Ingest   │  │Orchestr. │  │ HMAC + PR    │ │
                │  │  (routes) │─►│ (agents) │─►│  (gitops)    │─┼──► clinic-gitops-config
                │  └──────────┘  └──────────┘  └──────────────┘ │
                │                                                 │
                │  ┌──────────────────────────────────────────┐  │
  POST /webhook ─► │  GitHub Webhook ──► Worker (execute)     │  │
                │  │                     ├── WhatsApp sender  │  │
                │  │                     └── Twilio sender    │  │
                │  └──────────────────┬───────────────────────┘  │
                │                     │                           │
                │                ┌────▼─────┐                    │
                │                │Event Store│                    │
                │                │   (PG)    │                    │
                │                └──────────┘                    │
                └─────────────────────────────────────────────────┘
```

## Module map

| Module | Responsibility |
|--------|---------------|
| `api/app.py` | FastAPI app factory, middleware, lifespan |
| `api/routes/ingest.py` | Appointment ingestion endpoint |
| `api/routes/webhook_github.py` | GitHub PR merge webhook |
| `api/routes/health.py` | Health and metrics endpoints |
| `orchestration/orchestrator.py` | Coordinates scoring → sequencing → governance |
| `orchestration/agents/revenue_agent.py` | Generates action sequences by risk level |
| `orchestration/agents/compliance_agent.py` | Validates proposals against policies |
| `policy/opa_client.py` | OPA HTTP client |
| `policy/input_builder.py` | Builds OPA input from proposal context |
| `signing/canonical.py` | Canonical JSON serialisation |
| `signing/hmac.py` | HMAC-SHA256 signing and verification |
| `gitops/manifest.py` | Builds plan manifests for gitops-config |
| `gitops/github_pr.py` | Creates PRs via GitHub API |
| `storage/event_store.py` | Append-only PostgreSQL event log |
| `storage/projections.py` | Read-model projections from events |
| `queue/redis.py` | Redis connection management |
| `queue/enqueue.py` | Enqueue actions for worker execution |
| `workers/worker.py` | Processes queued actions post-merge |
| `workers/adapters/noop.py` | No-op adapter for testing |

## Request flow

1. **Ingest** — Appointments arrive via API or CSV import.
2. **Score** — `risk_scorer` assigns low/medium/high risk.
3. **Sequence** — `revenue_agent` generates an action sequence.
4. **Validate** — `compliance_agent` checks against OPA policies.
5. **Sign** — Proposal is HMAC-signed.
6. **PR** — Signed proposal is submitted as PR to gitops-config.
7. **(await merge)** — No action until PR is approved and merged.
8. **Webhook** — GitHub notifies the control-plane of the merge.
9. **Execute** — Worker sends messages via WhatsApp/SMS.
10. **Store** — Events recorded in PostgreSQL.

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| PR-first governance | No action without auditable approval |
| HMAC-signed proposals | Tamper-evident, verifiable origin |
| Event sourcing | Full replay capability, audit trail |
| Deterministic scoring | Predictable, testable, no ML dependency in MVP |
| Adapter pattern for messaging | Swap WhatsApp/Twilio without touching orchestration |
