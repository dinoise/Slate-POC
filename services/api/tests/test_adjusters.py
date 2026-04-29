"""Integration tests for the /api/v1/adjusters endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import api
from .factories import create_adjuster

_BASE = api("/adjusters")


# ── Create ────────────────────────────────────────────────────────────────────


async def test_create_adjuster_201(client: AsyncClient) -> None:
    payload = {
        "external_id": "ext-001",
        "first_name": "Luis",
        "last_name": "Martínez",
        "email": "luis@test.com",
        "home_latitude": 19.4326,
        "home_longitude": -99.1332,
        "skills": ["auto"],
        "max_cases_per_day": 5,
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["external_id"] == "ext-001"
    assert body["status"] == "available"
    assert body["is_active"] is True


async def test_create_adjuster_conflict_409(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_adjuster(db_session, external_id="dup-ext")
    payload = {
        "external_id": "dup-ext",
        "first_name": "Otro",
        "last_name": "Adj",
        "email": "otro@test.com",
        "home_latitude": 19.43,
        "home_longitude": -99.13,
        "skills": [],
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 409


# ── List ──────────────────────────────────────────────────────────────────────


async def test_get_adjusters(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_adjuster(db_session)
    await create_adjuster(db_session)
    response = await client.get(_BASE + "/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data and "total" in data
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


async def test_get_adjusters_is_active_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_adjuster(db_session, is_active=True)
    await create_adjuster(db_session, is_active=False, status="offline")
    active = await client.get(_BASE + "/", params={"is_active": "true"})
    inactive = await client.get(_BASE + "/", params={"is_active": "false"})
    assert active.status_code == 200
    assert inactive.status_code == 200
    for adj in active.json()["items"]:
        assert adj["is_active"] is True
    for adj in inactive.json()["items"]:
        assert adj["is_active"] is False


# ── Read ──────────────────────────────────────────────────────────────────────


async def test_get_adjuster_by_id(client: AsyncClient, db_session: AsyncSession) -> None:
    adjuster = await create_adjuster(db_session, first_name="Elena")
    response = await client.get(f"{_BASE}/{adjuster.id}")
    assert response.status_code == 200
    assert response.json()["first_name"] == "Elena"


async def test_get_adjuster_not_found(client: AsyncClient) -> None:
    response = await client.get(f"{_BASE}/99999")
    assert response.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────


async def test_update_adjuster(client: AsyncClient, db_session: AsyncSession) -> None:
    adjuster = await create_adjuster(db_session)
    response = await client.patch(f"{_BASE}/{adjuster.id}", json={"first_name": "Actualizado"})
    assert response.status_code == 200
    assert response.json()["first_name"] == "Actualizado"


# ── Delete ────────────────────────────────────────────────────────────────────


async def test_delete_adjuster_soft(client: AsyncClient, db_session: AsyncSession) -> None:
    adjuster = await create_adjuster(db_session)
    response = await client.delete(f"{_BASE}/{adjuster.id}")
    assert response.status_code == 204
    # Verify soft-delete: still exists but is_active=False
    get_resp = await client.get(f"{_BASE}/{adjuster.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False
    assert get_resp.json()["status"] == "offline"


# ── Reset status ──────────────────────────────────────────────────────────────


async def test_reset_status(client: AsyncClient, db_session: AsyncSession) -> None:
    adjuster = await create_adjuster(db_session, status="busy")
    response = await client.post(_BASE + "/reset-status")
    assert response.status_code == 200
    assert response.json()["reset"] >= 1
    get_resp = await client.get(f"{_BASE}/{adjuster.id}")
    assert get_resp.json()["status"] == "available"


# ── Available ─────────────────────────────────────────────────────────────────


async def test_get_available_adjusters(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_adjuster(db_session, status="available", is_active=True)
    response = await client.get(_BASE + "/available")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
