"""Aggregated dispatch metrics for the analytics AI agent."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Dispatch
from ..schemas.dispatch_metrics import DispatchMetrics


class DispatchMetricsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_metrics(self, window_hours: int = 8) -> DispatchMetrics:
        since = datetime.now(UTC) - timedelta(hours=window_hours)

        status_query = select(
            Dispatch.status,
            func.count().label("cnt"),
        ).group_by(Dispatch.status)

        status_rows = (await self.db.execute(status_query)).all()
        by_status = {row.status: row.cnt for row in status_rows}

        active_statuses = {"assigned", "accepted", "en_route", "arrived", "in_progress"}
        total_active = sum(by_status.get(s, 0) for s in active_statuses)

        resolution_query = select(
            func.avg(func.extract("epoch", Dispatch.completed_at - Dispatch.assigned_at)).label(
                "avg_s"
            ),
            func.percentile_cont(0.5)
            .within_group(func.extract("epoch", Dispatch.completed_at - Dispatch.assigned_at))
            .label("median_s"),
            func.count().label("completed_cnt"),
        ).where(
            Dispatch.status == "completed",
            Dispatch.completed_at >= since,
            Dispatch.completed_at.is_not(None),
        )

        res_row = (await self.db.execute(resolution_query)).one()

        volume_query = select(
            func.count(case((Dispatch.created_at >= since, Dispatch.id))).label("created_cnt"),
        )
        vol_row = (await self.db.execute(volume_query)).one()

        return DispatchMetrics(
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
