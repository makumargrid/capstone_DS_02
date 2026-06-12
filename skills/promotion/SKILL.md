# Promotion Pipeline

## Lifecycle
```
custom node (approved) 
  → CAPTURE as candidate template in config/templates/
  → PROPERTY-TEST: N random valid params → build → invariants pass
  → HUMAN APPROVAL
  → PROMOTE to config/primitives/ (permanent)
  → Registry loud-guard validates on next import
```

## Gates
1. **Property-test battery**: Candidate must build deterministically with N random valid parameter sets and pass all invariant checks. Any failure = rejected.
2. **Human approval**: After property tests pass, human confirms the promotion.
3. **Registry loud-guard**: On promotion, the registry validates the new primitive exists and its builder/param_model resolve correctly.

## Rejection
Un-promoted candidates stay in config/templates/ and remain in the flagged custom lane.
Rejected candidates are removed from config/templates/.

## After promotion
- The primitive is available to all planners via `list_primitives()`
- Builds deterministically — same params → same solid
- Passes the registry loud-guard (Prompt 2 Invariant 4)
- Behaves like any other native primitive