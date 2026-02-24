"""
Internal request authentication and tenant context helpers.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from hmac import compare_digest
from typing import Any, Optional

import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from config import settings

_context_var: ContextVar["InternalContext | None"] = ContextVar("becertain_internal_context", default=None)


@dataclass(frozen=True)
class InternalContext:
    tenant_id: str
    org_id: str
    user_id: str
    username: str
    permissions: list[str]
    group_ids: list[str]
    role: str
    is_superuser: bool


def _context_algorithms() -> list[str]:
    raw = settings.context_algorithms or "HS256"
    return [v.strip() for v in str(raw).split(",") if v.strip()] or ["HS256"]


def _parse_bearer(auth_header: str | None) -> str:
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    return parts[1].strip()


def _decode_context_token(token: str) -> dict[str, Any]:
    key = settings.context_verify_key
    if not key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing context verify key")
    try:
        return jwt.decode(
            token,
            key,
            algorithms=_context_algorithms(),
            audience=settings.context_audience,
            issuer=settings.context_issuer,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Context token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid context token") from exc


def _build_context(payload: dict[str, Any]) -> InternalContext:
    tenant_id = str(payload.get("tenant_id", "")).strip()
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing tenant context")
    return InternalContext(
        tenant_id=tenant_id,
        org_id=str(payload.get("org_id", tenant_id)),
        user_id=str(payload.get("user_id", "")),
        username=str(payload.get("username", "")),
        permissions=list(payload.get("permissions") or []),
        group_ids=list(payload.get("group_ids") or []),
        role=str(payload.get("role", "user")),
        is_superuser=bool(payload.get("is_superuser", False)),
    )


def set_internal_context(ctx: InternalContext) -> Token:
    return _context_var.set(ctx)


def reset_internal_context(token: Token) -> None:
    _context_var.reset(token)


def get_internal_context() -> InternalContext | None:
    return _context_var.get()


def get_context_tenant(default_tenant: Optional[str] = None) -> str:
    ctx = get_internal_context()
    if ctx:
        return ctx.tenant_id
    if default_tenant:
        return default_tenant
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing tenant context")


def enforce_request_tenant(model: Any) -> Any:
    if model is None:
        return model
    tenant = get_context_tenant(getattr(model, "tenant_id", None))
    if hasattr(model, "model_copy"):
        return model.model_copy(update={"tenant_id": tenant})
    if hasattr(model, "copy"):
        return model.copy(update={"tenant_id": tenant})
    try:
        model.tenant_id = tenant
    except Exception:
        pass
    return model


def authenticate_internal_request(request: Request) -> InternalContext:
    expected_service_token = settings.expected_service_token
    if not expected_service_token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing expected service token")

    provided_service_token = request.headers.get("x-service-token", "")
    if not compare_digest(provided_service_token, expected_service_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")

    bearer = _parse_bearer(request.headers.get("authorization"))
    payload = _decode_context_token(bearer)
    return _build_context(payload)


def _requires_internal_auth(path: str) -> bool:
    return path.startswith("/api/v1") and path != "/api/v1/ready"


class InternalAuthMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        if not _requires_internal_auth(path):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        try:
            ctx = authenticate_internal_request(request)
        except HTTPException as exc:
            response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
            await response(scope, receive, send)
            return

        token = set_internal_context(ctx)
        scope.setdefault("state", {})
        scope["state"]["internal_context"] = ctx
        try:
            await self.app(scope, receive, send)
        finally:
            reset_internal_context(token)


async def internal_auth_middleware(request: Request, call_next):
    if not _requires_internal_auth(request.url.path):
        return await call_next(request)

    ctx = authenticate_internal_request(request)
    token = set_internal_context(ctx)
    request.state.internal_context = ctx
    try:
        return await call_next(request)
    finally:
        reset_internal_context(token)
