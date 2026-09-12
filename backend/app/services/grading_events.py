"""Telling a student what the grader is doing, while it does it.

Grading takes seconds and happens in another process. Without a channel the
page can only guess, and the honest way to guess is to ask again -- polling,
which costs a request and a database round trip per student per second and
still shows a stale answer most of the time.

So the worker publishes what it is doing to Redis, and a WebSocket relays it.
Three properties of that arrangement shape everything in this module:

**Redis pub/sub has no memory.** A message published while nobody is
subscribed is gone; there is no replay, no acknowledgement and no redelivery.
A client that connects a moment late, or reconnects after a dropped Wi-Fi,
would otherwise wait forever for an event that already happened.

**So the database stays the source of truth.** Every socket opens with a
snapshot read from it, and goes back for another whenever the channel has been
quiet. The published events make the wait legible; the snapshots make it
correct. This is why losing Redis degrades the feature rather than breaking
it: the socket falls back to reading, which is what polling is.

**Nothing here is a result.** An event carries a status, a count and a letter
per case -- never output, never a message, never a test case's input. The
result is read from `GET /submissions/{id}`, the one endpoint where the
hidden-test-case rule is written down and tested.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Protocol

import redis
import redis.asyncio as aioredis
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import User
from app.schemas.grading import GradingEvent

logger = logging.getLogger(__name__)

#: One channel per submission rather than per user. Who may listen is decided
#: by whether they may read the submission, which is a question the database
#: already answers -- and a channel per user would need that same answer plus a
#: second rule about which of their submissions this message was about.
CHANNEL = "grading:events:{submission}"

#: How long a socket waits for a published event before reading the database
#: anyway. It is a heartbeat, a repair for a message that was never delivered,
#: and the thing that ends a socket whose worker died -- all for one indexed
#: read per idle client per interval.
QUIET_SNAPSHOT_SECONDS = 10.0

#: The same, for a socket that never got a subscription. Redis being down is
#: exactly when the fallback has to carry the feature, so it reads more often.
BLIND_SNAPSHOT_SECONDS = 2.0

#: How long to wait for Redis to confirm a subscription before giving up on
#: the confirmation and getting on with it.
CONFIRMATION_TIMEOUT_SECONDS = 1.0

#: The whole subscribe, connection included. Past this the socket gives up on
#: the channel and serves snapshots instead -- which is a working page, so
#: waiting longer buys nothing a student would thank us for.
SUBSCRIBE_TIMEOUT_SECONDS = 1.5

#: A socket is closed after this long no matter what. A submission that has
#: not finished in five minutes is not going to, and a forgotten tab must not
#: hold a Redis connection for a week.
MAX_SESSION_SECONDS = 300.0


def channel_for(submission_id: uuid.UUID) -> str:
    return CHANNEL.format(submission=submission_id)


# --- Publishing (the worker's side, and therefore synchronous) -------------


class EventPublisher(Protocol):
    """What the worker needs. A Protocol so a test can collect events in a
    list instead of running Redis."""

    def publish(self, event: GradingEvent) -> None: ...


class RedisEventPublisher:
    """Fire and forget, on purpose.

    A failure to publish is swallowed and logged. Progress is commentary on
    work whose real record is a database row that has already been committed:
    a student whose events are lost sees the page update a few seconds later
    from a snapshot instead, and a grading run that failed because Redis was
    briefly unreachable would be a worse outcome by every measure.
    """

    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    def publish(self, event: GradingEvent) -> None:
        try:
            self._redis.publish(
                channel_for(event.submission_id), event.model_dump_json()
            )
        except RedisError as exc:
            logger.warning(
                "could not publish grading progress for %s: %s",
                event.submission_id,
                exc,
            )


@lru_cache
def _shared_publisher() -> RedisEventPublisher:
    # The synchronous client, because the caller is a Celery worker: the
    # per-case callback fires from inside a blocking judge, where there is no
    # loop to await on.
    client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    return RedisEventPublisher(client)


def get_publisher() -> EventPublisher:
    return _shared_publisher()


def publish_event(event: GradingEvent) -> None:
    """Publish, and never let it be the reason a submission was not graded.

    Broader than the adapter's own `RedisError` guard by intention. This is
    the seam between grading and telemetry, and everything on the telemetry
    side of it -- a client that cannot be built, a model that will not
    serialise -- is a bug worth a log line and never a failed submission.
    """
    try:
        get_publisher().publish(event)
    except Exception as exc:  # noqa: BLE001 - see the docstring
        logger.warning("grading progress not published for %s: %s", event.submission_id, exc)


# --- Listening (the API's side, and therefore asynchronous) ----------------


class EventStream(Protocol):
    """A source of events that can be waited on with a timeout."""

    #: False when there is no subscription behind it, so the caller knows to
    #: read the database more often instead.
    live: bool

    async def next_event(self, timeout: float) -> GradingEvent | None: ...


class RedisEventStream:
    live = True

    def __init__(self, pubsub: aioredis.client.PubSub) -> None:
        self._pubsub = pubsub

    async def next_event(self, timeout: float) -> GradingEvent | None:
        try:
            message = await self._pubsub.get_message(
                ignore_subscribe_messages=True, timeout=timeout
            )
        except RedisError as exc:
            # The subscription died under us. Report quiet rather than raise:
            # the caller answers quiet with a database read, which is exactly
            # the right response to having lost the channel.
            logger.warning("grading event subscription failed: %s", exc)
            await asyncio.sleep(timeout)
            return None

        if message is None:
            return None

        try:
            return GradingEvent.model_validate_json(message["data"])
        except ValidationError:
            # Anything else on this channel is not ours. Ignoring it keeps a
            # stray publisher from closing a student's socket.
            logger.warning("ignored an unreadable message on a grading channel")
            return None


class SilentStream:
    """No subscription at all: every wait times out.

    Returned when Redis cannot be reached, so a socket still works -- it just
    becomes a poll that happens to run over a WebSocket.
    """

    live = False

    async def next_event(self, timeout: float) -> GradingEvent | None:
        await asyncio.sleep(timeout)
        return None


async def _join(pubsub: aioredis.client.PubSub, submission_id: uuid.UUID) -> None:
    await pubsub.subscribe(channel_for(submission_id))
    # Redis answers a subscription with a confirmation message. Left in the
    # buffer, the first `get_message(ignore_subscribe_messages=True)` returns
    # None for it -- indistinguishable from a wait that timed out, so every
    # socket would answer its own subscription with a database read and a
    # duplicate frame. Taking it here costs one round trip at connect; leaving
    # it costs one query per connection forever. It cannot swallow a real
    # event: the confirmation is queued before anything published after it.
    await pubsub.get_message(timeout=CONFIRMATION_TIMEOUT_SECONDS)


@asynccontextmanager
async def subscribe(submission_id: uuid.UUID) -> AsyncIterator[EventStream]:
    """Subscribe to one submission's channel for as long as the block runs."""
    client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    pubsub = client.pubsub()
    try:
        # Bounded rather than left to the client's own retry policy. A Redis
        # that is down is exactly when this path runs, and redis-py answers a
        # refused connection by trying again a few times -- which turned the
        # first frame of a degraded socket into a four-second wait. Giving up
        # quickly is right here: there is a snapshot ready to send either way.
        await asyncio.wait_for(_join(pubsub, submission_id), SUBSCRIBE_TIMEOUT_SECONDS)
    except (RedisError, OSError, TimeoutError) as exc:
        logger.warning("no grading event channel for %s: %s", submission_id, exc)
        # Close the pubsub as well, not just the client: a `wait_for` that
        # timed out cancelled the subscribe half way, and its connection is
        # still checked out of the pool.
        await _close(pubsub, client)
        yield SilentStream()
        return

    try:
        yield RedisEventStream(pubsub)
    finally:
        await _close(pubsub, client)


