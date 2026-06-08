import pytest

from app.core.config import settings
from app.services.auth.jwt_tokens import TokenValidationError, create_access_token, create_refresh_token, decode_token


def test_access_and_refresh_tokens_decode_with_expected_type():
    access_token, _ = create_access_token(user_id="mock-admin", tenant_id="CSCEC")
    refresh_token = create_refresh_token(user_id="mock-admin", tenant_id="CSCEC")

    access_payload = decode_token(access_token, expected_type="access")
    refresh_payload = decode_token(refresh_token, expected_type="refresh")

    assert access_payload["sub"] == "mock-admin"
    assert refresh_payload["tenant_id"] == "CSCEC"


def test_decode_rejects_wrong_token_type():
    refresh_token = create_refresh_token(user_id="mock-admin", tenant_id="CSCEC")
    with pytest.raises(TokenValidationError):
        decode_token(refresh_token, expected_type="access")


def test_decode_rejects_tampered_token():
    access_token, _ = create_access_token(user_id="mock-admin", tenant_id="CSCEC")
    tampered = access_token[:-1] + ("a" if access_token[-1] != "a" else "b")
    with pytest.raises(TokenValidationError):
        decode_token(tampered, expected_type="access")
