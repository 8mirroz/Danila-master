# .design/ — Client Design DNA Profile

This directory contains the **two-layer Client Design DNA** profile for PartsOps Admin Cockpit.

## Layer 1 — Immutable Baseline
- `design-dna.json` — Brand baseline captured from live UI code: tokens, colors, radii, shadows, spacing, typography, effects.

## Layer 2 — Client Decisions
- `feedback-events.jsonl` — Append-only log of all client and team feedback events (never deleted).
- `decisions.jsonl` — Append-only log of design decision proposals, approvals, and rejections.

## Derived
- `effective-design-dna.json` — Deterministic merge of baseline + all approved decisions. **Do not edit manually.** Rebuild with: `agds-dna build-effective`.

## Implementation Binding
- `implementation.json` — Maps semantic DNA token paths to CSS custom property names in `src/index.css`.

## Commands (from admin_cockpit/ root)
```bash
# Record client feedback
agds-dna record-feedback --author "Danila" --scope "colors.accent" --feedback "accent is too cyan for client taste"

# Propose a design decision with explicit patch
agds-dna propose --author "Design Lead" --scope "colors.accent" --patch '{"tokens.colors.accent-primary.value": "#00D4C2"}' --feedback-id fb-xxxx

# Approve and rebuild effective profile
agds-dna approve --decision-id dec-xxxx --approver "Danila"

# Run drift audit
agds-dna audit --path .

# Rebuild effective profile manually
agds-dna build-effective --path .
```

## CI Usage
```yaml
- name: Design DNA Drift Audit
  run: agds-dna audit --path partsops-ai-manager/06_UI/admin_cockpit
```
> In pilot mode: audit is a **warning** (exit 0). Use `--strict` flag to enable blocking gate.
