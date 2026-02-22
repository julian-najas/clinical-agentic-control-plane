## Description

<!-- Short summary of the change and why it is needed. -->

## Change Type

- [ ] New feature / agent
- [ ] Bugfix
- [ ] Refactor / internal improvement
- [ ] Configuration / infrastructure change
- [ ] Documentation
- [ ] Policy/security governance update

## Engineering Checklist

- [ ] Unit tests pass (`make test`)
- [ ] Lint passes (`make lint`)
- [ ] Type checks pass (`make typecheck`)
- [ ] Changelog updated when user-visible

## Security and Governance Checklist

- [ ] If `src/cacp/policy/`, `src/cacp/signing/`, or `src/cacp/workers/` changed, fail-closed behavior was verified.
- [ ] If policy behavior changed, `docs/policy-change-checklist.md` is completed.
- [ ] If error responses changed, alignment with `docs/error-model.md` and `specs/contracts/error.schema.json` was verified.
- [ ] Structured logging fields remain compliant with `docs/audit-model.md`.
- [ ] No bypass path introduced around webhook signature verification or compliance rails.

## Risk Notes

- [ ] Breaking change risk assessed
- [ ] Rollback approach documented
