"""Integration tests for the /api/v1/assignments endpoints."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import api
from .factories import create_dispatch, create_resource, create_task

_BASE = api("/assignments")


# ── Create ────────────────────────────────────────────────────────────────────


async def test_create_assignment_201(client: AsyncClient, db_session: AsyncSession) -> None:
    task = await create_task(db_session, status="pending")
    resource = await create_resource(db_session, status="available")
    payload = {
        "task_id": task.id,
        "resource_id": resource.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["task_id"] == task.id
    assert body["resource_id"] == resource.id
    assert body["status"] == "assigned"


async def test_create_assignment_task_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resource = await create_resource(db_session, status="available")
    payload = {
        "task_id": 99999,
        "resource_id": resource.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 404


async def test_create_assignment_resource_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    task = await create_task(db_session, status="pending")
    payload = {
        "task_id": task.id,
        "resource_id": 99999,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 404


async def test_create_assignment_resource_busy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    task = await create_task(db_session, status="pending")
    resource = await create_resource(db_session, status="busy")
    payload = {
        "task_id": task.id,
        "resource_id": resource.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 422


async def test_create_assignment_marks_task_assigned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    task = await create_task(db_session, status="pending")
    resource = await create_resource(db_session, status="available")
    payload = {
        "task_id": task.id,
        "resource_id": resource.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    await client.post(_BASE + "/", json=payload)
    task_resp = await client.get(api(f"/incidents/{task.id}"))
    assert task_resp.json()["status"] == "assigned"


async def test_create_assignment_marks_resource_busy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    task = await create_task(db_session, status="pending")
    resource = await create_resource(db_session, status="available")
    payload = {
        "task_id": task.id,
        "resource_id": resource.id,
        "assigned_at": datetime.now(tz=UTC).isoformat(),
    }
    await client.post(_BASE + "/", json=payload)
    res_resp = await client.get(api(f"/adjusters/{resource.id}"))
    assert res_resp.json()["status"] == "busy"


# ── List ──────────────────────────────────────────────────────────────────────


async def test_get_assignments(client: AsyncClient, db_session: AsyncSession) -> None:
    task = await create_task(db_session)
    resource = await create_resource(db_session)
    await create_dispatch(db_session, task, resource)
    response = await client.get(_BASE + "/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data and "total" in data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


# ── Read ──────────────────────────────────────────────────────────────────────


async def test_get_assignment_by_id(client: AsyncClient, db_session: AsyncSession) -> None:
    task = await create_task(db_session)
    resource = await create_resource(db_session)
    dispatch = await create_dispatch(db_session, task, resource)
    response = await client.get(f"{_BASE}/{dispatch.id}")
    assert response.status_code == 200
    assert response.json()["id"] == dispatch.id


async def test_get_assignment_not_found(client: AsyncClient) -> None:
    response = await client.get(f"{_BASE}/99999")
    assert response.status_code == 404


# ── By task / resource ────────────────────────────────────────────────────────


async def test_get_assignments_by_task(client: AsyncClient, db_session: AsyncSession) -> None:
    task = await create_task(db_session)
    resource = await create_resource(db_session)
    await create_dispatch(db_session, task, resource)
    response = await client.get(f"{_BASE}/by-task/{task.id}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["task_id"] == task.id


async def test_get_assignments_by_resource(client: AsyncClient, db_session: AsyncSession) -> None:
    task = await create_task(db_session)
    resource = await create_resource(db_session)
    await create_dispatch(db_session, task, resource)
    response = await client.get(f"{_BASE}/by-resource/{resource.id}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["resource_id"] == resource.id


# ── Update / status flow ──────────────────────────────────────────────────────


async def test_cancel_assignment_releases(client: AsyncClient, db_session: AsyncSession) -> None:
    task = await create_task(db_session, status="assigned")
    resource = await create_resource(db_session, status="busy")
    dispatch = await create_dispatch(db_session, task, resource, status="assigned")

    response = await client.patch(f"{_BASE}/{dispatch.id}", json={"status": "cancelled"})
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    res_resp = await client.get(api(f"/adjusters/{resource.id}"))
    assert res_resp.json()["status"] == "available"

    task_resp = await client.get(api(f"/incidents/{task.id}"))
    assert task_resp.json()["status"] == "cancelled"


async def test_update_assignment_status_flow(client: AsyncClient, db_session: AsyncSession) -> None:
    task = await create_task(db_session)
    resource = await create_resource(db_session)
    dispatch = await create_dispatch(db_session, task, resource, status="assigned")

    for new_status in ("accepted", "en_route", "arrived"):
        response = await client.patch(f"{_BASE}/{dispatch.id}", json={"status": new_status})
        assert response.status_code == 200
        assert response.json()["status"] == new_status
