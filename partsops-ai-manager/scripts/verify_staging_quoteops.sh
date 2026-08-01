#!/usr/bin/env bash
set -euo pipefail

# Prove the customer-facing QuoteOps workflow against the Docker staging stack:
# a real OIDC user imports a supplier feed and RFQ, the durable worker matches
# the position, an authorised approver issues a quote, and both exports work.
# Every IdP, PostgreSQL and object-storage record created by this verifier is
# removed before it exits.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE=(docker-compose --env-file .env.staging -f docker-compose.staging.yml)
if [[ "${PARTSOPS_DOCKER_COMPOSE:-}" == "docker compose" ]]; then
  COMPOSE=(docker compose --env-file .env.staging -f docker-compose.staging.yml)
fi

suffix="$(date +%s)-$$"
organization_id="quoteops-proof-${suffix}"
username="quoteops-proof-${suffix}"
email="${username}@proof.invalid"
password="ProofPass2026"
client_id=""
token=""
request_id=""
quote_id=""
run_id=""
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/partsops-quoteops-proof.XXXXXX")"
supplier_file="${work_dir}/supplier-feed.csv"
rfq_file="${work_dir}/rfq.csv"
quote_pdf="${work_dir}/quote.pdf"
quote_xlsx="${work_dir}/quote.xlsx"

