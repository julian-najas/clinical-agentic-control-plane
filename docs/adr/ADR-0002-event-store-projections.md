# ADR-0002: Event Store + Projections (Lecturas Derivadas)

## Status

Accepted

## Date

2026-02-16

## Context

El control-plane necesita persistir todo lo que ocurre (ingestas de citas,
propuestas generadas, decisiones OPA, PRs creados, ejecuciones) para
auditoría, replay y análisis.

Opciones evaluadas:
- A) CRUD tradicional con tablas por entidad → pierde historia, no replay.
- B) Event sourcing puro (Kafka + event bus) → overengineering para Day-1.
- C) Event store append-only en PostgreSQL + projections.

## Decision

Adoptamos **C**: event store minimalista en PostgreSQL.

### Event store
- Tabla `events` append-only: `event_id`, `event_type`, `payload`, `actor`, `created_at`.
- Sin UPDATE ni DELETE — inmutabilidad garantizada.
- Payloads en JSONB para flexibilidad de esquema.

### Projections
- Vistas materializadas o queries sobre el event store.
- Ejemplo: `NoShowProjection` calcula tasa de no-show por clínica.
- Las projections son derivadas y reconstruibles desde events.

### Event types
- `appointment_ingested` — cita recibida.
- `risk_scored` — riesgo calculado.
- `proposal_generated` — acciones propuestas.
- `pr_created` — PR abierto en gitops-config.
- `pr_merged` — PR aprobado y mergeado.
- `action_executed` — acción ejecutada por worker.
- `no_show_recorded` — no-show confirmado.
- `appointment_confirmed` — paciente confirmó asistencia.
- `appointment_rescheduled` — paciente reagendó.

## Consequences

### Positive
- Audit trail completo y reproducible.
- Análisis temporal: "¿qué pasó con esta cita?"
- No hay pérdida de información por design.

### Negative
- Storage grows monotonically.
- Queries de lectura requieren projections (no normalized tables).

### Mitigations
- Archiving policy: events > 1 año → cold storage.
- Índices sobre `event_type` y `created_at`.
