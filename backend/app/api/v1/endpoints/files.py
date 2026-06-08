from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.rbac import require_permissions
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.storage.local_files import resolve_image_path

router = APIRouter()


@router.get("/{file_id}")
def get_file(
    file_id: str,
    current_user: MockUser = Depends(require_permissions(Permission.WORK_ORDERS_READ)),
) -> FileResponse:
    resolved = resolve_image_path(file_id, current_user)
    if resolved is None:
        raise HTTPException(status_code=404, detail="File not found")
    path, content_type = resolved
    return FileResponse(path, media_type=content_type)
