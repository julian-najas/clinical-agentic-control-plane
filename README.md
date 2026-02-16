# clinical-agentic-control-plane

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

## Related repos

| Repo | Role |
|------|------|
| `clinic-gitops-config` | Approval boundary — receives HMAC-signed PRs from this service |
| `platform-infra` | Deploys this service (Docker Compose / K8s / ArgoCD) |
| `casf-core` | Zero-trust policy gateway (optional integration) |

## License

[Apache-2.0](LICENSE)
