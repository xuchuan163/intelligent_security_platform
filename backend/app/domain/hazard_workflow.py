from app.domain.work_orders import WorkOrderStatus


ROLE_GC_SAFETY_OFFICER = "gc_safety_officer"
ROLE_SAFETY_DIRECTOR = "safety_director"
ROLE_SUB_SAFETY_OFFICER = "sub_safety_officer"
ROLE_SYSTEM = "system"

ROLE_ACTION_MATRIX: dict[tuple[str, str, str], str] = {
    (WorkOrderStatus.PENDING_CONFIRM.value, "confirm", ROLE_SAFETY_DIRECTOR): "same_project",
    (WorkOrderStatus.DISPATCHED.value, "accept", ROLE_SUB_SAFETY_OFFICER): "same_subcontractor",
    (WorkOrderStatus.PROCESSING.value, "submit_result", ROLE_SUB_SAFETY_OFFICER): "same_subcontractor",
    (WorkOrderStatus.WAITING_REVIEW.value, "review_pass", ROLE_GC_SAFETY_OFFICER): "same_project",
    (WorkOrderStatus.WAITING_REVIEW.value, "review_reject", ROLE_GC_SAFETY_OFFICER): "same_project",
    (WorkOrderStatus.PROCESSING.value, "timeout", ROLE_SYSTEM): "system",
}

ACTION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "confirm": ("assignee_user_id", "due_time"),
    "submit_result": ("rectification_attachments",),
    "review_reject": ("reject_reason",),
}


def allowed_action(
    role_code: str,
    status: str,
    action: str,
    user_subcontractor_id: str | None = None,
    order_subcontractor_id: str | None = None,
) -> bool:
    rule = ROLE_ACTION_MATRIX.get((status, action, role_code))
    if rule is None:
        return False
    if rule == "same_subcontractor":
        return bool(user_subcontractor_id and user_subcontractor_id == order_subcontractor_id)
    return True


def required_fields_for_action(action: str) -> tuple[str, ...]:
    return ACTION_REQUIRED_FIELDS.get(action, ())
