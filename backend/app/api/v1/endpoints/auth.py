from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.responses import success
from app.core.security import MockUser, get_current_user
from app.infrastructure.database.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest
from app.services.auth.login_service import AuthenticationError, login, refresh_access_token
from app.services.auth.oauth import OAuthNotConfiguredError, build_oauth_authorize_payload, handle_oauth_callback
from app.services.auth.user_context import user_profile_dict

router = APIRouter()


@router.post("/login")
def auth_login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return success(login(db, tenant_id=body.tenant_id, user_id=body.user_id, password=body.password))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/refresh")
def auth_refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return success(refresh_access_token(db, refresh_token=body.refresh_token))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me")
def me(current_user: MockUser = Depends(get_current_user)) -> dict:
    return success(user_profile_dict(current_user))


@router.get("/oauth/authorize", response_model=None)
def oauth_authorize(
    request: Request,
    redirect: bool = Query(False, description="When true, HTTP-redirect to authorize_url (mock or IdP)."),
):
    try:
        payload = build_oauth_authorize_payload()
    except OAuthNotConfiguredError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if redirect:
        target = payload["authorize_url"]
        if target.startswith("/"):
            target = f"{str(request.base_url).rstrip('/')}{target}"
        return RedirectResponse(url=target, status_code=302)
    return success(payload)


@router.get("/oauth/callback", response_model=None)
def oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    frontend_redirect: bool = Query(
        False,
        description="When true and mock mode succeeds, redirect to OAUTH_FRONTEND_CALLBACK_URL with tokens in query.",
    ),
):
    try:
        tokens = handle_oauth_callback(
            db,
            code=code,
            state=state,
            error=error,
            error_description=error_description,
        )
    except OAuthNotConfiguredError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    if frontend_redirect and settings.oauth_frontend_callback_url:
        from urllib.parse import urlencode

        query = urlencode(
            {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": tokens["token_type"],
                "expires_in": tokens["expires_in"],
                "state": state or "",
            }
        )
        separator = "&" if "?" in settings.oauth_frontend_callback_url else "?"
        return RedirectResponse(
            url=f"{settings.oauth_frontend_callback_url}{separator}{query}",
            status_code=302,
        )

    return success(tokens)
