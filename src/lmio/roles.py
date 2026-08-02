"""Authenticated LMIO roles and explicit permission matrix."""

from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    OWNER = "owner"
    OPERATOR = "operator"
    REVIEWER = "reviewer"


class Principal(BaseModel):
    actor_id: str
    role: Role
    authentication_method: str


PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.OWNER: frozenset(
        {
            "view_dashboard",
            "view_evidence",
            "request_refresh",
            "manage_watchlists",
            "manage_plans",
            "submit_feedback",
            "view_health",
            "use_telegram",
            "access_public_audit",
        }
    ),
    Role.OPERATOR: frozenset(
        {
            "view_dashboard",
            "view_evidence",
            "request_refresh",
            "manage_watchlists",
            "manage_plans",
            "submit_feedback",
            "view_health",
            "use_telegram",
        }
    ),
    Role.REVIEWER: frozenset(
        {
            "view_dashboard",
            "view_evidence",
            "submit_feedback",
            "view_health",
            "access_public_audit",
        }
    ),
}


def can(principal: Principal, permission: str) -> bool:
    return permission in PERMISSIONS[principal.role]
