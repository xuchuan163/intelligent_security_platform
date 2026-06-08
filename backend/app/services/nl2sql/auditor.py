import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlglot import exp, parse, parse_one
from sqlglot.errors import ParseError

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import AgentNl2sqlAudit

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

TABLE_FIELD_WHITELIST: dict[str, set[str]] = {
    "project": {
        "tenant_id", "org_path", "project_id", "project_name", "project_type",
        "construction_phase", "region", "status", "schedule_pressure_index",
        "night_shift_days", "cross_operation_count",
    },
    "subcontractor": {
        "tenant_id", "org_path", "subcontractor_id", "subcontractor_name",
        "qualification", "safety_license_status", "accident_history_count",
        "credit_score", "status",
    },
    "worker": {
        "tenant_id", "org_path", "worker_id", "worker_name_masked", "work_type",
        "project_id", "subcontractor_id", "special_cert_status",
        "health_check_status", "exam_score", "violation_count_30d",
        "violation_count_180d", "entry_days", "status",
    },
    "hazard": {
        "tenant_id", "org_path", "hazard_id", "project_id", "subcontractor_id",
        "worker_id", "equipment_id", "hazard_type", "hazard_level",
        "description", "status", "due_date", "close_date", "is_major",
    },
    "equipment": {
        "tenant_id", "org_path", "equipment_id", "project_id", "subcontractor_id",
        "equipment_type", "equipment_name", "inspection_due_date",
        "maintenance_status", "use_status", "is_special",
    },
    "project_risk_profile": {
        "tenant_id", "org_path", "project_id", "calc_date", "total_risk_score",
        "risk_level", "data_completeness", "confidence_level",
        "strong_rule_flags", "risk_tags", "model_version",
    },
    "worker_risk_profile": {
        "tenant_id", "org_path", "worker_id", "project_id", "subcontractor_id",
        "calc_date", "total_risk_score", "risk_level", "data_completeness",
        "confidence_level", "risk_tags", "model_version",
    },
    "subcontractor_risk_profile": {
        "tenant_id", "org_path", "subcontractor_id", "project_id", "calc_date",
        "total_risk_score", "risk_level", "data_completeness",
        "confidence_level", "high_risk_worker_ratio",
        "overdue_rectification_ratio", "risk_tags", "model_version",
    },
    "rule_trigger_log": {
        "tenant_id", "org_path", "rule_id", "object_type", "object_id",
        "project_id", "trigger_condition", "evidence", "risk_action",
        "severity", "created_at",
    },
    "safety_work_order": {
        "tenant_id", "org_path", "work_order_id", "work_order_type",
        "source_type", "source_id", "project_id", "subcontractor_id",
        "worker_id", "equipment_id", "title", "description", "priority",
        "status", "responsible_user_id", "review_user_id", "due_time",
        "review_time", "close_time", "escalation_level", "rule_id",
        "created_at", "updated_at",
    },
    "metric_catalog": {
        "metric_code", "metric_name", "business_definition",
        "calculation_formula", "statistical_period", "dimensions",
        "source_tables", "source_fields", "filters", "aliases",
        "permission_level", "owner_department", "metric_version", "status",
    },
    "accident_case_library": {
        "tenant_id", "accident_case_id", "accident_type", "severity",
        "project_type", "operation_scene", "direct_cause", "indirect_cause",
        "involved_subjects", "warning_indicators", "rectification_measures",
        "tags", "embedding_version", "status", "created_at",
    },
}

COMPANY_SCOPED_TABLES = {
    "project",
    "subcontractor",
    "worker",
    "hazard",
    "equipment",
    "project_risk_profile",
    "worker_risk_profile",
    "subcontractor_risk_profile",
    "rule_trigger_log",
    "safety_work_order",
    "metric_catalog",
    "accident_case_library",
}

PROJECT_OVERRIDE_CONFIG_TABLES = {"metric_catalog"}

for _table_name in COMPANY_SCOPED_TABLES:
    TABLE_FIELD_WHITELIST[_table_name].add("company_id")

TABLE_FIELD_WHITELIST["metric_catalog"].add("project_id")

SENSITIVE_FIELD_NAMES = {
    "identity_card", "id_card", "id_card_no", "phone", "mobile", "bank_card",
    "password", "token", "secret", "api_key", "health_detail",
    "health_details", "face_image", "raw_video",
}


