from app.domain.hazard_workflow import allowed_action, required_fields_for_action


def test_role_matrix_allows_expected_actions_only():
    assert allowed_action(
        role_code="safety_director",
        status="pending_confirm",
        action="confirm",
    )
    assert allowed_action(
        role_code="sub_safety_officer",
        status="dispatched",
        action="accept",
        user_subcontractor_id="S003",
        order_subcontractor_id="S003",
    )
    assert allowed_action(
        role_code="sub_safety_officer",
        status="processing",
        action="submit_result",
        user_subcontractor_id="S003",
        order_subcontractor_id="S003",
    )
    assert allowed_action(
        role_code="gc_safety_officer",
        status="waiting_review",
        action="review_pass",
    )
    assert allowed_action(
        role_code="gc_safety_officer",
        status="waiting_review",
        action="review_reject",
    )

    assert not allowed_action(role_code="sub_safety_officer", status="pending_confirm", action="confirm")
    assert not allowed_action(role_code="gc_safety_officer", status="dispatched", action="accept")
    assert not allowed_action(
        role_code="sub_safety_officer",
        status="processing",
        action="submit_result",
        user_subcontractor_id="S001",
        order_subcontractor_id="S003",
    )


def test_workflow_required_fields_for_actions():
    assert required_fields_for_action("confirm") == ("assignee_user_id", "due_time")
    assert required_fields_for_action("submit_result") == ("rectification_attachments",)
    assert required_fields_for_action("review_reject") == ("reject_reason",)
    assert required_fields_for_action("accept") == ()
