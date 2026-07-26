# Contract Control V2 Adaptation Report

Date: 2026-07-24

## Scope

Adapted the contract spare-parts list process into `partsops-ai-manager` as a controlled execution layer:

- contract audit and traceability registry;
- coverage and gap analysis;
- canonical internal registry as source of truth;
- separate OEM, analog, compatibility, price, screenshot, and approval evidence;
- workflow v2 with hard gates;
- internal and client XLSX exports generated from the same canonical data;
- client approval, purchase authorization, receipt verification, and archive records;
- exception lifecycle, operational metrics, crawler import adapter, and orchestration job.

## Implementation Plan Applied

1. Added contract audit, requirement, gap, decision, exception, approval, purchase, receipt, archive, OEM, analog, compatibility, workflow, and export persistence.
2. Moved contract behavior into service and router layers instead of `main.py`.
3. Added workflow locks so approval, client export, purchase, receipt, and archive cannot skip required evidence.
4. Added deterministic evidence checks: screenshot file ownership, image format, dimensions, SHA-256 hash, freshness, and export-time revalidation.
5. Added generated internal and client documents, both derived from the canonical registry hash.
6. Added UI controls for contract control, metrics, exceptions, OEM and analog candidate registration.
7. Added crawler-result upload/import path without modifying the separate dirty `my-crawler` worktree.
8. Added `contract_orchestrate` automation job that coordinates contract audit, evidence, pricing, export readiness, and workflow supervision without bypassing human approval.

## Validation

Executed successfully:

```bash
./venv/bin/python -m pytest -q tests/
npx tsc --noEmit -p tsconfig.app.json && npm run build
./venv/bin/alembic current
```

Results:

- backend: `209 passed, 1 skipped`;
- admin cockpit: TypeScript check and production build passed;
- Alembic: `c3d4e5f6a708 (head)`.

## Known Boundaries

- Screenshot validation is structural and deterministic. It validates PNG/JPEG readability, dimensions, completeness status, file hash, and export-time integrity. It does not perform full OCR or vision-model semantic comparison yet.
- Crawler integration accepts normalized external results through an adapter/upload path. It does not rewrite the separate `my-crawler` implementation in this branch.
- Human approval remains mandatory. The orchestration job can advance technical gates, but cannot authorize client approval or purchase by itself.

## Follow-Up Improvements

- Add an optional vision/OCR provider behind the existing screenshot validation fields.
- Add a scheduled runner for `contract_orchestrate` if this process should execute continuously rather than through API/manual automation runs.
- Add production storage retention and evidence export bundle policies for long-term contract archives.
