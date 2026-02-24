# clinical-agentic-control-plane

> **Public by design** — This repository is public for demo / portfolio purposes.
> It contains **no secrets, credentials, or PHI**. Production configurations live in private infrastructure.

**PR-first agentic control plane** for clinical no-show reduction.

This service ingests appointments, scores risk, generates action proposals,
signs them with HMAC, and submits them as PRs to `clinic-gitops-config`.
Actions are **never executed without merge approval**.

## Architecture

```
Clinic Cloud API / CSV ──► Ingest
                              │
                              ▼
                        Orchestrator
                         ├── Risk Scorer (deterministic heuristic)
                         ├── Revenue Agent (action sequencing)
                         └── Compliance Agent (policy validation)
                              │
                              ▼
                      HMAC Sign + PR Create ──► clinic-gitops-config
                              │
                     (webhook: PR merged)
                              │
                              ▼
                         Worker (execute)
                         ├── WhatsApp sender
                         └── Twilio SMS sender
                              │
                              ▼
                        Event Store (PG)
```

## Key principles

- **No action without merge.** The control-plane proposes; humans (or automerge) approve.
- **HMAC-signed proposals.** Every PR payload is signed with HMAC-SHA256.
- **Event-sourced.** All events are appended to PostgreSQL for audit and replay.
- **Deterministic scoring.** Risk is calculated with heuristics, not ML (until Phase 3).
- **Fail-closed on governance.** If HMAC signing or policy validation fails, no PR is created.

## Quick start

```bash
# Local development
cd infra/local
docker compose up --build -d

# Run tests
pip install -e ".[dev]"
pytest -v

# Run the service
uvicorn cacp.api.app:app --reload --port 8080
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest` | Receive appointments (from Clinic Cloud or CSV) |
| `POST` | `/webhook/github` | Receive PR merge events → trigger execution |
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/metrics` | Prometheus text exposition |

## Inter-repo contracts

This service is the **producer** side of the governance boundary.
It generates proposals and delivers them as HMAC-signed PRs — but
**never executes anything until a PR is merged**.

### Outbound — toward `clinic-gitops-config`

| What | Format | Delivery |
|------|--------|----------|
| Execution plans | JSON (`specs/execution_plan.schema.json`) | HMAC-SHA256 signed, opened as PR via GitHub API |
| Message templates | JSON (`specs/template.schema.json`) | HMAC-SHA256 signed, opened as PR via GitHub API |

> **Signing contract**: canonical JSON (sorted keys, no extra whitespace,
> `signature` field excluded from digest). Key sourced from `HMAC_SECRET`
> environment variable (rotated every 90 days dev / 30 days prod).

### Inbound — from `clinic-gitops-config`

| What | Mechanism |
|------|-----------|
| PR merge event | GitHub webhook `POST /webhook/github`. Control-plane verifies webhook signature, then dispatches the merged plan to workers for execution. |

> Workers **only act on merge events** from `clinic-gitops-config`. Any other
> source is rejected.

### Dependency — `casf-core`

`casf-core` (v0.13.0, scope-frozen) can optionally sit in front of this
service as a zero-trust gateway. This service does **not** import `casf-core`
code; it consumes it as an HTTP edge enforcer. Domain logic stays here.

### Dependency — `platform-infra`

`platform-infra` deploys this service via ArgoCD / Kustomize. This service
has **no runtime dependency** on `platform-infra` — it only provides the
container image and health endpoints that `platform-infra` expects:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness probe (k8s `livenessProbe`) |
| `GET /ready` | Readiness probe (k8s `readinessProbe`) |
| `GET /metrics` | Prometheus scrape target |

### Contract invariants

1. **No action without merge** — proposals are PRs; execution requires merge webhook.
2. **Fail-closed on signing** — if HMAC key is absent, no PR is created.
3. **Event-sourced audit** — every ingest, proposal, merge, and execution is appended to PostgreSQL.
4. **Deterministic scoring** — risk heuristic is reproducible; no ML until Phase 3.

## Related repos

| Repo | Role |
|------|------|
| `clinic-gitops-config` | Approval boundary — receives HMAC-signed PRs from this service |
| `platform-infra` | Deploys this service (Docker Compose / K8s / ArgoCD) |
| `casf-core` | Zero-trust policy gateway (optional integration) |

## License

[Apache-2.0](LICENSE)
