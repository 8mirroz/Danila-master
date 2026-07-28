# Contract export templates

Place production XLSX templates here. The exporter looks for:

1. `PARTSOPS_CONTRACT_EXPORT_TEMPLATE` (env absolute/relative path)
2. `08_DATA/templates/Форма ответа_договор.xlsx`
3. `08_DATA/templates/test_custom_report.xlsx`
4. package-root / cwd fallbacks with the same filenames

## Rules

- **Do not** rely on absolute machine paths (`/Users/.../Downloads/...`).
- Prefer a checked-in **empty sample** name only if it contains no customer PII.
- Real contract forms with client branding can stay out of git; point env to them in STAGE/PROD.

## Example

```bash
export PARTSOPS_CONTRACT_EXPORT_TEMPLATE="/secure/path/Форма ответа_договор.xlsx"
# or
cp "/secure/path/Форма ответа_договор.xlsx" \
  partsops-ai-manager/08_DATA/templates/Форма\ ответа_договор.xlsx
```

If no template is found, export returns **422** with an explicit error (fail-closed).
