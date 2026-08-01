"""Static contract checks for the Keycloak realm imported by staging."""

from __future__ import annotations

import json
from pathlib import Path

REALM_PATH = Path(__file__).resolve().parents[1] / "01_CONFIGS" / "keycloak-realm.json"


def test_partsops_api_client_emits_required_oidc_claims() -> None:
    realm = json.loads(REALM_PATH.read_text(encoding="utf-8"))
    client = next(item for item in realm["clients"] if item["clientId"] == "partsops-api")

    assert client["publicClient"] is True
    assert client["standardFlowEnabled"] is True
    assert client["directAccessGrantsEnabled"] is False
    assert client["implicitFlowEnabled"] is False
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    assert client["fullScopeAllowed"] is True

    mappers = {item["name"]: item for item in client["protocolMappers"]}
    organization = mappers["organization_id"]
    assert organization["protocolMapper"] == "oidc-usermodel-attribute-mapper"
    assert organization["config"]["user.attribute"] == "organization_id"
    assert organization["config"]["claim.name"] == "organization_id"
    assert organization["config"]["access.token.claim"] == "true"

    roles = mappers["partsops realm roles"]
    assert roles["protocolMapper"] == "oidc-usermodel-realm-role-mapper"
    assert roles["config"]["claim.name"] == "realm_access.roles"
    assert roles["config"]["access.token.claim"] == "true"

    audience = mappers["partsops-api audience"]
    assert audience["protocolMapper"] == "oidc-audience-mapper"
    assert audience["config"]["included.client.audience"] == "partsops-api"
    assert audience["config"]["access.token.claim"] == "true"

    profile_components = realm["components"][
        "org.keycloak.userprofile.UserProfileProvider"
    ]
    profile = json.loads(profile_components[0]["config"]["kc.user.profile.config"][0])
    organization_profile = next(
        item for item in profile["attributes"] if item["name"] == "organization_id"
    )
    assert organization_profile["permissions"] == {
        "view": ["admin"],
        "edit": ["admin"],
    }
    assert profile["unmanagedAttributePolicy"] == "ADMIN_EDIT"
