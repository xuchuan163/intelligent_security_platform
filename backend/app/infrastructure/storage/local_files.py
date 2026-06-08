import datetime as dt
import hashlib
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import settings
from app.core.security import MockUser, ScopeType

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class UploadLike(Protocol):
    filename: str | None
    content_type: str | None
    file: BinaryIO


def save_image(
    upload: UploadLike,
    tenant_id: str,
    project_id: str,
    uploaded_by: str,
    phase: str = "discovery",
    upload_dir: str | Path | None = None,
    max_bytes: int | None = None,
) -> dict:
    content_type = upload.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Only JPEG and PNG images are allowed")

    payload = upload.file.read()
    if hasattr(upload.file, "seek"):
        upload.file.seek(0)

    limit = max_bytes if max_bytes is not None else settings.max_upload_bytes
    if len(payload) > limit:
        raise ValueError("File exceeds max upload size")

    file_id = f"F-{dt.datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    suffix = ALLOWED_IMAGE_TYPES[content_type]
    base_dir = Path(upload_dir or settings.upload_dir)
    target_dir = base_dir / tenant_id / project_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{file_id}{suffix}"
    target_path.write_bytes(payload)

    return {
        "file_id": file_id,
        "phase": phase,
        "content_type": content_type,
        "file_name": upload.filename or f"{file_id}{suffix}",
        "url": f"/api/v1/files/{file_id}",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "uploaded_by": uploaded_by,
        "uploaded_at": dt.datetime.utcnow().isoformat(),
    }


def resolve_image_path(
    file_id: str,
    current_user: MockUser,
    upload_dir: str | Path | None = None,
) -> tuple[Path, str] | None:
    if "/" in file_id or "\\" in file_id or ".." in file_id:
        return None

    base_dir = Path(upload_dir or settings.upload_dir) / current_user.tenant_id
    project_dirs = _candidate_project_dirs(base_dir, current_user)
    content_type_by_suffix = {suffix: content_type for content_type, suffix in ALLOWED_IMAGE_TYPES.items()}

    for project_dir in project_dirs:
        for suffix, content_type in content_type_by_suffix.items():
            candidate = project_dir / f"{file_id}{suffix}"
            if candidate.is_file():
                return candidate, content_type
    return None


def _candidate_project_dirs(base_dir: Path, current_user: MockUser) -> list[Path]:
    if current_user.scope_type == ScopeType.PROJECT and current_user.authorized_project_ids:
        return [base_dir / project_id for project_id in current_user.authorized_project_ids]
    if not base_dir.is_dir():
        return []
    return [path for path in base_dir.iterdir() if path.is_dir()]
