from dataclasses import dataclass
from typing import Mapping

from app.services.nl2sql.auditor import SENSITIVE_FIELD_NAMES, TABLE_FIELD_WHITELIST

SCOPE_FIELDS = {"company_id", "tenant_id", "org_path"}

TABLE_DESCRIPTIONS: dict[str, str] = {
    "project": "construction project master data",
    "subcontractor": "subcontractor safety and qualification data",
    "worker": "masked worker roster and safety status",
    "hazard": "hazard ledger and rectification status",
    "equipment": "equipment inspection and usage status",
    "project_risk_profile": "calculated project risk profile",
    "worker_risk_profile": "calculated worker risk profile",
    "subcontractor_risk_profile": "calculated subcontractor risk profile",
    "rule_trigger_log": "strong rule trigger evidence",
    "safety_work_order": "safety work order lifecycle",
    "metric_catalog": "metric semantic catalog and aliases",
    "accident_case_library": "structured accident case library",
}

JOIN_HINTS = [
    "project.project_id = hazard.project_id",
    "project.project_id = safety_work_order.project_id",
    "project.project_id = worker.project_id",
    "subcontractor.subcontractor_id = worker.subcontractor_id",
    "subcontractor.subcontractor_id = hazard.subcontractor_id",
]


@dataclass(frozen=True)
class SchemaTable:
    name: str
    description: str
    fields: list[str]


@dataclass(frozen=True)
class MetricAliasHint:
    metric_code: str
    aliases: list[str]


@dataclass(frozen=True)
class SchemaContext:
    tables: list[SchemaTable]
    metric_alias_hints: list[MetricAliasHint]
    join_hints: list[str]

    @property
    def table_names(self) -> list[str]:
        return [table.name for table in self.tables]

    def allowed_fields_for(self, table_name: str) -> list[str]:
        for table in self.tables:
            if table.name == table_name:
                return table.fields
        return []


def _prompt_safe_fields(fields: set[str]) -> list[str]:
    return sorted(field for field in fields if field not in SCOPE_FIELDS and field not in SENSITIVE_FIELD_NAMES)


def build_schema_context(metric_aliases: Mapping[str, list[str]] | None = None) -> SchemaContext:
    tables = [
        SchemaTable(
            name=table_name,
            description=TABLE_DESCRIPTIONS.get(table_name, "approved business table"),
            fields=_prompt_safe_fields(fields),
        )
        for table_name, fields in sorted(TABLE_FIELD_WHITELIST.items())
    ]
    alias_hints = [
        MetricAliasHint(metric_code=metric_code, aliases=list(aliases))
        for metric_code, aliases in sorted((metric_aliases or {}).items())
    ]
    return SchemaContext(tables=tables, metric_alias_hints=alias_hints, join_hints=JOIN_HINTS)


def render_schema_context(context: SchemaContext) -> str:
    lines = ["Allowed schema:"]
    for table in context.tables:
        lines.append(f"- {table.name}: {table.description}; fields: {', '.join(table.fields)}")

    if context.join_hints:
        lines.append("Approved join hints:")
        for hint in context.join_hints:
            lines.append(f"- {hint}")

    if context.metric_alias_hints:
        lines.append("Metric alias hints:")
        for hint in context.metric_alias_hints:
            lines.append(f"- {hint.metric_code}: {', '.join(hint.aliases)}")

    return "\n".join(lines)
