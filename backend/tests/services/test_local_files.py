from io import BytesIO

import pytest

from app.infrastructure.storage.local_files import save_image


class FakeUploadFile:
    def __init__(self, filename: str, content_type: str, payload: bytes) -> None:
        self.filename = filename
        self.content_type = content_type
        self.file = BytesIO(payload)


def test_save_image_writes_file_and_returns_attachment_metadata(tmp_path):
    upload = FakeUploadFile("hazard.jpg", "image/jpeg", b"fake-jpeg")

    item = save_image(
        upload,
        tenant_id="COMPANY-A",
        project_id="P002",
        uploaded_by="U-GC-01",
        phase="discovery",
        upload_dir=tmp_path,
        max_bytes=1024,
    )

    assert item["file_id"].startswith("F-")
    assert item["phase"] == "discovery"
    assert item["content_type"] == "image/jpeg"
    assert item["file_name"] == "hazard.jpg"
    assert item["url"] == f"/api/v1/files/{item['file_id']}"
    assert item["size_bytes"] == len(b"fake-jpeg")
    assert item["uploaded_by"] == "U-GC-01"
    assert len(item["sha256"]) == 64
    assert (tmp_path / "COMPANY-A" / "P002" / f"{item['file_id']}.jpg").read_bytes() == b"fake-jpeg"


def test_save_image_rejects_non_image_or_large_file(tmp_path):
    with pytest.raises(ValueError, match="Only JPEG and PNG images are allowed"):
        save_image(
            FakeUploadFile("note.txt", "text/plain", b"text"),
            tenant_id="COMPANY-A",
            project_id="P002",
            uploaded_by="U-GC-01",
            upload_dir=tmp_path,
        )

    with pytest.raises(ValueError, match="File exceeds max upload size"):
        save_image(
            FakeUploadFile("hazard.png", "image/png", b"x" * 5),
            tenant_id="COMPANY-A",
            project_id="P002",
            uploaded_by="U-GC-01",
            upload_dir=tmp_path,
            max_bytes=4,
        )
