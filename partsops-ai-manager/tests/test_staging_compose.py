"""Static staging invariants that prevent container-local OIDC failures."""

from pathlib import Path

COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.staging.yml"


def test_backend_uses_docker_reachable_jwks_url() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")

    assert "PARTSOPS_OIDC_JWKS_URL: http://keycloak:8080/realms/partsops/protocol/openid-connect/certs" in compose
    assert "urlopen(settings.OIDC_JWKS_URL" in compose
    assert "KC_HOSTNAME=localhost" in compose
    assert "AWS_ACCESS_KEY_ID: ${MINIO_ROOT_USER" in compose
    assert "AWS_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD" in compose
    assert "KC_HOSTNAME=http://" not in compose
