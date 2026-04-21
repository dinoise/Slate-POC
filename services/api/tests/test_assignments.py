"""Integration tests for the /api/v1/assignments endpoints."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import api
from .factories import create_adjuster, create_assignment, create_incident

_BASE = api("/assignments")


# ── Create ────────────────────────────────────────────────────────────────────


async def test_create_assignment_201(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session, status="pending")
    adjuster = await create_adjuster(db_session, status="available")
    payload = {
        "incident_id": incident.id,
        "adjuster_id": adjuster.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["incident_id"] == incident.id
    assert body["adjuster_id"] == adjuster.id
    assert body["status"] == "assigned"


async def test_create_assignment_incident_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    adjuster = await create_adjuster(db_session, status="available")
    payload = {
        "incident_id": 99999,
        "adjuster_id": adjuster.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 404


async def test_create_assignment_adjuster_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    incident = await create_incident(db_session, status="pending")
    payload = {
        "incident_id": incident.id,
        "adjuster_id": 99999,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 404


async def test_create_assignment_adjuster_busy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    incident = await create_incident(db_session, status="pending")
    adjuster = await create_adjuster(db_session, status="busy")
    payload = {
        "incident_id": incident.id,
        "adjuster_id": adjuster.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 422


async def test_create_assignment_marks_incident_assigned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    incident = await create_incident(db_session, status="pending")
    adjuster = await create_adjuster(db_session, status="available")
    payload = {
        "incident_id": incident.id,
        "adjuster_id": adjuster.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    await client.post(_BASE + "/", json=payload)
    inc_resp = await client.get(api(f"/incidents/{incident.id}"))
    assert inc_resp.json()["status"] == "assigned"


async def test_create_assignment_marks_adjuster_busy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    incident = await create_incident(db_session, status="pending")
    adjuster = await create_adjuster(db_session, status="available")
    payload = {
        "incident_id": incident.id,
        "adjuster_id": adjuster.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    await client.post(_BASE + "/", json=payload)
    adj_resp = await client.get(api(f"/adjusters/{adjuster.id}"))
    assert adj_resp.json()["status"] == "busy"


# ── List ──────────────────────────────────────────────────────────────────────


async def test_get_assignments(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session)
    adjuster = await create_adjuster(db_session)
    await create_assignment(db_session, incident, adjuster)
    response = await client.get(_BASE + "/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data and "total" in data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


# ── Read ──────────────────────────────────────────────────────────────────────


async def test_get_assignment_by_id(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session)
    adjuster = await create_adjuster(db_session)
    assignment = await create_assignment(db_session, incident, adjuster)
    response = await client.get(f"{_BASE}/{assignment.id}")
    assert response.status_code == 200
    assert response.json()["id"] == assignment.id


async def test_get_assignment_not_found(client: AsyncClient) -> None:
    response = await client.get(f"{_BASE}/99999")
    assert response.status_code == 404


# ── By incident / adjuster ────────────────────────────────────────────────────


async def test_get_assignments_by_incident(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session)
    adjuster = await create_adjuster(db_session)
    await create_assignment(db_session, incident, adjuster)
    response = await client.get(f"{_BASE}/by-incident/{incident.id}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["incident_id"] == incident.id


async def test_get_assignments_by_adjuster(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session)
    adjuster = await create_adjuster(db_session)
    await create_assignment(db_session, incident, adjuster)
    response = await client.get(f"{_BASE}/by-adjuster/{adjuster.id}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["adjuster_id"] == adjuster.id


# ── Update / status flow ──────────────────────────────────────────────────────


async def test_cancel_assignment_releases(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session, status="assigned")
    adjuster = await create_adjuster(db_session, status="busy")
    assignment = await create_assignment(db_session, incident, adjuster, status="assigned")

    response = await client.patch(f"{_BASE}/{assignment.id}", json={"status": "cancelled"})
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    adj_resp = await client.get(api(f"/adjusters/{adjuster.id}"))
    assert adj_resp.json()["status"] == "available"

    inc_resp = await client.get(api(f"/incidents/{incident.id}"))
    assert inc_resp.json()["status"] == "pending"


async def test_update_assignment_status_flow(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session)
    adjuster = await create_adjuster(db_session)
    assignment = await create_assignment(db_session, incident, adjuster, status="assigned")

    for new_status in ("accepted", "en_route", "arrived"):
        response = await client.patch(f"{_BASE}/{assignment.id}", json={"status": new_status})
        assert response.status_code == 200
        assert response.json()["status"] == new_status
