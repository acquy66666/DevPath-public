"""The progress channel: what is published, and what a socket does with it.

The loop under test is `stream_progress`, and it is written against two
narrow protocols -- something to read snapshots from, something to send on --
so every question about it can be asked without Redis, without a database and
without a WebSocket. What is left is the behaviour that actually matters, and
most of it is about the channel *failing*:

Redis pub/sub delivers to whoever is listening at that instant and to nobody
else. There is no queue, no replay and no acknowledgement. So the interesting
tests here are not "does an event get through" -- they are "what happens to
the student whose event did not", and the answer has to be the same thing the
polling client would have seen.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.deps import WEBSOCKET_BEARER, websocket_token
from app.schemas.grading import GradingCaseEvent, GradingEvent
from app.services.grading_events import (
    BLIND_SNAPSHOT_SECONDS,
    EXPIRED,
    FINISHED,
    GONE,
    QUIET_SNAPSHOT_SECONDS,
    RedisEventPublisher,
    RedisEventStream,
    SilentStream,
    _shared_publisher,
    channel_for,
    publish_event,
    stream_progress,
)

SUBMISSION = uuid.UUID("11111111-1111-1111-1111-111111111111")


def running(completed: int = 0, total: int = 3) -> GradingEvent:
    return GradingEvent(
        submission_id=SUBMISSION,
        status="running",
        total_cases=total,
        completed_cases=completed,
    )


def finished(verdict: str = "AC") -> GradingEvent:
    return GradingEvent(
        submission_id=SUBMISSION,
        status="done",
        total_cases=3,
        completed_cases=3,
        verdict=verdict,
        score=100,
    )


def snapshot(status: str = "running", **fields) -> GradingEvent:
    return GradingEvent(
        type="snapshot", submission_id=SUBMISSION, status=status, **fields
    )


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    def statuses(self) -> list[str]:
        return [message["status"] for message in self.sent]

    def kinds(self) -> list[str]:
        return [message["type"] for message in self.sent]


class ScriptedStream:
    """Hands out prepared events; `None` stands for a wait that timed out."""

    def __init__(self, *events: GradingEvent | None, live: bool = True) -> None:
        self._events = list(events)
        self.live = live
        self.waits: list[float] = []

    async def next_event(self, timeout: float) -> GradingEvent | None:
        self.waits.append(timeout)
        if not self._events:
            raise AssertionError("the loop waited for more events than the script has")
        return self._events.pop(0)


def snapshots(*events: GradingEvent | None):
    """A snapshot reader that answers with each of these in turn, then repeats
    the last one for as long as it is asked."""
    remaining = list(events)

    async def read() -> GradingEvent | None:
        if len(remaining) > 1:
            return remaining.pop(0)
        return remaining[0]

    return read


# --- The channel itself ----------------------------------------------------


def test_every_submission_has_its_own_channel() -> None:
    other = uuid.uuid4()
    assert channel_for(SUBMISSION) != channel_for(other)
    assert str(SUBMISSION) in channel_for(SUBMISSION)


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1


class BrokenRedis:
    def publish(self, channel: str, message: str) -> int:
        raise RedisConnectionError("redis is down")


def test_an_event_is_published_as_json_on_its_own_channel() -> None:
    client = FakeRedis()
    event = running(completed=2)

    RedisEventPublisher(client).publish(event)

    channel, payload = client.published[0]
    assert channel == channel_for(SUBMISSION)
    assert GradingEvent.model_validate_json(payload) == event


def test_a_redis_that_is_down_does_not_raise() -> None:
    """The caller is a worker in the middle of grading a submission.

    Progress is commentary on work whose real record has already been
    committed. A failure to narrate must not become a failure to grade.
    """
    RedisEventPublisher(BrokenRedis()).publish(running())


def test_the_shared_publisher_is_the_adapter_and_not_a_bare_client() -> None:
    """A regression test for a bug that only a running stack could find.

    `_shared_publisher` once returned the Redis client itself. Every call then
    reached `Redis.publish(event)` -- one argument where two were wanted --
    and `publish_event` dutifully swallowed the `TypeError`, so grading kept
    working and not a single progress event was ever delivered. Every unit
    test still passed: they exercise the adapter directly, and the fixtures
    replace this function. What is asserted here is the wiring between them.

    It reaches for the private builder because the public `get_publisher` is
    exactly what the fixtures stand in for; going around them is the point.
    Nothing connects: redis-py builds its client lazily.
    """
    assert isinstance(_shared_publisher(), RedisEventPublisher)


def test_publishing_swallows_anything_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """The seam is `publish_event`, not the adapter, so it is broader than
    `RedisError` -- a client that cannot even be built is on the same side of
    the line as a network that is down."""

    def explode():
        raise RuntimeError("no client for you")

    monkeypatch.setattr("app.services.grading_events.get_publisher", explode)
    publish_event(running())


class FakePubSub:
    def __init__(self, *messages) -> None:
        self._messages = list(messages)

    async def get_message(self, *, ignore_subscribe_messages: bool, timeout: float):
        return self._messages.pop(0)


async def test_a_published_event_arrives_as_the_model_it_left_as() -> None:
    event = running(completed=1)
    stream = RedisEventStream(FakePubSub({"data": event.model_dump_json()}))

    assert await stream.next_event(1.0) == event


async def test_a_stray_message_on_the_channel_is_ignored_not_relayed() -> None:
    """Redis channels are not typed and not ours alone.

    Anything unreadable reads as quiet, which the loop answers with a database
    read -- so a stray publisher can waste a query and cannot close a socket
    or show a student a made-up verdict.
    """
    stream = RedisEventStream(FakePubSub({"data": '{"hello": "world"}'}))

    assert await stream.next_event(1.0) is None


# --- The loop: what a client is told ---------------------------------------


async def test_a_socket_opens_with_a_snapshot_before_anything_is_published() -> None:
    socket = FakeSocket()

    await stream_progress(
        snapshots(snapshot(total_cases=3), snapshot("done")),
        ScriptedStream(None),
        socket,
    )

    assert socket.kinds()[0] == "snapshot"
    assert socket.sent[0]["total_cases"] == 3


async def test_a_client_that_connects_after_the_grading_finished_is_told_at_once() -> (
    None
):
    """The failure this whole design is arranged around.

    Grading a two-case exercise takes a second or two. A page that opens its
    socket after that has missed every event there will ever be, and a channel
    with no replay has nothing left to give it. Opening with a read is what
    keeps that client from waiting forever for a message that was published
    before it arrived.
    """
    socket = FakeSocket()

    reason = await stream_progress(
        snapshots(snapshot("done", verdict="AC", score=100)),
        # Not one event, ever: the script would raise if the loop waited.
        ScriptedStream(),
        socket,
    )

    assert reason == FINISHED
    assert socket.statuses() == ["done"]
    assert socket.sent[0]["verdict"] == "AC"


async def test_progress_events_are_relayed_as_they_come() -> None:
    socket = FakeSocket()

    reason = await stream_progress(
        snapshots(snapshot()),
        ScriptedStream(running(1), running(2), running(3), finished()),
        socket,
    )

    assert reason == FINISHED
    # The opening snapshot, three ticks, then the verdict.
    assert [message["completed_cases"] for message in socket.sent] == [0, 1, 2, 3, 3]
    assert socket.kinds() == ["snapshot", "progress", "progress", "progress", "progress"]


async def test_a_case_that_was_hidden_stays_hidden_on_the_way_through() -> None:
    """The loop relays; it does not edit. What it must not do is add.

    The event is passed through as the worker built it, and the worker built
    it out of a model with no field for output -- so this asserts the shape
    that arrives at a browser, which is the only shape that matters.
    """
    socket = FakeSocket()
    event = GradingEvent(
        submission_id=SUBMISSION,
        status="running",
        total_cases=2,
        completed_cases=1,
        case=GradingCaseEvent(position=1, is_hidden=True, verdict="WA", run_time_ms=9),
    )

    await stream_progress(
        snapshots(snapshot()), ScriptedStream(event, finished()), socket
    )

    relayed = socket.sent[1]["case"]
    assert relayed == {
        "position": 1,
        "is_hidden": True,
        "verdict": "WA",
        "run_time_ms": 9,
    }


async def test_quiet_is_answered_by_reading_the_database_again() -> None:
    """A message that was never delivered must not cost a student the result.

    Publishing happens once, to whoever is listening at that instant. If the
    subscription was still being set up, or the connection blinked, the event
    is gone. The loop answers silence with a read, which is exactly what the
    polling client it replaces would have done.
    """
    socket = FakeSocket()

    reason = await stream_progress(
        snapshots(snapshot(), snapshot("done", verdict="WA")),
        ScriptedStream(None),
        socket,
    )

    assert reason == FINISHED
    assert socket.kinds() == ["snapshot", "snapshot"]
    assert socket.sent[-1]["verdict"] == "WA"


async def test_a_submission_deleted_while_being_watched_ends_the_socket() -> None:
    socket = FakeSocket()

    reason = await stream_progress(
        snapshots(snapshot(), None), ScriptedStream(None), socket
    )

    assert reason == GONE


async def test_a_viewer_who_may_not_read_it_is_never_accepted() -> None:
    """No snapshot, no socket. The permission check is the first read, so
    there is no state in which a stream has been subscribed to on behalf of
    someone who was never allowed to see the submission."""
    socket = FakeSocket()

    reason = await stream_progress(snapshots(None), ScriptedStream(), socket)

    assert reason == GONE
    assert socket.sent == []


async def test_a_socket_does_not_wait_forever() -> None:
    """A worker that died holding the row at `running` leaves nothing to wait
    for, and a forgotten tab must not hold a connection over it."""
    socket = FakeSocket()

    reason = await stream_progress(
        snapshots(snapshot()), ScriptedStream(), socket, deadline_seconds=0
    )

    assert reason == EXPIRED
    assert socket.statuses() == ["running"]


async def test_a_socket_with_no_channel_behind_it_reads_more_often() -> None:
    """Redis being down is exactly when the fallback carries the feature.

    The socket still works -- it becomes a poll that happens to run over a
    WebSocket -- so it polls at a rate a person would accept rather than at
    the heartbeat rate meant for a channel that is doing the real work.
    """
    blind = ScriptedStream(None, live=False)

    await stream_progress(
        snapshots(snapshot(), snapshot("done")), blind, FakeSocket()
    )

    assert blind.waits == [BLIND_SNAPSHOT_SECONDS]
    assert BLIND_SNAPSHOT_SECONDS < QUIET_SNAPSHOT_SECONDS


async def test_a_dead_subscription_reads_as_quiet_rather_than_as_an_error() -> None:
    """`SilentStream` is what `subscribe` yields when Redis will not talk."""
    stream = SilentStream()
    assert stream.live is False
    assert await asyncio.wait_for(stream.next_event(0.01), timeout=1) is None


# --- How a token reaches a socket ------------------------------------------


def websocket_offering(*subprotocols: str):
    class Handshake:
        scope = {"subprotocols": list(subprotocols)}

    return Handshake()


def test_the_token_travels_in_the_handshake_not_in_the_url() -> None:
    """A query string ends up in nginx's access log, and an access token in a
    log file is a credential someone else can read tomorrow."""
    assert (
        websocket_token(websocket_offering(WEBSOCKET_BEARER, "a.b.c")) == "a.b.c"
    )


@pytest.mark.parametrize(
    "offered",
    [
        (),
        (WEBSOCKET_BEARER,),
        ("a.b.c",),
        (WEBSOCKET_BEARER, "a.b.c", "extra"),
        ("basic", "a.b.c"),
    ],
)
def test_anything_but_exactly_our_two_protocols_carries_no_token(offered) -> None:
    """Guessing which entry is the credential is how a credential gets read
    out of the wrong field."""
    assert websocket_token(websocket_offering(*offered)) is None