@dataclass(frozen=True)
class AuditResult:
    allowed: bool
    reject_reason: str | None
    sanitized_sql: str | None
    scope_injected: bool
    tables_used: list[str]
    fields_used: list[str]


def _reject(reason: str, tables_used: list[str] | None = None, fields_used: list[str] | None = None) -> AuditResult:
    return AuditResult(
        allowed=False,
        reject_reason=reason,
        sanitized_sql=None,
        scope_injected=False,
        tables_used=tables_used or [],
        fields_used=fields_used or [],
    )


def _literal_value(node: exp.Expression) -> str | None:
    if isinstance(node, exp.Literal):
        return str(node.this)
    return None


def _has_tenant_override(expression: exp.Expression, tenant_id: str) -> bool:
    for eq in expression.find_all(exp.EQ):
        left, right = eq.args.get("this"), eq.args.get("expression")
        if isinstance(left, exp.Column) and left.name.lower() == "tenant_id":
            value = _literal_value(right)
            if value is not None and value != tenant_id:
                return True
        if isinstance(right, exp.Column) and right.name.lower() == "tenant_id":
            value = _literal_value(left)
            if value is not None and value != tenant_id:
                return True
    return False


def _has_company_override(expression: exp.Expression, company_id: str) -> bool:
    for eq in expression.find_all(exp.EQ):
        left, right = eq.args.get("this"), eq.args.get("expression")
        if isinstance(left, exp.Column) and left.name.lower() == "company_id":
            value = _literal_value(right)
            if value is not None and value != company_id:
                return True
        if isinstance(right, exp.Column) and right.name.lower() == "company_id":
            value = _literal_value(left)
            if value is not None and value != company_id:
                return True
    return False


def _has_project_override(expression: exp.Expression, authorized_project_ids: tuple[str, ...]) -> bool:
    if not authorized_project_ids:
        return False
    allowed = set(authorized_project_ids)
    for eq in expression.find_all(exp.EQ):
        left, right = eq.args.get("this"), eq.args.get("expression")
        if isinstance(left, exp.Column) and left.name.lower() == "project_id":
            value = _literal_value(right)
            if value is not None and value not in allowed:
                return True
        if isinstance(right, exp.Column) and right.name.lower() == "project_id":
            value = _literal_value(left)
            if value is not None and value not in allowed:
                return True
    for in_expression in expression.find_all(exp.In):
        column = in_expression.args.get("this")
        if not isinstance(column, exp.Column) or column.name.lower() != "project_id":
            continue
        values = [
            _literal_value(item)
            for item in in_expression.args.get("expressions", [])
        ]
        if any(value is not None and value not in allowed for value in values):
            return True
    return False


def _limit_value(expression: exp.Select) -> int | None:
    limit = expression.args.get("limit")
    if limit is None:
        return None
    node = limit.args.get("expression")
    if isinstance(node, exp.Literal):
        try:
            return int(node.this)
        except ValueError:
            return None
    return None


def _set_limit(expression: exp.Select, value: int) -> exp.Select:
    expression.set("limit", exp.Limit(expression=exp.Literal.number(value)))
    return expression


def _append_where(expression: exp.Select, condition_sql: str) -> exp.Select:
    condition = parse_one(condition_sql, read="mysql")
    where = expression.args.get("where")
    if where is None:
        expression.set("where", exp.Where(this=condition))
    else:
        expression.set("where", exp.Where(this=exp.and_(where.this, condition)))
    return expression


def _quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _resolve_column_table(column: exp.Column, tables: list[str], table_aliases: dict[str, str]) -> str | None:
    if column.table:
        return table_aliases.get(column.table.lower(), column.table.lower())
    if len(tables) == 1:
        return tables[0]
    return None


