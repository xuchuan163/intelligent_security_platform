from app.infrastructure.database.models import Hazard, ProjectUser, WorkOrderFlowLog


def test_hazard_workflow_tables_and_columns_are_declared():
    project_user_columns = set(ProjectUser.__table__.columns.keys())
    flow_log_columns = set(WorkOrderFlowLog.__table__.columns.keys())
    hazard_columns = set(Hazard.__table__.columns.keys())

    assert {
        "tenant_id",
        "company_id",
        "org_path",
        "project_id",
        "user_id",
        "user_name",
        "role_code",
        "subcontractor_id",
        "status",
    } <= project_user_columns
    assert {
        "work_order_id",
        "from_status",
        "to_status",
        "action",
        "operator_user_id",
        "operator_role",
        "comment",
        "reject_reason",
        "attachments",
    } <= flow_log_columns
    assert {
        "discovered_by_user_id",
        "location",
        "attachments",
        "work_order_id",
    } <= hazard_columns


def test_project_user_has_unique_project_user_role_constraint():
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in ProjectUser.__table__.constraints
        if getattr(constraint, "columns", None)
    }

    assert ("project_id", "user_id", "role_code") in constraints
