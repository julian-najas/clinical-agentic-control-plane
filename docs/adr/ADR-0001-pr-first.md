# ADR-0001: PR-First — El Sistema No Ejecuta Sin Merge

## Status

Accepted

## Date

2026-02-16

## Context

El control-plane agentic genera propuestas de acción (enviar SMS, WhatsApp,
ofrecer reagendamiento). La pregunta es: ¿cuándo y cómo se ejecutan?

Opciones evaluadas:
- A) Ejecución directa tras scoring → rápido, pero sin revisión humana.
- B) Cola de aprobación in-app → duplica Git como sistema de revisión.
- C) PR-first: toda propuesta se materializa como PR en `clinic-gitops-config`.

## Decision

Adoptamos **C**: PR-first.

### Invariante
**Ninguna acción patient-facing se ejecuta sin que un PR haya sido mergeado.**

### Flujo
1. Orchestrator genera acciones.
2. Revenue Agent secuencia acciones por riesgo.
3. Compliance Agent valida contra messaging limits.
4. Signing module firma con HMAC-SHA256.
5. GitOps module abre PR en `clinic-gitops-config`.
6. CI valida (OPA tests + schema + HMAC).
7. Merge (manual en prod, automerge en dev para low-risk).
8. Webhook notifica este repo → Worker ejecuta.

### Automerge (dev only)
- PRs automatizados con HMAC verificado y label `automated`.
- Solo aplica a propuestas low-risk en `dev`.
- Nunca en `prod`.

## Consequences

### Positive
- Audit trail completo (git history).
- Natural separation of proposal vs. execution.
- Rollback = revert PR.

### Negative
- Latencia (minutos, no segundos).
- Dependencia de GitHub como middleware crítico.

### Mitigations
- Break-glass para emergencias (bypass PR, audit obligatorio).
- Automerge en dev para flujo rápido durante desarrollo.
