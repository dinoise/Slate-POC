"""Aggregated assignment metrics for the analytics AI agent."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.assignment import Assignment
from ..schemas.assignment_metrics import AssignmentMetrics


class AssignmentMetricsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_metrics(self, window_hours: int = 8) -> AssignmentMetrics:
        since = datetime.now(UTC) - timedelta(hours=window_hours)

        # ── Counts by status (single query) ──────────────────────────────────
        status_query = select(
            Assignment.status,
            func.count().label("cnt"),
        ).group_by(Assignment.status)

        status_rows = (await self.db.execute(status_query)).all()
        by_status = {row.status: row.cnt for row in status_rows}

        active_statuses = {"assigned", "accepted", "en_route", "arrived", "in_progress"}
        total_active = sum(by_status.get(s, 0) for s in active_statuses)

        # ── Resolution time stats for completed assignments in window ─────────
        resolution_query = select(
            func.avg(func.extract("epoch", Assignment.completed_at - Assignment.assigned_at)).label(
                "avg_s"
            ),
            func.percentile_cont(0.5)
            .within_group(func.extract("epoch", Assignment.completed_at - Assignment.assigned_at))
            .label("median_s"),
            func.count().label("completed_cnt"),
        ).where(
            Assignment.status == "completed",
            Assignment.completed_at >= since,
            Assignment.completed_at.is_not(None),
        )

        res_row = (await self.db.execute(resolution_query)).one()

        # ── Volume in window ─────────────────────────────────────────────────
        volume_query = select(
            func.count(case((Assignment.created_at >= since, Assignment.id))).label("created_cnt"),
        )
        vol_row = (await self.db.execute(volume_query)).one()

        return AssignmentMetrics(
            total_active=total_active,
            by_status=by_status,
            avg_resolution_seconds=float(res_row.avg_s) if res_row.avg_s is not None else None,
            median_resolution_seconds=float(res_row.median_s)
            if res_row.median_s is not None
            else None,
            window_hours=window_hours,
            completed_in_window=res_row.completed_cnt or 0,
            created_in_window=vol_row.created_cnt or 0,
        )
