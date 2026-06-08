import datetime as dt
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.infrastructure.storage.local_files import save_image
from app.schemas.hazards import HazardCreatePayload
from app.services.hazards.service import create_hazard_with_work_order

router = APIRouter()


@dataclass
class _ParsedUpload:
    filename: str | None
    content_type: str | None
    file: BytesIO


@router.post("/{project_id}/hazards")
async def post_project_hazard(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.WORK_ORDERS_WRITE)),
) -> dict:
    try:
        fields, images = await _parse_multipart_request(request)
        if len(images) > 9:
            raise ValueError("At most 9 discovery images are allowed")
        attachments = [
            save_image(
                image,
                tenant_id=current_user.tenant_id,
                project_id=project_id,
                uploaded_by=current_user.user_id,
                phase="discovery",
            )
            for image in images
        ]
        payload = HazardCreatePayload(
            description=_required_field(fields, "description"),
            hazard_type=_required_field(fields, "hazard_type"),
            hazard_level=_required_field(fields, "hazard_level"),
            subcontractor_id=_required_field(fields, "subcontractor_id"),
            due_date=dt.date.fromisoformat(_required_field(fields, "due_date")),
            location=fields.get("location"),
        )
        result = create_hazard_with_work_order(db, project_id, payload, attachments, current_user)
        result["attachments"] = attachments
        return success(result)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _parse_multipart_request(request: Request) -> tuple[dict[str, str], list[_ParsedUpload]]:
    content_type = request.headers.get("content-type") or ""
    if "multipart/form-data" not in content_type:
        raise ValueError("Content-Type must be multipart/form-data")

    body = await request.body()
    raw_message = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode() + body
    message = BytesParser(policy=policy.default).parsebytes(raw_message)

    fields: dict[str, str] = {}
    images: list[_ParsedUpload] = []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            if name == "images":
                images.append(
                    _ParsedUpload(
                        filename=filename,
                        content_type=part.get_content_type(),
                        file=BytesIO(payload),
                    )
                )
            continue
        fields[name] = payload.decode(part.get_content_charset() or "utf-8")
    return fields, images


def _required_field(fields: dict[str, str], name: str) -> str:
    value = fields.get(name)
    if value is None or value == "":
        raise ValueError(f"{name} is required")
    return value