async def _close(pubsub: aioredis.client.PubSub, client: aioredis.Redis) -> None:
    try:
        await pubsub.aclose()
    except (RedisError, OSError):
        # Already unusable, which is the state we were aiming for.
        logger.debug("grading event subscription did not close cleanly")
    finally:
        await client.aclose()


# --- The snapshot, which is what makes the rest of it safe -----------------


async def snapshot_for(
    session: AsyncSession, submission_id: uuid.UUID, user: User
) -> GradingEvent | None:
    """Where this submission stands, or None if this caller may not know.

    The permission check is not written here: it is `get_submission`, the same
    function the REST endpoint uses, so "may I watch this?" and "may I read
    this?" cannot drift into two different answers. A caller who is refused
    gets None, and a socket that gets None is closed -- which is the same
    answer the REST endpoint gives a stranger, a 404.
    """
    from app.services import grading as grading_service

    try:
        submission, results = await grading_service.get_submission(
            session, submission_id, user
        )
    except grading_service.SubmissionNotFoundError:
        return None

    return GradingEvent(
        type="snapshot",
        submission_id=submission.id,
        status=submission.status,
        total_cases=await grading_service.count_test_cases(
            session, submission.exercise_id, samples_only=submission.is_trial
        ),
        # The rows that exist are the cases that finished, so the count comes
        # from the same read as everything else rather than from a counter
        # somebody has to remember to keep.
        completed_cases=len(results),
        verdict=submission.verdict,
        score=submission.score,
    )


