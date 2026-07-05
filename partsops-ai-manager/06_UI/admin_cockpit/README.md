# Admin Cockpit

## Purpose
- `admin_cockpit` is the operator UI for `PartsOps AI Manager`.
- The target is a premium operations control plane, not a generic dashboard.

## Current state
- React + TypeScript + Vite frontend.
- Tailwind-driven styling with project CSS variables in `src/index.css`.
- Existing UI is an early mock and should be treated as structural scaffolding, not final design.

## Design brief
- Make the interface more premium, more logical, more filled with useful information, and more functional.
- Preserve fast triage workflows for requests, suppliers, approvals, and invoice actions.
- Increase functional density and explainability: every major panel should answer what is happening, why it matters, and what to do next.
- Treat the cockpit as a shell/workspace/rail control plane: overview, supplier workspace, request triage, request workspace, and audit must stay linked by the same status semantics.
- Prefer derived or live data over decorative mock metrics. If backend data is missing, surface `partial`, `stale`, or `blocked` explicitly.

## Required redesign outcomes
- Stronger shell hierarchy between app frame, workspace, and focused side panels.
- Better information architecture for the overview screen.
- Richer operational widgets: system health, queue urgency, evidence summary, confidence/risk indicators, next-best actions.
- Consistent tokenized surfaces, status colors, focus states, and motion.
- Clear states for loading, empty, partial, stale, blocked, validated, and invoice-ready requests.

## UX validation
- `queue -> inspect -> compare -> approve/escalate -> draft ERP` is the core loop.
- Overview must answer: what is happening, what is blocked, what is urgent, and what to do next.
- Request workspace must expose normalization, matching, pricing, and audit as distinct steps.
- Approval and invoice actions must follow backend state-machine legality, not local hardcodes.

## Source of truth
- Project UI guide: `../../../DM obs/06-agents/ui-premium-design-system.md`

## Validation
```bash
npm install
npm run lint
npm run build
```
