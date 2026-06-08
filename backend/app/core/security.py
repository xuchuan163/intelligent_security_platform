from dataclasses import asdict, dataclass
from enum import StrEnum

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Query, Session

from app.core.config import settings
from app.infrastructure.database.session import get_db


class DataScope(StrEnum):
    """Legacy MVP mock scopes used before the real IAM service is connected."""

    TENANT = "tenant"
    ORG = "org"


class ScopeType(StrEnum):
    """Company-project scope model used by the Phase 2 compatibility layer."""

    COMPANY = "company"
    PROJECT = "project"


def _scope_from_legacy(data_scope: DataScope) -> ScopeType:
    if data_scope == DataScope.ORG:
        return ScopeType.PROJECT
    return ScopeType.COMPANY


def _parse_project_ids(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


http_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class MockUser:
    user_id: str
    user_name: str
    tenant_id: str
    org_path: str
    role: str
    data_scope: DataScope = DataScope.TENANT
    company_id: str | None = None
    scope_type: ScopeType | None = None
    authorized_project_ids: tuple[str, ...] = ()
    subcontractor_id: str | None = None
    permissions: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    auth_source: str = "mock"

    def __post_init__(self) -> None:
        if self.company_id is None:
            object.__setattr__(self, "company_id", self.tenant_id)
        if self.scope_type is None:
            object.__setattr__(self, "scope_type", _scope_from_legacy(self.data_scope))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["data_scope"] = self.data_scope.value
        data["scope_type"] = self.scope_type.value if self.scope_type else None
        data["authorized_project_ids"] = list(self.authorized_project_ids)
        data["permissions"] = list(self.permissions)
        data["roles"] = list(self.roles)
        data["auth_source"] = self.auth_source
        return data


def _mock_user_from_headers(
    x_mock_user_id: str,
    x_mock_user_name: str,
    x_tenant_id: str,
    x_org_path: str,
    x_role: str,
    x_data_scope: str,
    x_company_id: str | None,
    x_scope_type: str | None,
    x_authorized_project_ids: str | None,
    x_subcontractor_id: str | None,
) -> MockUser:
    try:
        data_scope = DataScope(x_data_scope)
    except ValueError:
        data_scope = DataScope.TENANT

    try:
        scope_type = ScopeType(x_scope_type) if x_scope_type else None
    except ValueError:
        scope_type = None

    return MockUser(
        user_id=x_mock_user_id,
        user_name=x_mock_user_name,
        tenant_id=x_tenant_id,
        org_path=x_org_path,
        role=x_role,
        data_scope=data_scope,
        company_id=x_company_id or x_tenant_id,
        scope_type=scope_type,
        authorized_project_ids=_parse_project_ids(x_authorized_project_ids),
        subcontractor_id=x_subcontractor_id,
        auth_source="mock",
    )


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    x_mock_user_id: str = Header("mock-admin", alias="X-Mock-User-Id"),
    x_mock_user_name: str = Header("Platform Admin", alias="X-Mock-User-Name"),
    x_tenant_id: str = Header("CSCEC", alias="X-Tenant-Id"),
    x_org_path: str = Header("CSCEC", alias="X-Org-Path"),
    x_role: str = Header("platform_admin", alias="X-Role"),
    x_data_scope: str = Header(DataScope.TENANT.value, alias="X-Data-Scope"),
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    x_scope_type: str | None = Header(None, alias="X-Scope-Type"),
    x_authorized_project_ids: str | None = Header(None, alias="X-Authorized-Project-Ids"),
    x_subcontractor_id: str | None = Header(None, alias="X-Subcontractor-Id"),
) -> MockUser:
    """Resolve the current user from JWT Bearer token or mock headers."""

    if credentials is not None and credentials.scheme.lower() == "bearer":
        from app.services.auth.login_service import AuthenticationError, resolve_user_from_access_token

        try:
            return resolve_user_from_access_token(db, credentials.credentials)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    if settings.auth_mode == "jwt" and not settings.auth_allow_mock_headers:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return _mock_user_from_headers(
        x_mock_user_id=x_mock_user_id,
        x_mock_user_name=x_mock_user_name,
        x_tenant_id=x_tenant_id,
        x_org_path=x_org_path,
        x_role=x_role,
        x_data_scope=x_data_scope,
        x_company_id=x_company_id,
        x_scope_type=x_scope_type,
        x_authorized_project_ids=x_authorized_project_ids,
        x_subcontractor_id=x_subcontractor_id,
    )


def _has_column(model, column_name: str) -> bool:
    return hasattr(model, column_name)


def _company_column(model):
    if _has_column(model, "company_id"):
        return model.company_id
    if _has_column(model, "tenant_id"):
        return model.tenant_id
    return None


def apply_data_scope(query: Query, model, current_user: MockUser) -> Query:
    """Apply the shared company/project data boundary to a SQLAlchemy query."""

    company_column = _company_column(model)
    if company_column is not None:
        query = query.filter(company_column == current_user.company_id)

    if current_user.scope_type == ScopeType.PROJECT:
        if current_user.authorized_project_ids and _has_column(model, "project_id"):
            return query.filter(model.project_id.in_(current_user.authorized_project_ids))
        if _has_column(model, "org_path"):
            return query.filter(model.org_path.like(f"{current_user.org_path}%"))

    return query


def assert_project_access(project_id: str | None, current_user: MockUser) -> None:
    """Reject path/body project ids outside the current user's project scope."""

    if (
        project_id
        and current_user.scope_type == ScopeType.PROJECT
        and current_user.authorized_project_ids
        and project_id not in current_user.authorized_project_ids
    ):
        raise PermissionError("No permission to access this project")
