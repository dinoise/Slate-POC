"""Integration tests for the /api/v1/users endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import api
from tests.factories import create_user

_BASE = api("/users")


# ── Create ────────────────────────────────────────────────────────────────────


async def test_create_user_201(client: AsyncClient) -> None:
    payload = {
        "first_name": "María",
        "last_name": "González",
        "email": "maria@test.com",
        "phone": "5551110000",
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "María"
    assert body["email"] == "maria@test.com"
    assert body["id"] is not None


async def test_create_user_generates_external_id(client: AsyncClient) -> None:
    payload = {
        "first_name": "Juan",
        "last_name": "Pérez",
        "email": "juan@test.com",
    }
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 201
    assert response.json()["external_id"] is not None
    assert len(response.json()["external_id"]) > 0


async def test_create_user_duplicate_email_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="duplicate@test.com")
    payload = {"first_name": "Otro", "last_name": "Usuario", "email": "duplicate@test.com"}
    response = await client.post(_BASE + "/", json=payload)
    assert response.status_code == 409


# ── List ──────────────────────────────────────────────────────────────────────


async def test_get_users_empty(client: AsyncClient) -> None:
    response = await client.get(_BASE + "/")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_users_returns_list(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session)
    await create_user(db_session)
    response = await client.get(_BASE + "/")
    assert response.status_code == 200
    assert len(response.json()) == 2


# ── Read ──────────────────────────────────────────────────────────────────────


async def test_get_user_by_id(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await create_user(db_session, first_name="Test")
    response = await client.get(f"{_BASE}/{user.id}")
    assert response.status_code == 200
    assert response.json()["id"] == user.id
    assert response.json()["first_name"] == "Test"


async def test_get_user_not_found_404(client: AsyncClient) -> None:
    response = await client.get(f"{_BASE}/99999")
    assert response.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────


async def test_update_user(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await create_user(db_session, first_name="Original")
    response = await client.patch(f"{_BASE}/{user.id}", json={"first_name": "Updated"})
    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"


async def test_update_user_not_found_404(client: AsyncClient) -> None:
    response = await client.patch(f"{_BASE}/99999", json={"first_name": "X"})
    assert response.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────


async def test_delete_user_204(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await create_user(db_session)
    response = await client.delete(f"{_BASE}/{user.id}")
    assert response.status_code == 204


async def test_delete_user_not_found_404(client: AsyncClient) -> None:
    response = await client.delete(f"{_BASE}/99999")
    assert response.status_code == 404


async def test_get_user_after_delete_404(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await create_user(db_session)
    await client.delete(f"{_BASE}/{user.id}")
    response = await client.get(f"{_BASE}/{user.id}")
    assert response.status_code == 404
