"""RBAC permission codes and default role bundles for Phase 3-A."""

from enum import StrEnum


class Permission(StrEnum):
    DASHBOARD_READ = "dashboard.read"
    PROFILE_READ = "profile.read"
    PROFILE_RECALCULATE = "profile.recalculate"
    WORK_ORDERS_READ = "work_orders.read"
    WORK_ORDERS_WRITE = "work_orders.write"
    METRICS_READ = "metrics.read"
    RULES_READ = "rules.read"
    AGENT_ASK = "agent.ask"
    AGENT_APPROVE = "agent.approve"
    ANALYSIS_ATTRIBUTION = "analysis.attribution"
    AUTH_ADMIN = "auth.admin"


PLATFORM_ADMIN_PERMISSIONS: tuple[str, ...] = tuple(Permission)
COMPANY_ANALYST_PERMISSIONS: tuple[str, ...] = (
    Permission.DASHBOARD_READ,
    Permission.PROFILE_READ,
    Permission.METRICS_READ,
    Permission.RULES_READ,
    Permission.WORK_ORDERS_READ,
    Permission.AGENT_ASK,
    Permission.ANALYSIS_ATTRIBUTION,
)
PROJECT_SAFETY_OFFICER_PERMISSIONS: tuple[str, ...] = (
    Permission.DASHBOARD_READ,
    Permission.PROFILE_READ,
    Permission.WORK_ORDERS_READ,
    Permission.WORK_ORDERS_WRITE,
    Permission.RULES_READ,
    Permission.AGENT_ASK,
    Permission.AGENT_APPROVE,
)

DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "platform_admin": PLATFORM_ADMIN_PERMISSIONS,
    "company_analyst": COMPANY_ANALYST_PERMISSIONS,
    "project_safety_officer": PROJECT_SAFETY_OFFICER_PERMISSIONS,
}