# --- The loop -------------------------------------------------------------


class Socket(Protocol):
    """The half of a WebSocket this module uses. Narrow so the loop below can
    be tested against a list."""

    async def send_json(self, data: object) -> None: ...


ReadSnapshot = Callable[[], Awaitable[GradingEvent | None]]

#: Why a socket ended. The route turns these into close codes, and a test can
#: assert on the reason instead of on how the loop happened to exit.
FINISHED = "finished"
GONE = "gone"
EXPIRED = "expired"


async def stream_progress(
    read_snapshot: ReadSnapshot,
    stream: EventStream,
    socket: Socket,
    *,
    deadline_seconds: float = MAX_SESSION_SECONDS,
) -> str:
    """Send what is known now, then what happens next, until there is nothing
    left to wait for.

    The snapshot comes first and it is not an optimisation. Between a client
    deciding to connect and the subscription being live, the submission may
    already have been graded -- and a channel with no replay has nothing to
    tell it. Opening with a read means a socket connected too late still ends
    correctly, on its very first message.

    Quiet is answered with another read rather than with patience. That covers
    a message that was published while the subscription was still being set
    up, a Redis that dropped the connection, and a worker that died holding
    the row at `running` -- three different failures with one answer, and the
    answer is the same thing the polling client would have done.
    """
    snapshot = await read_snapshot()
    if snapshot is None:
        return GONE

    await socket.send_json(snapshot.model_dump(mode="json"))
    if snapshot.is_terminal:
        return FINISHED

    # A socket with no channel behind it reads more often, because reading is
    # then the only thing it does.
    interval = QUIET_SNAPSHOT_SECONDS if stream.live else BLIND_SNAPSHOT_SECONDS
    loop = asyncio.get_running_loop()
    ends_at = loop.time() + deadline_seconds

    while loop.time() < ends_at:
        event = await stream.next_event(interval)

        if event is None:
            snapshot = await read_snapshot()
            if snapshot is None:
                # The submission was deleted while being watched -- an
                # instructor removing the exercise takes it with them.
                return GONE
            await socket.send_json(snapshot.model_dump(mode="json"))
            if snapshot.is_terminal:
                return FINISHED
            continue

        await socket.send_json(event.model_dump(mode="json"))
        if event.is_terminal:
            return FINISHED

    return EXPIRED
