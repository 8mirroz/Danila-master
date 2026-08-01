#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE=(docker-compose --env-file .env.staging -f docker-compose.staging.yml)
if [[ "${PARTSOPS_DOCKER_COMPOSE:-}" == "docker compose" ]]; then
  COMPOSE=(docker compose --env-file .env.staging -f docker-compose.staging.yml)
fi

suffix="$(date +%s)-$$"
organization_a="security-a-${suffix}"
organization_b="security-b-${suffix}"
username_a="security-a-${suffix}"
username_b="security-b-${suffix}"
email_a="${username_a}@proof.invalid"
email_b="${username_b}@proof.invalid"
password="ProofPass2026"
request_id=""
artifact_uri=""
client_id=""
upload_file="$(mktemp "${TMPDIR:-/tmp}/partsops-security-upload.XXXXXX.csv")"

kc() {
  "${COMPOSE[@]}" exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

cleanup_database() {
  "${COMPOSE[@]}" exec -T backend-staging python - "${organization_a}" "${organization_b}" "${request_id}" "${artifact_uri}" <<'PY' >/dev/null 2>&1 || true
import sys
from sqlalchemy import delete
from sqlmodel import Session
from app.automation.storage import storage
from database import engine
from models import (Membership, OnboardingState, Organization, PartRequest, RequestEvent,
                    Subscription, UploadArtifact, UsageEvent, User)

organization_a, organization_b, request_id, artifact_uri = sys.argv[1:]
if artifact_uri:
    try:
        storage.delete_file(artifact_uri)
    except ValueError:
        pass
with Session(engine) as session:
    for organization_id in (organization_a, organization_b):
        session.exec(delete(UploadArtifact).where(UploadArtifact.tenant_id == organization_id))
        session.exec(delete(RequestEvent).where(RequestEvent.tenant_id == organization_id))
        session.exec(delete(UsageEvent).where(UsageEvent.organization_id == organization_id))
        session.exec(delete(PartRequest).where(PartRequest.tenant_id == organization_id))
        session.exec(delete(Membership).where(Membership.organization_id == organization_id))
        session.exec(delete(OnboardingState).where(OnboardingState.organization_id == organization_id))
        session.exec(delete(Subscription).where(Subscription.organization_id == organization_id))
        session.exec(delete(Organization).where(Organization.organization_id == organization_id))
    session.exec(delete(User).where(User.email.in_([sys.argv[1].replace('security-a-', 'security-a-') + '@proof.invalid', sys.argv[2].replace('security-b-', 'security-b-') + '@proof.invalid'])))
    session.commit()
PY
}

cleanup() {
  if [[ -n "${client_id}" ]]; then
    kc update "clients/${client_id}" -r partsops -s directAccessGrantsEnabled=false >/dev/null 2>&1 || true
  fi
  for username in "${username_a}" "${username_b}"; do
    user_id="$(kc get users -r partsops -q "username=${username}" 2>/dev/null | sed -n 's/.*"id" : "\([^"]*\)".*/\1/p' | head -1 || true)"
    if [[ -n "${user_id}" ]]; then
      kc delete "users/${user_id}" -r partsops >/dev/null 2>&1 || true
    fi
  done
  cleanup_database
  rm -f "${upload_file}"
}
trap cleanup EXIT

"${COMPOSE[@]}" exec -T keycloak sh -lc '/opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD"' >/dev/null
client_id="$(kc get clients -r partsops -q clientId=partsops-api | sed -n 's/.*"id" : "\([^"]*\)".*/\1/p' | head -1)"
[[ -n "${client_id}" ]] || { echo "PartsOps Keycloak client not found" >&2; exit 1; }
kc update "clients/${client_id}" -r partsops -s directAccessGrantsEnabled=true >/dev/null
sleep 1

for values in "${username_a}|${email_a}|${organization_a}" "${username_b}|${email_b}|${organization_b}"; do
  IFS='|' read -r username email organization_id <<<"${values}"
  kc create users -r partsops -s "username=${username}" -s "email=${email}" -s firstName=Security -s lastName=Proof -s emailVerified=true -s enabled=true -s "attributes.organization_id=${organization_id}" >/dev/null
  kc set-password -r partsops --username "${username}" --new-password "${password}" --temporary=false
  kc add-roles -r partsops --uusername "${username}" --rolename admin
done

"${COMPOSE[@]}" exec -T backend-staging python - "${organization_a}" "${email_a}" "${organization_b}" "${email_b}" <<'PY' >/dev/null
import sys
from sqlmodel import Session
from database import engine
from services.saas import provision_organization

with Session(engine) as session:
    provision_organization(session, organization_id=sys.argv[1], display_name="Security proof A", owner_email=sys.argv[2], provisioned_by="security-verifier")
    provision_organization(session, organization_id=sys.argv[3], display_name="Security proof B", owner_email=sys.argv[4], provisioned_by="security-verifier")
PY

token_for() {
  curl --silent --show-error \
    -d grant_type=password -d client_id=partsops-api -d "username=$1" -d "password=${password}" \
    http://localhost:8080/realms/partsops/protocol/openid-connect/token \
    | ./venv/bin/python -c 'import json, sys; response = json.load(sys.stdin); token = response.get("access_token"); token or sys.exit("OAuth password grant failed: " + str(response.get("error", "unknown")) + ": " + str(response.get("error_description", ""))); print(token)'
}
token_a="$(token_for "${username_a}")"
token_b="$(token_for "${username_b}")"

api_status() {
  curl --silent --output /dev/null --write-out '%{http_code}' "$@"
}
[[ "$(api_status -H "Authorization: Bearer ${token_a}" http://localhost:8000/api/session)" == "200" ]]
[[ "$(api_status -H "Authorization: Bearer ${token_b}" http://localhost:8000/api/session)" == "200" ]]

request_response="$(curl --fail --silent --show-error -X POST http://localhost:8000/api/requests \
  -H "Authorization: Bearer ${token_a}" -H 'Content-Type: application/json' \
  --data '{"source":"manual","text":"Security proof brake pad x1","customer_name":"Security proof"}')"
request_id="$(printf '%s' "${request_response}" | ./venv/bin/python -c 'import json, sys; response = json.load(sys.stdin); request_id = response.get("request", {}).get("request_id"); request_id or sys.exit("RFQ create failed: " + str(response.get("detail", "unknown"))); print(request_id)')"
[[ "$(api_status -H "Authorization: Bearer ${token_b}" "http://localhost:8000/api/requests/${request_id}")" == "404" ]]

printf 'part_number,quantity\nSECURITY-PROOF,1\n' >"${upload_file}"
upload_response="$(curl --fail --silent --show-error -X POST http://localhost:8000/api/attachments/upload \
  -H "Authorization: Bearer ${token_a}" -F "file=@${upload_file};type=text/csv")"
artifact_id="$(printf '%s' "${upload_response}" | ./venv/bin/python -c 'import json, sys; print(json.load(sys.stdin)["artifact_id"])')"
artifact_uri="$(printf '%s' "${upload_response}" | ./venv/bin/python -c 'import json, sys; print(json.load(sys.stdin)["stored_path"])')"
[[ "$(api_status -X POST -H "Authorization: Bearer ${token_b}" -H 'Content-Type: application/json' \
  --data "{\"artifact_id\":\"${artifact_id}\"}" http://localhost:8000/api/requests/import-from-artifact)" == "404" ]]

audit_before="$(curl --fail --silent --show-error -H "Authorization: Bearer ${token_a}" "http://localhost:8000/api/requests/${request_id}/audit")"
printf '%s' "${audit_before}" | ./venv/bin/python -c 'import json, sys; assert json.load(sys.stdin)["valid"] is True'
"${COMPOSE[@]}" exec -T backend-staging python - "${request_id}" "${organization_a}" <<'PY' >/dev/null
import sys
from sqlalchemy import text
from database import engine
with engine.begin() as connection:
    connection.execute(text("UPDATE requestevent SET payload_json = :payload WHERE request_id = :request_id AND tenant_id = :tenant_id"), {"payload": "{\"tampered\":true}", "request_id": sys.argv[1], "tenant_id": sys.argv[2]})
PY
audit_after="$(curl --fail --silent --show-error -H "Authorization: Bearer ${token_a}" "http://localhost:8000/api/requests/${request_id}/audit")"
printf '%s' "${audit_after}" | ./venv/bin/python -c 'import json, sys; assert json.load(sys.stdin)["valid"] is False'

echo "staging_security=passed oidc_cross_tenant=1 upload_scope=1 audit_tamper_detected=1"