def audit_sql(candidate_sql: str, current_user: MockUser) -> AuditResult:
    try:
        statements = parse(candidate_sql, read="mysql")
    except ParseError:
        return _reject("SQL parse failed")

    if len(statements) != 1:
        return _reject("multiple SQL statements are not allowed")

    statement = statements[0]
    if not isinstance(statement, exp.Select):
        return _reject("only SELECT statements are allowed")

    table_nodes = list(statement.find_all(exp.Table))
    tables = [table.name.lower() for table in table_nodes]
    table_aliases = {
        (table.alias_or_name or table.name).lower(): table.name.lower()
        for table in table_nodes
    }
    for table in tables:
        if table not in TABLE_FIELD_WHITELIST:
            return _reject(f"table not allowed: {table}", tables_used=tables)

    if list(statement.find_all(exp.Star)):
        return _reject("SELECT * is not allowed", tables_used=tables)

    fields: list[str] = []
    for column in statement.find_all(exp.Column):
        field = column.name.lower()
        fields.append(field)
        table = _resolve_column_table(column, tables, table_aliases)
        if table is None:
            return _reject(f"ambiguous unqualified field in multi-table query: {field}", tables, fields)
        if field in SENSITIVE_FIELD_NAMES:
            return _reject(f"field not allowed: {table or 'unknown'}.{field}", tables, fields)
        if table is not None and field not in TABLE_FIELD_WHITELIST.get(table, set()):
            return _reject(f"field not allowed: {table}.{field}", tables, fields)

    if _has_tenant_override(statement, current_user.tenant_id):
        return _reject("tenant_id override is not allowed", tables, fields)

    if _has_company_override(statement, current_user.company_id):
        return _reject("company_id override is not allowed", tables, fields)

    if (
        current_user.scope_type == ScopeType.PROJECT
        and _has_project_override(statement, current_user.authorized_project_ids)
    ):
        return _reject("project_id override is not allowed", tables, fields)

    scoped = statement.copy()
    scope_parts: list[str] = []
    for table_node in table_nodes:
        table = table_node.name.lower()
        qualifier = (table_node.alias_or_name or table_node.name).lower()
        allowed_fields = TABLE_FIELD_WHITELIST[table]
        if "company_id" in allowed_fields:
            scope_parts.append(f"{qualifier}.company_id = '{current_user.company_id}'")
        elif "tenant_id" in allowed_fields:
            scope_parts.append(f"{qualifier}.tenant_id = '{current_user.company_id}'")
        if (
            current_user.scope_type == ScopeType.PROJECT
            and current_user.authorized_project_ids
            and "project_id" in allowed_fields
        ):
            if table in PROJECT_OVERRIDE_CONFIG_TABLES:
                scope_parts.append(
                    f"({qualifier}.project_id IS NULL OR "
                    f"{qualifier}.project_id IN ({_quoted_values(current_user.authorized_project_ids)}))"
                )
            else:
                scope_parts.append(f"{qualifier}.project_id IN ({_quoted_values(current_user.authorized_project_ids)})")
        elif current_user.data_scope == DataScope.ORG and "org_path" in allowed_fields:
            scope_parts.append(f"{qualifier}.org_path LIKE '{current_user.org_path}%'")

    if scope_parts:
        _append_where(scoped, " AND ".join(scope_parts))

    limit = _limit_value(scoped)
    if limit is None:
        _set_limit(scoped, DEFAULT_LIMIT)
    elif limit > MAX_LIMIT:
        _set_limit(scoped, MAX_LIMIT)

    sanitized_sql = scoped.sql(dialect="mysql", pretty=False)
    return AuditResult(
        allowed=True,
        reject_reason=None,
        sanitized_sql=sanitized_sql,
        scope_injected=bool(scope_parts),
        tables_used=sorted(set(tables)),
        fields_used=sorted(set(fields)),
    )


def audit_sql_with_log(
    db: Session,
    question: str,
    candidate_sql: str,
    current_user: MockUser,
) -> AuditResult:
    start = time.perf_counter()
    result = audit_sql(candidate_sql, current_user)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    db.add(
        AgentNl2sqlAudit(
            audit_id=f"NLSQL-{uuid.uuid4().hex[:16]}",
            tenant_id=current_user.tenant_id,
            org_path=current_user.org_path,
            user_id=current_user.user_id,
            question=question,
            candidate_sql=candidate_sql,
            sanitized_sql=result.sanitized_sql,
            allowed=result.allowed,
            reject_reason=result.reject_reason,
            tables_used=result.tables_used,
            fields_used=result.fields_used,
            scope_injected=result.scope_injected,
            execution_status="audited",
            elapsed_ms=elapsed_ms,
        )
    )
    db.commit()
    return result
