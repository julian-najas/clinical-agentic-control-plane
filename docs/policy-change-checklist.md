# Policy Change Checklist

Use this checklist for any change affecting policy evaluation, policy inputs,
signing gates, or execution rails.

## Change Classification

- [ ] Additive policy change (non-breaking)
- [ ] Breaking policy change (requires major policy version)
- [ ] Emergency fix

## Required Inputs

- [ ] Clear change description and rationale
- [ ] Impacted modules listed (`src/cacp/policy/`, `src/cacp/orchestration/`, `src/cacp/workers/`)
- [ ] Policy version increment strategy documented
- [ ] Rollback strategy documented

## Safety Gates

- [ ] No bypass introduced around compliance checks
- [ ] No bypass introduced around signature verification/signing
- [ ] Fail-closed behavior preserved on dependency failure (OPA, webhook validation)
- [ ] Audit event/log coverage preserved for allow and deny paths

## Validation Evidence

- [ ] Contract/schema changes documented in `specs/contracts/` when applicable
- [ ] Security reviewer approval (CODEOWNERS)
- [ ] Changelog entry added

## Release Controls

- [ ] Rollout scope identified (dev/staging/prod)
- [ ] Backout trigger defined (what metric/log condition requires rollback)
- [ ] Post-deploy verification checklist completed
