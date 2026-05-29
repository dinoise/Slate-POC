"""Test data factories — create model instances directly in the DB."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from geoalchemy2.functions import ST_MakePoint
from sqlalchemy.ext.asyncio import AsyncSession

from slate_api.models import Dispatch, Resource, Task, User

# Default coordinates: Mexico City center
_CDMX_LAT = 19.4326
_CDMX_LON = -99.1332


async def create_user(db: AsyncSession, **kwargs) -> User:
    defaults: dict = {
        "external_id": str(uuid.uuid4()),
        "first_name": "Ana",
        "last_name": "López",
        "email": f"user-{uuid.uuid4().hex[:8]}@test.com",
        "phone": "5551234567",
    }
    defaults.update(kwargs)
    user = User(**defaults)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def create_resource(db: AsyncSession, **kwargs) -> Resource:
    lat = kwargs.pop("home_latitude", _CDMX_LAT)
    lon = kwargs.pop("home_longitude", _CDMX_LON)
    defaults: dict = {
        "external_id": str(uuid.uuid4()),
        "first_name": "Carlos",
        "last_name": "García",
        "email": f"res-{uuid.uuid4().hex[:8]}@test.com",
        "phone": "5559876543",
        "home_latitude": lat,
        "home_longitude": lon,
        "home_location": ST_MakePoint(lon, lat),
        "skills": ["auto", "fire"],
        "max_cases_per_day": 5,
        "is_active": True,
        "status": "available",
    }
    defaults.update(kwargs)
    resource = Resource(**defaults)
    db.add(resource)
    await db.flush()
    await db.refresh(resource)
    return resource


# Backward-compat alias used in existing tests
create_adjuster = create_resource


async def create_task(db: AsyncSession, **kwargs) -> Task:
    lat = kwargs.pop("latitude", _CDMX_LAT)
    lon = kwargs.pop("longitude", _CDMX_LON)
    defaults: dict = {
        "external_id": str(uuid.uuid4()),
        "incident_type": "auto",
        "severity": 3,
        "description": "Test task",
        "latitude": lat,
        "longitude": lon,
        "location": ST_MakePoint(lon, lat),
        "address": "Av. Reforma 1, CDMX",
        "incident_datetime": datetime.now(tz=UTC),
        "status": "pending",
    }
    defaults.update(kwargs)
    task = Task(**defaults)
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


# Backward-compat alias used in existing tests
create_incident = create_task


async def create_dispatch(
    db: AsyncSession,
    task: Task,
    resource: Resource,
    **kwargs,
) -> Dispatch:
    defaults: dict = {
        "task_id": task.id,
        "resource_id": resource.id,
        "assigned_at": datetime.now(tz=UTC),
        "status": "assigned",
    }
    defaults.update(kwargs)
    dispatch = Dispatch(**defaults)
    db.add(dispatch)
    await db.flush()
    await db.refresh(dispatch)
    return dispatch


# Backward-compat alias used in existing tests
create_assignment = create_dispatch
