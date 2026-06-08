from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(default="CSCEC", max_length=64)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class AuthUserOut(BaseModel):
    user_id: str
    user_name: str
    tenant_id: str
    company_id: str
    org_path: str
    role: str
    roles: list[str]
    permissions: list[str]
    scope_type: str
    authorized_project_ids: list[str]
    subcontractor_id: str | None = None
    auth_source: str = "jwt"


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserOut
