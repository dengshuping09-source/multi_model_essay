from __future__ import annotations

from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import delete

from app.db.models import User
from app.db.session import get_session_factory


async def authenticate_test_client(client: AsyncClient) -> UUID:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": f"integration-{uuid4()}@example.com",
            "display_name": "Integration test",
            "password": "test-password-2026",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    client.headers["Authorization"] = f"Bearer {payload['access_token']}"
    return UUID(payload["user"]["id"])


async def delete_test_user(user_id: UUID | None) -> None:
    if user_id is None:
        return
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
