from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.infrastructure.database.models import MetricCatalog


def metric_to_item(row: MetricCatalog) -> dict:
    return {
        "metric_code": row.metric_code,
        "metric_name": row.metric_name,
        "business_definition": row.business_definition,
        "statistical_period": row.statistical_period,
        "permission_level": row.permission_level,
        "metric_version": row.metric_version,
        "status": row.status,
    }


def metric_to_detail(row: MetricCatalog) -> dict:
    data = metric_to_item(row)
    data.update(
        {
            "calculation_formula": row.calculation_formula,
            "dimensions": row.dimensions,
            "source_tables": row.source_tables,
            "source_fields": row.source_fields,
            "filters": row.filters,
            "aliases": row.aliases or [],
            "owner_department": row.owner_department,
        }
    )
    return data


def list_metric_catalog(
    db: Session,
    page_no: int = 1,
    page_size: int = 20,
    status: str | None = None,
    keyword: str | None = None,
) -> dict:
    query = db.query(MetricCatalog)
    if status:
        query = query.filter(MetricCatalog.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                MetricCatalog.metric_code.like(pattern),
                MetricCatalog.metric_name.like(pattern),
                MetricCatalog.business_definition.like(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(MetricCatalog.metric_code.asc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "page_no": page_no,
        "page_size": page_size,
        "total": total,
        "items": [metric_to_item(row) for row in rows],
    }


def get_metric_detail(db: Session, metric_code: str) -> dict | None:
    row = db.query(MetricCatalog).filter(MetricCatalog.metric_code == metric_code).first()
    if row is None:
        return None
    return metric_to_detail(row)


def _list_value(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return [value]


def validate_metric_contract(db: Session, metric_codes: list[str]) -> dict:
    items: list[dict] = []
    for metric_code in metric_codes:
        row = db.query(MetricCatalog).filter(MetricCatalog.metric_code == metric_code).first()
        if row is None:
            items.append(
                {
                    "metric_code": metric_code,
                    "valid": False,
                    "errors": ["metric not found"],
                    "warnings": [],
                }
            )
            continue

        errors: list[str] = []
        warnings: list[str] = []
        if row.status != "enabled":
            errors.append("metric is not enabled")
        for field in ("business_definition", "calculation_formula"):
            if not getattr(row, field):
                errors.append(f"{field} is required")
        for field in ("dimensions", "source_tables", "source_fields"):
            if not _list_value(getattr(row, field)):
                errors.append(f"{field} is required")
        if not _list_value(row.aliases):
            warnings.append("aliases is empty")

        items.append(
            {
                "metric_code": row.metric_code,
                "metric_name": row.metric_name,
                "valid": not errors,
                "errors": errors,
                "warnings": warnings,
            }
        )
    return {"valid": all(item["valid"] for item in items), "items": items}


def get_metric_lineage(db: Session, metric_code: str) -> dict | None:
    row = db.query(MetricCatalog).filter(MetricCatalog.metric_code == metric_code).first()
    if row is None:
        return None
    return {
        "metric_code": row.metric_code,
        "metric_name": row.metric_name,
        "calculation_formula": row.calculation_formula,
        "dimensions": row.dimensions or [],
        "source_tables": row.source_tables or [],
        "source_fields": row.source_fields or [],
        "filters": row.filters or {},
        "aliases": row.aliases or [],
    }


def list_metric_aliases(db: Session, keyword: str | None = None) -> dict:
    rows = db.query(MetricCatalog).filter(MetricCatalog.status == "enabled").order_by(MetricCatalog.metric_code.asc()).all()
    items = []
    for row in rows:
        aliases = _list_value(row.aliases)
        haystack = " ".join([row.metric_code, row.metric_name or "", *[str(alias) for alias in aliases]])
        if keyword and keyword not in haystack:
            continue
        items.append({"metric_code": row.metric_code, "metric_name": row.metric_name, "aliases": aliases})
    return {"total": len(items), "items": items}
