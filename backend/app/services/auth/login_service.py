from sqlalchemy.orm import Session

from app.infrastructure.database.models import UserAccount
from app.services.auth.jwt_tokens import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.services.auth.passwords import verify_password
from app.services.auth.user_context import build_mock_user_from_account, user_profile_dict


class AuthenticationError(ValueError):
    pass


def authenticate_user(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    password: str,
) -> UserAccount:
    account = (
        db.query(UserAccount)
        .filter(UserAccount.tenant_id == tenant_id, UserAccount.user_id == user_id)
        .first()
    )
    if account is None or account.status != "active":
        raise AuthenticationError("Invalid credentials")
    if not verify_password(password, account.password_hash):
        raise AuthenticationError("Invalid credentials")
    return account


def issue_token_pair(db: Session, account: UserAccount) -> dict:
    user = build_mock_user_from_account(db, account, auth_source="jwt")
    access_token, expires_in = create_access_token(
        user_id=account.user_id,
        tenant_id=account.tenant_id,
    )
    refresh_token = create_refresh_token(
        user_id=account.user_id,
        tenant_id=account.tenant_id,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user_profile_dict(user),
    }


def login(db: Session, *, tenant_id: str, user_id: str, password: str) -> dict:
    account = authenticate_user(db, tenant_id=tenant_id, user_id=user_id, password=password)
    return issue_token_pair(db, account)


def refresh_access_token(db: Session, *, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenValidationError as exc:
        raise AuthenticationError(str(exc)) from exc

    account = (
        db.query(UserAccount)
        .filter(
            UserAccount.tenant_id == payload["tenant_id"],
            UserAccount.user_id == payload["sub"],
        )
        .first()
    )
    if account is None or account.status != "active":
        raise AuthenticationError("Invalid credentials")
    return issue_token_pair(db, account)


def resolve_user_from_access_token(db: Session, access_token: str):
    try:
        payload = decode_token(access_token, expected_type="access")
    except TokenValidationError as exc:
        raise AuthenticationError(str(exc)) from exc

    account = (
        db.query(UserAccount)
        .filter(
            UserAccount.tenant_id == payload["tenant_id"],
            UserAccount.user_id == payload["sub"],
        )
        .first()
    )
    if account is None or account.status != "active":
        raise AuthenticationError("Invalid credentials")
    return build_mock_user_from_account(db, account, auth_source="jwt")
