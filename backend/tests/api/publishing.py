"""Putting a course on sale the only way there is: submit, then an admin approves.

Shared because half the suite needs a published course made through the API,
and since the auto-approve flag went away that takes two actors, not one.
"""

import uuid

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import User
from app.services.tasks import get_task_queue
from tests.api.fakes import FakeQueue

PASSWORD = "mật-khẩu-đủ-dài"


async def make_admin(session: AsyncSession) -> User:
    admin = User(
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Quản Trị Viên",
        password_hash=hash_password(PASSWORD),
        role="admin",
    )
    session.add(admin)
    await session.flush()
    return admin


async def admin_headers(client: AsyncClient, session: AsyncSession) -> dict[str, str]:
    admin = await make_admin(session)
    response = await client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def publish_via_review(
    app: FastAPI,
    client: AsyncClient,
    session: AsyncSession,
    course_id: uuid.UUID | str,
    instructor: dict[str, str],
) -> dict:
    """Submit as the instructor, approve as a fresh admin. Returns the course.

    Approving schedules Celery jobs; unless the test installed its own queue,
    they go to a fake rather than to a broker.
    """
    app.dependency_overrides.setdefault(get_task_queue, FakeQueue)

    submitted = await client.post(f"/api/v1/courses/{course_id}/submit", headers=instructor)
    assert submitted.status_code == 200, submitted.text

    approved = await client.post(
        f"/api/v1/admin/courses/{course_id}/approve",
        headers=await admin_headers(client, session),
    )
    assert approved.status_code == 200, approved.text
    return approved.json()
