from fastapi import APIRouter, Depends

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.services.config.bayesian_versions import list_bayesian_config_versions
from app.services.config.weight_versions import list_weight_config_versions

router = APIRouter()


@router.get("/weight-versions")
def get_weight_versions(
    current_user: MockUser = Depends(require_permissions(Permission.PROFILE_READ)),
) -> dict:
    _ = current_user
    return success(list_weight_config_versions())


@router.get("/bayesian-versions")
def get_bayesian_versions(
    current_user: MockUser = Depends(require_permissions(Permission.ANALYSIS_ATTRIBUTION)),
) -> dict:
    _ = current_user
    return success(list_bayesian_config_versions())
