# ADR-0003: OPA como Árbitro — Input Contract y Decision Log

## Status

Accepted

## Date

2026-02-16

## Context

El control-plane necesita validar que cada acción propuesta cumple las
políticas de la clínica antes de crear un PR. La lógica de políticas debe
ser externalizable y auditable.

Opciones evaluadas:
- A) Reglas hardcoded en Python → coupled, no auditable externamente.
- B) DSL custom para reglas → reinventar la rueda.
- C) OPA (Open Policy Agent) con Rego, policies versionadas en gitops.

## Decision

Adoptamos **C**: OPA como policy engine externo.

### Input contract
El control-plane construye un documento OPA input con campos estrictos:

```json
{
  "action": "send_sms",
  "role": "operator",
  "mode": "ALLOW",
  "patient_id": "PAT-001",
  "clinic_id": "CLINIC-A",
  "messages_sent_today": 2,
  "daily_limit": 5,
  "risk_score": 0.72,
  "environment": "dev"
}
```

El módulo `input_builder.py` es responsable de construir este payload
de forma consistente. Cambios en el input contract requieren update
coordinado entre control-plane y policies.

### Decision log
- Toda respuesta OPA (allow/deny + reasons) se persiste como evento.
- Event type: `opa_decision`.
- Payload incluye: input, result, policy version, timestamp.

### Fail-closed
- Si OPA no está disponible → deny all (no fallback permissive).
- Error de red, timeout, malformed response → deny + alert.

## Consequences

### Positive
- Policies desacopladas del código — cambio requiere solo merge en gitops.
- Deny-by-default — nuevas acciones son denegadas hasta whitelisting explícito.
- Decision log provee trazabilidad completa.

### Negative
- Network hop adicional (control-plane → OPA).
- Equipo debe aprender Rego.
- Input contract es un contrato implícito entre repos.

### Mitigations
- OPA como sidecar para minimizar latencia.
- Input contract documentado en `specs/` con JSON Schema.
- Tests OPA en CI obligatorios antes de merge.
