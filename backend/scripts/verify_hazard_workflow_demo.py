"""Run the hazard upload -> work-order close demo through real API routes.

This script uses FastAPI's in-process TestClient against the configured local
database. It seeds the P002 demo roles, creates a fresh hazard through the
multipart API, moves the generated work order through the role-gated workflow,
and verifies the closed hazard plus flow-log count.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.models import Hazard, WorkOrderFlowLog
from app.infrastructure.database.session import SessionLocal
from app.main import app
from scripts.seed_demo_data import seed_work_order_workflow_demo


PROJECT_ID = "P002"
SUBCONTRACTOR_ID = "S003"


def _headers(user_id: str, role: str, subcontractor_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Tenant-Id": "CSCEC",
        "X-Company-Id": "CSCEC",
        "X-Mock-User-Id": user_id,
        "X-Role": role,
        "X-Scope-Type": "project",
        "X-Authorized-Project-Ids": PROJECT_ID,
    }
    if subcontractor_id:
        headers["X-Subcontractor-Id"] = subcontractor_id
    return headers


GC_HEADERS = _headers("U-GC-01", "gc_safety_officer")
DIRECTOR_HEADERS = _headers("U-DIR-01", "safety_director")
SUB_HEADERS = _headers("U-SUB-S003", "sub_safety_officer", SUBCONTRACTOR_ID)


def _assert_success(response, label: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise RuntimeError(f"{label} failed: HTTP {response.status_code} {response.text}")
    body = response.json()
    if body.get("code") != "SUCCESS":
        raise RuntimeError(f"{label} failed: {body}")
    return body["data"]


def main() -> None:
    db = SessionLocal()
    try:
        seed_work_order_workflow_demo(db)
    finally:
        db.close()

    client = TestClient(app)
    due_date = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    due_time = (dt.datetime.now() + dt.timedelta(days=3)).replace(microsecond=0).isoformat()

    created = _assert_success(
        client.post(
            f"/api/v1/projects/{PROJECT_ID}/hazards",
            data={
                "description": "基坑东侧临边防护缺失，存在坠落风险，需立即整改。",
                "hazard_type": "临边防护",
                "hazard_level": "major",
                "subcontractor_id": SUBCONTRACTOR_ID,
                "due_date": due_date,
                "location": "基坑东侧",
            },
            files={"images": ("hazard-demo.jpg", b"demo-discovery-image", "image/jpeg")},
            headers=GC_HEADERS,
        ),
        "upload hazard",
    )
    work_order_id = created["work_order_id"]
    hazard_id = created["hazard_id"]

    _assert_success(
        client.patch(
            f"/api/v1/work-orders/{work_order_id}/status",
            json={
                "action": "confirm",
                "assignee_user_id": "U-SUB-S003",
                "due_time": due_time,
                "comment": "请3日内完成整改。",
            },
            headers=DIRECTOR_HEADERS,
        ),
        "confirm work order",
    )
    _assert_success(
        client.patch(
            f"/api/v1/work-orders/{work_order_id}/status",
            json={"action": "accept", "comment": "已接单。"},
            headers=SUB_HEADERS,
        ),
        "accept work order",
    )
    _assert_success(
        client.patch(
            f"/api/v1/work-orders/{work_order_id}/status",
            data={"action": "submit_result", "comment": "临边防护已恢复。"},
            files={"images": ("rectification-demo.jpg", b"demo-rectification-image", "image/jpeg")},
            headers=SUB_HEADERS,
        ),
        "submit rectification",
    )
    _assert_success(
        client.patch(
            f"/api/v1/work-orders/{work_order_id}/status",
            json={"action": "review_pass", "comment": "复查合格，同意闭环。"},
            headers=GC_HEADERS,
        ),
        "review pass",
    )
    detail = _assert_success(
        client.get(f"/api/v1/work-orders/{work_order_id}", headers=GC_HEADERS),
        "get work order detail",
    )

    db = SessionLocal()
    try:
        hazard = db.query(Hazard).filter(Hazard.hazard_id == hazard_id).one()
        flow_count = db.query(WorkOrderFlowLog).filter(WorkOrderFlowLog.work_order_id == work_order_id).count()
    finally:
        db.close()

    if detail["status"] != "closed":
        raise RuntimeError(f"Expected closed work order, got {detail['status']}")
    if hazard.status != "closed":
        raise RuntimeError(f"Expected closed hazard, got {hazard.status}")
    if flow_count < 5:
        raise RuntimeError(f"Expected at least 5 flow logs, got {flow_count}")

    print("Hazard workflow demo passed")
    print(f"  hazard_id: {hazard_id}")
    print(f"  work_order_id: {work_order_id}")
    print(f"  work_order_status: {detail['status']}")
    print(f"  hazard_status: {hazard.status}")
    print(f"  flow_logs: {flow_count}")
    print(f"  attachments: {len((detail.get('attachments') or {}).get('items') or [])}")


if __name__ == "__main__":
    main()
