import pytest

from app.domain.work_orders import WorkOrderStatus, transition_status


def test_work_order_can_move_from_pending_to_dispatched():
    assert transition_status(WorkOrderStatus.PENDING_CONFIRM, "confirm") == WorkOrderStatus.DISPATCHED


def test_invalid_work_order_transition_is_rejected():
    with pytest.raises(ValueError, match="Invalid work-order transition"):
        transition_status(WorkOrderStatus.CLOSED, "accept")
