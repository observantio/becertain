from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
import jwt

from api.security import (
    InternalAuthMiddleware,
    InternalContext,
    enforce_request_tenant,
    get_context_tenant,
    reset_internal_context,
    set_internal_context,
)
from config import settings


def _build_app():
    app = FastAPI()
    app.add_middleware(InternalAuthMiddleware)

    @app.get("/api/v1/tenant")
    async def tenant_echo(tenant_id: str = "spoofed-tenant"):
        return {"tenant_id": get_context_tenant(tenant_id)}

    return app


def _headers(payload):
    token = jwt.encode(payload, settings.context_verify_key, algorithm="HS256")
    return {
        "X-Service-Token": settings.expected_service_token,
        "Authorization": f"Bearer {token}",
    }


def _set_security_defaults():
    settings.expected_service_token = "internal-service-token"
    settings.context_verify_key = "very-secret-signing-key"
    settings.context_issuer = "beobservant-main"
    settings.context_audience = "becertain"
    settings.context_algorithms = "HS256"


def test_missing_service_token_rejected():
    _set_security_defaults()
    app = _build_app()
    client = TestClient(app)
    resp = client.get("/api/v1/tenant")
    assert resp.status_code == 401


def test_invalid_context_token_rejected():
    _set_security_defaults()
    app = _build_app()
    client = TestClient(app)
    resp = client.get(
        "/api/v1/tenant",
        headers={"X-Service-Token": settings.expected_service_token, "Authorization": "Bearer invalid"},
    )
    assert resp.status_code == 401


def test_valid_context_enforces_tenant_scope():
    _set_security_defaults()
    app = _build_app()
    client = TestClient(app)
    headers = _headers(
        {
            "iss": settings.context_issuer,
            "aud": settings.context_audience,
            "iat": 1_700_000_000,
            "exp": 4_700_000_000,
            "tenant_id": "tenant-from-context",
            "org_id": "tenant-from-context",
            "user_id": "u1",
            "username": "alice",
        }
    )
    resp = client.get("/api/v1/tenant?tenant_id=spoofed", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "tenant-from-context"


def test_enforce_request_tenant_overrides_payload():
    token = set_internal_context(
        InternalContext(
            tenant_id="ctx-tenant",
            org_id="ctx-tenant",
            user_id="u1",
            username="alice",
            permissions=[],
            group_ids=[],
            role="user",
            is_superuser=False,
        )
    )

    class Req(BaseModel):
        tenant_id: str
        start: int
        end: int

    try:
        req = Req(tenant_id="spoofed", start=1, end=2)
        scoped = enforce_request_tenant(req)
        assert scoped.tenant_id == "ctx-tenant"
    finally:
        reset_internal_context(token)
