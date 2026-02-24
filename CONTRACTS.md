# Contracts & Versioning

This repository enforces explicit contract versioning.


## Contract Versioning Model

Contracts integrators SHOULD include a `contract_version` field (string).
Enforcement at runtime may be partial or evolving; see implementation notes.

Example:

```json
{
  "contract_version": "v1",
  "type": "proposal",
  "payload": {}
}
```

## Compatibility Rules

* Additive changes → minor revision
* Breaking changes → new major contract version
* Old versions remain supported unless explicitly deprecated

## Evolution Policy

* No silent schema mutation
* No field repurposing
* Deprecations documented before removal
