"""OAuth2/OIDC placeholder for future CSCEC IdP integration (Phase 3-A.6)."""

import secrets
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.auth.login_service import issue_token_pair
from app.infrastructure.database.models import UserAccount


class OAuthNotConfiguredError(HTTPException):
    def __init__(self, message: str = "OAuth2 provider is not configured") -> None:
        super().__init__(status_code=501, detail=message)


def _oauth_mode() -> str:
    if settings.oauth_enabled:
        return "live"
    if settings.oauth_mock_enabled:
        return "mock"
    return "disabled"


def build_oauth_authorize_payload() -> dict[str, Any]:
    state = secrets.token_urlsafe(16)
    mode = _oauth_mode()

    if mode == "disabled":
        raise OAuthNotConfiguredError("OAuth2 is disabled. Set OAUTH_MOCK_ENABLED=true for local demo.")

    if mode == "mock":
        query = urlencode(
            {
                "code": settings.oauth_mock_code,
                "state": state,
            }
        )
        callback_path = "/api/v1/auth/oauth/callback"
        authorize_url = f"{callback_path}?{query}"
        return {
            "mode": "mock",
            "state": state,
            "authorize_url": authorize_url,
            "callback_path": callback_path,
            "message": "IdP not connected; use authorize_url to complete mock OAuth2 code flow.",
        }

    params = {
        "response_type": "code",
        "client_id": settings.oauth_client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "scope": settings.oauth_scopes,
        "state": state,
    }
    authorize_url = f"{settings.oauth_authorize_url}?{urlencode(params)}"
    return {
        "mode": "live",
        "state": state,
        "authorize_url": authorize_url,
        "redirect_uri": settings.oauth_redirect_uri,
        "message": "Redirect end user to authorize_url. Token exchange is not implemented yet.",
    }


def handle_oauth_callback(
    db: Session,
    *,
    code: str | None,
    state: str | None,
    error: str | None,
    error_description: str | None,
) -> dict[str, Any]:
    if error:
        detail = error_description or error
        raise HTTPException(status_code=400, detail=f"OAuth2 authorization failed: {detail}")

    if not code:
        raise HTTPException(status_code=422, detail="Missing authorization code")

    mode = _oauth_mode()
    if mode == "mock":
        if code != settings.oauth_mock_code:
            raise HTTPException(status_code=401, detail="Invalid OAuth2 mock authorization code")
        account = (
            db.query(UserAccount)
            .filter(
                UserAccount.tenant_id == settings.oauth_default_tenant_id,
                UserAccount.user_id == settings.oauth_mock_user_id,
            )
            .first()
        )
        if account is None or account.status != "active":
            raise HTTPException(status_code=401, detail="OAuth2 mock user is not available")
        tokens = issue_token_pair(db, account)
        tokens["oauth"] = {
            "mode": "mock",
            "state": state,
            "provider": "mock-idp",
        }
        return tokens

    if mode == "live":
        raise OAuthNotConfiguredError(
            "OAuth2 token exchange with the corporate IdP is reserved for a later release."
        )

    raise OAuthNotConfiguredError()
