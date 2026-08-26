"""Dashboard schema — ADR-014: exactly the five metrics from the brief, all-time."""

from pydantic import BaseModel

from app.schemas.common import Money


class DashboardMetrics(BaseModel):
    members_total: int
    loans_active: int
    disbursed_total: Money
    collected_total: Money
    outstanding_total: Money
