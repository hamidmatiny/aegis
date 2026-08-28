"""Authentication HTTP routes."""

from __future__ import annotations

from typing import Union

from fastapi import APIRouter, Request, Response, status

from aegis_smb_copilot.auth import service as auth_service
from aegis_smb_copilot.auth.schema import (
    AdminLoginRequest,
    AdminMeResponse,
    CustomerMeResponse,
    GuestMeResponse,
    LoginRequest,
    RegisterRequest,
)
from aegis_smb_copilot.auth.sessions import (
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    delete_session,
    session_from_request,
    set_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response) -> dict[str, str]:
    """Register email+password, creating a tenant and customer session."""
    tenant_id, slug, api_key, session = auth_service.register_customer(body)
    signed = create_session(session)
    set_session_cookie(response, signed)
    return {
        "tenant_id": str(tenant_id),
        "slug": slug,
        "api_key": api_key,
        "email": body.email,
    }


@router.post("/login")
def login(body: LoginRequest, response: Response) -> dict[str, str]:
    session = auth_service.login_customer(body.email, body.password)
    signed = create_session(session)
    set_session_cookie(response, signed)
    return {"status": "ok", "role": "customer"}


@router.post("/admin-login")
def admin_login(body: AdminLoginRequest, response: Response) -> dict[str, str]:
    session = auth_service.login_admin(body.username.strip(), body.password)
    signed = create_session(session)
    set_session_cookie(response, signed)
    return {"status": "ok", "role": "admin"}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        from aegis_smb_copilot.auth.sessions import _verify_signed

        token = _verify_signed(cookie)
        if token:
            delete_session(token)
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=None)
def me(request: Request) -> Union[CustomerMeResponse, AdminMeResponse, GuestMeResponse]:
    session = session_from_request(request)
    if session is None:
        return GuestMeResponse()
    if session.role == "admin":
        return AdminMeResponse(username=session.username or "")
    if session.role == "customer":
        from aegis_smb_copilot.auth.sessions import customer_tenant_id

        tenant_id = customer_tenant_id(session)
        email, slug, tier = auth_service.customer_me(tenant_id)
        return CustomerMeResponse(email=email, tenant_id=tenant_id, slug=slug, tier=tier)
    return GuestMeResponse()
