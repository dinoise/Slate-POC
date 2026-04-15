"""Test data factories — create model instances directly in the DB."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from geoalchemy2.functions import ST_MakePoint
from sqlalchemy.ext.asyncio import AsyncSession

from slate_api.models.adjuster import Adjuster
from slate_api.models.assignment import Assignment
from slate_api.models.incident import Incident
from slate_api.models.user import User

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


async def create_adjuster(db: AsyncSession, **kwargs) -> Adjuster:
    lat = kwargs.pop("home_latitude", _CDMX_LAT)
    lon = kwargs.pop("home_longitude", _CDMX_LON)
    defaults: dict = {
        "external_id": str(uuid.uuid4()),
        "first_name": "Carlos",
        "last_name": "García",
        "email": f"adj-{uuid.uuid4().hex[:8]}@test.com",
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
    adjuster = Adjuster(**defaults)
    db.add(adjuster)
    await db.flush()
    await db.refresh(adjuster)
    return adjuster


async def create_incident(db: AsyncSession, **kwargs) -> Incident:
    lat = kwargs.pop("latitude", _CDMX_LAT)
    lon = kwargs.pop("longitude", _CDMX_LON)
    defaults: dict = {
        "external_id": str(uuid.uuid4()),
        "incident_type": "auto",
        "severity": 3,
        "description": "Test incident",
        "latitude": lat,
        "longitude": lon,
        "location": ST_MakePoint(lon, lat),
        "address": "Av. Reforma 1, CDMX",
        "incident_datetime": datetime.now(tz=UTC),
        "status": "pending",
    }
    defaults.update(kwargs)
    incident = Incident(**defaults)
    db.add(incident)
    await db.flush()
    await db.refresh(incident)
    return incident


async def create_assignment(
    db: AsyncSession,
    incident: Incident,
    adjuster: Adjuster,
    **kwargs,
) -> Assignment:
    defaults: dict = {
        "incident_id": incident.id,
        "adjuster_id": adjuster.id,
        "assigned_at": datetime.now(tz=UTC),
        "status": "assigned",
    }
    defaults.update(kwargs)
    assignment = Assignment(**defaults)
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment
