"""What has to wait until the transaction that caused it has committed.

Paying XP and finishing a course both happen inside a transaction, and both
have consequences outside the database: points on the Redis leaderboard, a
certificate PDF for the worker to draw. Doing those before the commit would
act on something that may still be rolled back -- so the services stage them
on the session, and whoever commits calls `run` straight after.

One function rather than one call per consequence, so that a caller cannot
remember the leaderboard and forget the certificate. Neither step raises: the
committed rows are the record, and each consequence has its own way back (the
leaderboard's nightly rebuild, the certificate download that queues its PDF).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import certificates, leaderboard


async def run(session: AsyncSession) -> None:
    """Call after `commit()`. Carries out whatever that commit staged."""
    await leaderboard.publish_awards(session)
    certificates.dispatch_staged(session)
