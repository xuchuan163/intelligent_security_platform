from app.services.nl2sql.prompt_builder import build_candidate_sql_prompt
from app.services.nl2sql.schema_context import build_schema_context, render_schema_context


def test_schema_context_uses_audit_whitelist_and_excludes_internal_or_sensitive_fields():
    context = build_schema_context(metric_aliases={"MTR-HZD-OPEN": ["open hazard count", "hazard backlog"]})
    rendered = render_schema_context(context)

    assert "project" in context.table_names
    assert "worker" in context.table_names
    assert "metric_catalog" in context.table_names
    assert "agent_nl2sql_audit" not in context.table_names
    assert "agent_session_summary" not in context.table_names

    assert "worker_id" in context.allowed_fields_for("worker")
    assert "worker_name_masked" in context.allowed_fields_for("worker")
    assert "company_id" not in rendered
    assert "tenant_id" not in rendered
    assert "org_path" not in rendered
    assert "identity_card" not in rendered
    assert "raw_video" not in rendered
    assert "MTR-HZD-OPEN" in rendered
    assert "open hazard count" in rendered


def test_prompt_builder_renders_strict_candidate_sql_constraints():
    context = build_schema_context(metric_aliases={"MTR-PROJ-RISK": ["project risk score"]})

    prompt = build_candidate_sql_prompt(
        question="List high risk projects",
        schema_context=context,
    )

    assert "List high risk projects" in prompt
    assert "Return exactly one MySQL SELECT statement" in prompt
    assert "Do not return Markdown" in prompt
    assert "Do not use SELECT *" in prompt
    assert "Do not include company_id, tenant_id, or org_path predicates" in prompt
    assert "Do not add data-scope project_id predicates" in prompt
    assert "Use only the tables and fields listed below" in prompt
    assert "CLARIFICATION_REQUIRED" in prompt
    assert "project" in prompt
    assert "project_id" in prompt
    assert "identity_card" not in prompt
    assert "raw_video" not in prompt
