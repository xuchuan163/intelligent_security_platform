from enum import StrEnum


class WorkOrderStatus(StrEnum):
    PENDING_CONFIRM = "pending_confirm"
    DISPATCHED = "dispatched"
    PROCESSING = "processing"
    WAITING_REVIEW = "waiting_review"
    CLOSED = "closed"
    REJECTED = "rejected"
    OVERDUE_ESCALATED = "overdue_escalated"


_TRANSITIONS = {
    (WorkOrderStatus.PENDING_CONFIRM, "confirm"): WorkOrderStatus.DISPATCHED,
    (WorkOrderStatus.DISPATCHED, "accept"): WorkOrderStatus.PROCESSING,
    (WorkOrderStatus.PROCESSING, "submit_result"): WorkOrderStatus.WAITING_REVIEW,
    (WorkOrderStatus.WAITING_REVIEW, "review_pass"): WorkOrderStatus.CLOSED,
    (WorkOrderStatus.WAITING_REVIEW, "review_reject"): WorkOrderStatus.PROCESSING,
    (WorkOrderStatus.PROCESSING, "timeout"): WorkOrderStatus.OVERDUE_ESCALATED,
}


def transition_status(current: WorkOrderStatus, action: str) -> WorkOrderStatus:
    next_status = _TRANSITIONS.get((current, action))
    if next_status is None:
        raise ValueError(f"Invalid work-order transition: {current} + {action}")
    return next_status
