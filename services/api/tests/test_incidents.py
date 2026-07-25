"""Integration tests for the /api/v1/incidents endpoints."""

from datetime import UTC

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import api
from .factories import create_dispatch, create_resource, create_task, create_user

create_adjuster = create_resource
create_incident = create_task
create_assignment = create_dispatch

_BASE = api("/incidents")


def _incident_payload(**kwargs) -> dict:
    import uuid
    from datetime import datetime

    defaults = {
        "external_id": str(uuid.uuid4()),
        "incident_type": "auto",
        "severity": 2,
        "description": "Test",
        "latitude": 19.4326,
        "longitude": -99.1332,
        "address": "Reforma 1, CDMX",
        "incident_datetime": datetime.now(tz=UTC).isoformat(),
    }
    defaults.update(kwargs)
    return defaults


# ── Create ────────────────────────────────────────────────────────────────────


async def test_create_incident_201(client: AsyncClient) -> None:
    response = await client.post(_BASE + "/", json=_incident_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["incident_type"] == "auto"


async def test_create_incident_conflict_409(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session)
    payload = _incident_payload(external_id=incident.external_id)
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 409


async def test_create_incident_with_user(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await create_user(db_session)
    payload = _incident_payload(reported_by_user_id=user.id)
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 201
    assert response.json()["reported_by_user_id"] == user.id


# ── List ──────────────────────────────────────────────────────────────────────


async def test_get_incidents_empty(client: AsyncClient) -> None:
    response = await client.get(_BASE + "/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data and "total" in data
    assert data["total"] == 0
    assert data["items"] == []


async def test_get_incidents_with_data(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_incident(db_session)
    await create_incident(db_session)
    response = await client.get(_BASE + "/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


async def test_get_incidents_status_filter(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_incident(db_session, status="pending")
    await create_incident(db_session, status="cancelled")
    response = await client.get(_BASE + "/", params={"status": "pending"})
    assert response.status_code == 200
    for inc in response.json()["items"]:
        assert inc["status"] == "pending"


# ── Read ──────────────────────────────────────────────────────────────────────


async def test_get_incident_by_id(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session, incident_type="fire")
    response = await client.get(f"{_BASE}/{incident.id}")
    assert response.status_code == 200
    assert response.json()["incident_type"] == "fire"


async def test_get_incident_not_found(client: AsyncClient) -> None:
    response = await client.get(f"{_BASE}/99999")
    assert response.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────


async def test_update_incident(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session)
    response = await client.patch(f"{_BASE}/{incident.id}", json={"severity": 5})
    assert response.status_code == 200
    assert response.json()["severity"] == 5


# ── Delete (soft) ─────────────────────────────────────────────────────────────


async def test_soft_delete_incident(client: AsyncClient, db_session: AsyncSession) -> None:
    incident = await create_incident(db_session)
    response = await client.delete(f"{_BASE}/{incident.id}")
    assert response.status_code == 204
    get_resp = await client.get(f"{_BASE}/{incident.id}")
    assert get_resp.json()["status"] == "cancelled"


async def test_delete_incident_releases_adjuster(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resource = await create_adjuster(db_session, status="busy")
    task = await create_incident(db_session, status="assigned")
    await create_assignment(db_session, task, resource, status="assigned")

    response = await client.delete(f"{_BASE}/{task.id}")
    assert response.status_code == 204

    res_resp = await client.get(api(f"/adjusters/{resource.id}"))
    assert res_resp.json()["status"] == "available"


# ── Cancel all ────────────────────────────────────────────────────────────────


async def test_cancel_all_active(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_incident(db_session, status="pending")
    await create_incident(db_session, status="assigned")
    response = await client.delete(_BASE + "/")
    assert response.status_code == 200
    body = response.json()
    assert body["cancelled"] >= 2


# ── Nearby ────────────────────────────────────────────────────────────────────


async def test_get_nearby_incidents(client: AsyncClient, db_session: AsyncSession) -> None:
    # Create incident at CDMX center
    await create_incident(db_session, latitude=19.4326, longitude=-99.1332)
    response = await client.get(
        _BASE + "/nearby/",
        params={"latitude": 19.4326, "longitude": -99.1332, "radius_km": 5},
    )
    assert response.status_code == 200
    assert len(response.json()) >= 1
