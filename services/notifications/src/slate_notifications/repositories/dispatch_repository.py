"""Repository for enriched dispatch queries in the notifications service."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from slate_core.models import Dispatch, Resource, Task

_ACTIVE_STATUSES = frozenset({"assigned", "accepted", "en_route", "arrived", "in_progress"})


@dataclass
class EnrichedDispatch:
    """Flat projection of dispatch + task + resource location for SSE payloads."""

    dispatch_id: int
    resource_id: int
    task_id: int
    status: str
    distance_km: float | None
    travel_time_minutes: int | None
    assigned_at: datetime | None
    route_polyline: str | None
    route_provider: str | None
    route_distance_m: int | None
    route_duration_s: int | None
    route_traffic_segments: list | None
    incident_type: str
    severity: int
    description: str | None
    address: str | None
    latitude: float
    longitude: float
    resource_lat: float
    resource_lon: float


class DispatchRepository:
    """Queries for the notifications service — read-only, enriched projections."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_enriched(self, dispatch_id: int) -> EnrichedDispatch | None:
        result = await self.db.execute(
            select(Dispatch, Task, Resource)
            .join(Task, Task.id == Dispatch.task_id)
            .join(Resource, Resource.id == Dispatch.resource_id)
            .where(Dispatch.id == dispatch_id)
        )
        row = result.first()
        if row is None:
            return None

        dispatch, task, resource = row
        return EnrichedDispatch(
            dispatch_id=dispatch.id,
            resource_id=dispatch.resource_id,
            task_id=dispatch.task_id,
            status=dispatch.status,
            distance_km=dispatch.distance_km,
            travel_time_minutes=dispatch.travel_time_minutes,
            assigned_at=dispatch.assigned_at,
            route_polyline=dispatch.route_polyline,
            route_provider=dispatch.route_provider,
            route_distance_m=dispatch.route_distance_m,
            route_duration_s=dispatch.route_duration_s,
            route_traffic_segments=dispatch.route_traffic_segments,
            incident_type=task.incident_type,
            severity=task.severity,
            description=task.description,
            address=task.address,
            latitude=task.latitude,
            longitude=task.longitude,
            resource_lat=resource.home_latitude,
            resource_lon=resource.home_longitude,
        )

    async def get_by_task(self, task_id: int) -> list[EnrichedDispatch]:
        result = await self.db.execute(
            select(Dispatch, Task, Resource)
            .join(Task, Task.id == Dispatch.task_id)
            .join(Resource, Resource.id == Dispatch.resource_id)
            .where(
                Dispatch.task_id == task_id,
                Dispatch.status.in_(_ACTIVE_STATUSES),
            )
            .order_by(Dispatch.assigned_at.desc())
        )
        rows = result.all()
        return [
            EnrichedDispatch(
                dispatch_id=d.id,
                resource_id=d.resource_id,
                task_id=d.task_id,
                status=d.status,
                distance_km=d.distance_km,
                travel_time_minutes=d.travel_time_minutes,
                assigned_at=d.assigned_at,
                route_polyline=d.route_polyline,
                route_provider=d.route_provider,
                route_distance_m=d.route_distance_m,
                route_duration_s=d.route_duration_s,
                route_traffic_segments=d.route_traffic_segments,
                incident_type=t.incident_type,
                severity=t.severity,
                description=t.description,
                address=t.address,
                latitude=t.latitude,
                longitude=t.longitude,
                resource_lat=r.home_latitude,
                resource_lon=r.home_longitude,
            )
            for d, t, r in rows
        ]

    async def get_all_active_enriched(self) -> list[EnrichedDispatch]:
        result = await self.db.execute(
            select(Dispatch, Task, Resource)
            .join(Task, Task.id == Dispatch.task_id)
            .join(Resource, Resource.id == Dispatch.resource_id)
            .where(Dispatch.status.in_(_ACTIVE_STATUSES))
            .order_by(Dispatch.assigned_at.desc())
        )
        rows = result.all()
        return [
            EnrichedDispatch(
                dispatch_id=d.id,
                resource_id=d.resource_id,
                task_id=d.task_id,
                status=d.status,
                distance_km=d.distance_km,
                travel_time_minutes=d.travel_time_minutes,
                assigned_at=d.assigned_at,
                route_polyline=d.route_polyline,
                route_provider=d.route_provider,
                route_distance_m=d.route_distance_m,
                route_duration_s=d.route_duration_s,
                route_traffic_segments=d.route_traffic_segments,
                incident_type=t.incident_type,
                severity=t.severity,
                description=t.description,
                address=t.address,
                latitude=t.latitude,
                longitude=t.longitude,
                resource_lat=r.home_latitude,
                resource_lon=r.home_longitude,
            )
            for d, t, r in rows
        ]
