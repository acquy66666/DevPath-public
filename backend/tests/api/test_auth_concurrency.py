"""Two refreshes with one cookie at the same moment.

Everything else in this suite runs inside one rolled-back transaction, on one
connection -- which cannot race. This needs two real connections, so unlike
the rest it commits, under an `@e2e.devpath.example` address
(`scripts.purge_e2e` removes it if the cleanup below never ran), and deletes
what it wrote.
"""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import hash_refresh_token
from app.models import RefreshToken, User
from app.services import auth as auth_service


async def test_two_tabs_refreshing_together_queue_on_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the row lock both requests read the token as unrotated and both
    rotate it; with it, the second waits for the first, finds the token
    rotated a moment ago, and comes in through the leeway."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    email = f"refresh-concurrency-{uuid.uuid4().hex[:12]}@e2e.devpath.example"

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            # ck_users_credential wants a password or Google; this one opens nothing.
            user = User(email=email, full_name="Hai Tab", password_hash="!not-a-bcrypt-hash")
            session.add(user)
            await session.flush()
            issued = await auth_service._issue_tokens(session, user, auth_service.ClientInfo())
            await session.commit()
    except OSError as exc:
        await engine.dispose()
        if os.getenv("CI"):
            raise
        pytest.skip(f"Postgres không chạy ({exc}).")

    let_in: list[bool] = []
    real_check = auth_service._rotated_moments_ago

    async def counting_check(session: AsyncSession, row: RefreshToken) -> bool:
        verdict = await real_check(session, row)
        let_in.append(verdict)
        return verdict

    monkeypatch.setattr(auth_service, "_rotated_moments_ago", counting_check)

    async def one_tab() -> auth_service.IssuedTokens:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            return await auth_service.rotate_refresh_token(
                session, raw_token=issued.refresh_token
            )

    try:
        first, second = await asyncio.gather(one_tab(), one_tab())

        # One rotation, one late tab let in -- not two rotations.
        assert let_in == [True]
        assert first.refresh_token != second.refresh_token

        async with AsyncSession(engine) as session:
            rows = {
                row.token_hash: row
                for row in await session.scalars(
                    select(RefreshToken).where(RefreshToken.user_id == user.id)
                )
            }
        original = rows[hash_refresh_token(issued.refresh_token)]
        new_hashes = {hash_refresh_token(t.refresh_token) for t in (first, second)}
        assert original.revoked_at is not None
        assert original.replaced_by_id in {rows[h].id for h in new_hashes}
        assert all(rows[h].revoked_at is None for h in new_hashes)
    finally:
        async with AsyncSession(engine) as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await engine.dispose()