kc() {
  "${COMPOSE[@]}" exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

cleanup_database() {
  "${COMPOSE[@]}" exec -T backend-staging python - "${organization_id}" "${email}" <<'PY' >/dev/null 2>&1 || true
import sys
from sqlalchemy import delete
from sqlmodel import Session, select

from app.automation.storage import storage
from database import engine
from models import (
    ApprovalTicket, ImportMapping, IntegrationConnection, Membership,
    OnboardingState, Organization, OutboundMessage, PartRequest, PipelineRun,
    PipelineRunEvent, PriceHistoryLedger, QuoteDocument, QuoteVersion,
    RequestEvent, Subscription, UploadArtifact, UsageEvent, User,
)
from suppliers import (
    Invoice, Supplier, SupplierActivityLog, SupplierCatalogItem, SupplierTable,
    SupplierTableRow,
)

organization_id, email = sys.argv[1:]
with Session(engine) as session:
    artifacts = session.exec(
        select(UploadArtifact).where(UploadArtifact.tenant_id == organization_id)
    ).all()
    for artifact in artifacts:
        try:
            storage.delete_file(artifact.stored_path)
        except (OSError, ValueError):
            pass

    for model in (
        PipelineRunEvent, PipelineRun, RequestEvent, OutboundMessage,
        ApprovalTicket,
    ):
        session.exec(delete(model).where(model.tenant_id == organization_id))
    for model in (SupplierActivityLog, SupplierTableRow, SupplierTable,
                  SupplierCatalogItem, PriceHistoryLedger, Invoice, Supplier):
        session.exec(delete(model).where(model.tenant_id == organization_id))
    session.exec(delete(UploadArtifact).where(UploadArtifact.tenant_id == organization_id))
    session.exec(delete(PartRequest).where(PartRequest.tenant_id == organization_id))
    session.exec(delete(UsageEvent).where(UsageEvent.organization_id == organization_id))
    session.exec(delete(QuoteVersion).where(QuoteVersion.organization_id == organization_id))
    session.exec(delete(QuoteDocument).where(QuoteDocument.organization_id == organization_id))
    session.exec(delete(ImportMapping).where(ImportMapping.organization_id == organization_id))
    session.exec(delete(IntegrationConnection).where(IntegrationConnection.organization_id == organization_id))
    session.exec(delete(Membership).where(Membership.organization_id == organization_id))
    session.exec(delete(OnboardingState).where(OnboardingState.organization_id == organization_id))
    session.exec(delete(Subscription).where(Subscription.organization_id == organization_id))
    session.exec(delete(Organization).where(Organization.organization_id == organization_id))
    session.exec(delete(User).where(User.email == email))
    session.commit()
PY
}

cleanup() {
  if [[ -n "${client_id}" ]]; then
    kc update "clients/${client_id}" -r partsops -s directAccessGrantsEnabled=false >/dev/null 2>&1 || true
  fi
  user_id="$(kc get users -r partsops -q "username=${username}" 2>/dev/null | sed -n 's/.*"id" : "\([^"]*\)".*/\1/p' | head -1 || true)"
  if [[ -n "${user_id}" ]]; then
    kc delete "users/${user_id}" -r partsops >/dev/null 2>&1 || true
  fi
  cleanup_database
  rm -rf "${work_dir}"
}
trap cleanup EXIT

json_field() {
  local field="$1"
  ./venv/bin/python -c "import json, sys; value=json.load(sys.stdin)${field}; print(value)"
}

"${COMPOSE[@]}" exec -T keycloak sh -lc '/opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD"' >/dev/null
client_id="$(kc get clients -r partsops -q clientId=partsops-api | sed -n 's/.*"id" : "\([^"]*\)".*/\1/p' | head -1)"
[[ -n "${client_id}" ]] || { echo "PartsOps Keycloak client not found" >&2; exit 1; }
kc update "clients/${client_id}" -r partsops -s directAccessGrantsEnabled=true >/dev/null
sleep 1
kc create users -r partsops -s "username=${username}" -s "email=${email}" -s firstName=QuoteOps -s lastName=Proof -s emailVerified=true -s enabled=true -s "attributes.organization_id=${organization_id}" >/dev/null
kc set-password -r partsops --username "${username}" --new-password "${password}" --temporary=false
kc add-roles -r partsops --uusername "${username}" --rolename admin

"${COMPOSE[@]}" exec -T backend-staging python - "${organization_id}" "${email}" <<'PY' >/dev/null
import sys
from sqlmodel import Session
from database import engine
from services.saas import provision_organization

with Session(engine) as session:
    provision_organization(
        session,
        organization_id=sys.argv[1],
        display_name="QuoteOps proof",
        owner_email=sys.argv[2],
        provisioned_by="quoteops-verifier",
    )
PY

token="$(curl --fail --silent --show-error \
  -d grant_type=password -d client_id=partsops-api -d "username=${username}" -d "password=${password}" \
  http://localhost:8080/realms/partsops/protocol/openid-connect/token \
  | ./venv/bin/python -c 'import json, sys; payload=json.load(sys.stdin); token=payload.get("access_token"); token or sys.exit("OAuth password grant failed: " + str(payload)); print(token)')"
auth_header=( -H "Authorization: Bearer ${token}" )

session_payload="$(curl --fail --silent --show-error "${auth_header[@]}" http://localhost:8000/api/session)"
printf '%s' "${session_payload}" | ./venv/bin/python -c 'import json, sys; payload=json.load(sys.stdin); assert payload["tenant_id"].startswith("quoteops-proof-"); assert payload["role"] == "admin"'

erp_health="$(curl --fail --silent --show-error "${auth_header[@]}" http://localhost:8000/api/erp/connection-health)"
printf '%s' "${erp_health}" | ./venv/bin/python -c 'import json, sys; payload=json.load(sys.stdin); assert payload["status"] in {"connected", "not_configured", "credentials_missing", "unreachable", "authentication_failed", "unexpected_response"}; assert payload["dry_run"] is False; assert not ({"endpoint", "authorization", "api_key", "api_secret"} & payload.keys())'

supplier_response="$(curl --fail --silent --show-error -X POST http://localhost:8000/api/suppliers \
  "${auth_header[@]}" -H 'Content-Type: application/json' \
  --data '{"name":"QuoteOps verification supplier","reliability_score":0.95,"avg_delivery_days":2,"status":"active"}')"
supplier_id="$(printf '%s' "${supplier_response}" | json_field '["supplier_id"]')"

printf 'part_name,oem_number,brand,price,currency,stock_qty,delivery_days,category\nBrake Pad Proof,PROOF-BRAKE-001,PartsOps,1250,RUB,8,2,brake\n' >"${supplier_file}"
supplier_import="$(curl --fail --silent --show-error -X POST "http://localhost:8000/api/suppliers/${supplier_id}/tables/import" \
  "${auth_header[@]}" -F "file=@${supplier_file};type=text/csv" -F 'name=QuoteOps proof feed')"
printf '%s' "${supplier_import}" | ./venv/bin/python -c 'import json, sys; payload=json.load(sys.stdin); assert payload["status"] == "success"; assert payload["import_summary"]["imported_rows"] == 1'
items="$(curl --fail --silent --show-error "${auth_header[@]}" "http://localhost:8000/api/suppliers/${supplier_id}/items")"
printf '%s' "${items}" | ./venv/bin/python -c 'import json, sys; items=json.load(sys.stdin); assert len(items) == 1; assert items[0]["oem_number"] == "PROOF-BRAKE-001"'

printf 'part_number,description,quantity,brand\nPROOF-BRAKE-001,Brake Pad Proof,1,PartsOps\n' >"${rfq_file}"
upload_response="$(curl --fail --silent --show-error -X POST http://localhost:8000/api/attachments/upload \
  "${auth_header[@]}" -F "file=@${rfq_file};type=text/csv")"
artifact_id="$(printf '%s' "${upload_response}" | json_field '["artifact_id"]')"
preview="$(curl --fail --silent --show-error -X POST http://localhost:8000/api/rfq-imports/preview \
  "${auth_header[@]}" -H 'Content-Type: application/json' --data "{\"artifact_id\":\"${artifact_id}\"}")"
printf '%s' "${preview}" | ./venv/bin/python -c 'import json, sys; payload=json.load(sys.stdin); assert payload["valid_positions"] == 1; assert payload["requires_mapping"] is False'
mapping_name="QuoteOps proof mapping ${suffix}"
curl --fail --silent --show-error -X POST http://localhost:8000/api/rfq-imports/mappings \
  "${auth_header[@]}" -H 'Content-Type: application/json' \
  --data "{\"name\":\"${mapping_name}\",\"mapping\":{\"part_number\":\"part_number\",\"description\":\"description\",\"quantity\":\"quantity\",\"brand\":\"brand\"}}" >/dev/null
commit="$(curl --fail --silent --show-error -X POST http://localhost:8000/api/rfq-imports/commit \
  "${auth_header[@]}" -H 'Content-Type: application/json' \
  --data "{\"artifact_id\":\"${artifact_id}\",\"customer_name\":\"QuoteOps proof customer\"}")"
request_id="$(printf '%s' "${commit}" | json_field '["request"]["request_id"]')"
printf '%s' "${commit}" | ./venv/bin/python -c 'import json, sys; payload=json.load(sys.stdin); assert payload["import"]["valid_positions"] == 1; assert payload["idempotent"] is False'

run_response="$(curl --fail --silent --show-error -X POST "http://localhost:8000/api/requests/${request_id}/pipeline-runs" \
  "${auth_header[@]}" -H 'Content-Type: application/json' --data '{}')"
run_id="$(printf '%s' "${run_response}" | json_field '["run_id"]')"
for attempt in $(seq 1 45); do
  run_status="$(curl --fail --silent --show-error "${auth_header[@]}" "http://localhost:8000/api/requests/${request_id}/pipeline-runs/${run_id}")"
  state="$(printf '%s' "${run_status}" | json_field '["status"]')"
  if [[ "${state}" == "completed" ]]; then
    break
  fi
  if [[ "${state}" == "failed" || "${state}" == "blocked" ]]; then
    printf '%s\n' "${run_status}" >&2
    exit 1
  fi
  sleep 1
done
[[ "${state}" == "completed" ]] || { echo "Timed out waiting for durable pipeline run" >&2; exit 1; }

approval="$(curl --fail --silent --show-error -X POST "http://localhost:8000/api/requests/${request_id}/approve" \
  "${auth_header[@]}" -H 'Content-Type: application/json' --data '{"action":"approve","comment":"QuoteOps staging proof"}')"
quote_id="$(printf '%s' "${approval}" | json_field '["quote"]["quote_id"]')"
printf '%s' "${approval}" | ./venv/bin/python -c 'import json, sys; payload=json.load(sys.stdin); assert payload["new_status"] == "APPROVED"; assert payload["quote"]["version"] == 1; assert payload["quote"]["selected_offers"]'

pdf_type="$(curl --fail --silent --show-error -o "${quote_pdf}" -w '%{content_type}' "${auth_header[@]}" "http://localhost:8000/api/quotes/${quote_id}/export/pdf")"
xlsx_type="$(curl --fail --silent --show-error -o "${quote_xlsx}" -w '%{content_type}' "${auth_header[@]}" "http://localhost:8000/api/quotes/${quote_id}/export/xlsx")"
[[ "${pdf_type}" == application/pdf* && -s "${quote_pdf}" ]]
[[ "${xlsx_type}" == application/vnd.openxmlformats-officedocument* && -s "${quote_xlsx}" ]]
usage="$(curl --fail --silent --show-error "${auth_header[@]}" http://localhost:8000/api/billing/usage)"
printf '%s' "${usage}" | ./venv/bin/python -c 'import json, sys; payload=json.load(sys.stdin); assert payload["positions_used"] == 1'

echo "staging_quoteops=passed oidc=1 erp_preflight=1 supplier_feed=1 rfq_import=1 durable_pipeline=1 quote_exports=2 usage=1"
