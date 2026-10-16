"""Stand-ins for the things this app talks to but the tests must not.

`ObjectStorage` is a Protocol precisely so the routes can be exercised without
a bucket: the fake below records what was asked of it and signs nothing real.
Videos, avatars and transcripts all go through it, so it lives here rather
than in any one test module.
"""

from typing import NamedTuple

from app.services.storage import StorageError


class SignedPut(NamedTuple):
    """One upload URL as it was asked for."""

    key: str
    content_type: str
    expires_in: int
    size_bytes: int


class FakeStorage:
    """Records what was signed, deleted, and moved. Reaches no network."""

    def __init__(self) -> None:
        self.signed: list[SignedPut] = []
        self.deleted_prefixes: list[str] = []
        self.uploaded: list[tuple[str, str]] = []
        self.downloaded: list[str] = []
        # Small objects the API writes itself (transcripts): key -> (bytes, type).
        self.objects: dict[str, tuple[bytes, str]] = {}

    def presigned_put_url(
        self, key: str, content_type: str, expires_in: int, *, size_bytes: int
    ) -> str:
        self.signed.append(SignedPut(key, content_type, expires_in, size_bytes))
        return f"https://bucket.example/{key}?signature=fake"

    def public_url(self, key: str) -> str:
        return f"https://cdn.example/{key}"

    def download_file(self, key: str, destination: str) -> None:
        self.downloaded.append(key)

    def upload_file(self, source: str, key: str, content_type: str | None = None) -> None:
        self.uploaded.append((source, key))

    def upload_bytes(self, data: bytes, key: str, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def read_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise StorageError(f"Không đọc được {key} từ kho lưu trữ")
        return self.objects[key][0]

    def delete_prefix(self, prefix: str) -> None:
        self.deleted_prefixes.append(prefix)
        for key in [key for key in self.objects if key.startswith(prefix)]:
            del self.objects[key]


class UnwritableStorage(FakeStorage):
    """A bucket that takes no new objects -- a 502 the API has to survive."""

    def upload_bytes(self, data: bytes, key: str, content_type: str) -> None:
        raise StorageError("Kho lưu trữ không nhận tệp")


class RefusingStorage(FakeStorage):
    """A bucket that will not delete. Used to prove a failed cleanup is survivable."""

    def delete_prefix(self, prefix: str) -> None:
        raise RuntimeError("bucket unreachable")


class AllowAllRateLimiter:
    """A limiter that never refuses, and remembers being asked.

    The default for API tests: almost none of them are about rate limiting,
    and the real limiter would both need Redis and reject the second
    submission in any test that makes two.
    """

    def __init__(self) -> None:
        self.claims: list[tuple[str, int]] = []
        self.counts: list[tuple[str, int, int]] = []

    async def claim(self, key: str, seconds: int) -> int:
        self.claims.append((key, seconds))
        return 0

    async def count(self, key: str, limit: int, window_seconds: int) -> int:
        self.counts.append((key, limit, window_seconds))
        return 0


class MemoryRateLimiter:
    """The real rules, in a dictionary, on a clock the test moves itself.

    Same semantics as `RedisRateLimiter` -- a claim held for N seconds, a
    counter per window -- so a test can prove the endpoint refuses without
    sleeping through a real cooldown.
    """

    def __init__(self) -> None:
        self.held: dict[str, int] = {}
        self.used: dict[str, int] = {}
        self.window_ends: dict[str, int] = {}
        self.now = 0

    async def claim(self, key: str, seconds: int) -> int:
        until = self.held.get(key, 0)
        if until > self.now:
            return until - self.now
        self.held[key] = self.now + seconds
        return 0

    async def count(self, key: str, limit: int, window_seconds: int) -> int:
        if self.window_ends.get(key, 0) <= self.now:
            self.used[key] = 0
            self.window_ends[key] = self.now + window_seconds

        self.used[key] += 1
        if self.used[key] <= limit:
            return 0
        return self.window_ends[key] - self.now


class MemoryRecommendationCache:
    """The recommendation cache as a dictionary.

    Holds `CachedList` objects rather than their JSON, because the encoding is
    tested on its own (`tests/test_recommendations.py`) and a test about the
    endpoint should not have to spell out a payload to make its point.

    The distinction the endpoint turns on is kept exactly: a user with no key
    reads as None ("nothing computed yet"), and a user whose entry holds an
    empty list reads as a computed empty list.
    """

    def __init__(self) -> None:
        self.entries: dict[object, object] = {}

    async def read(self, user_id):
        return self.entries.get(user_id)

    def write(self, user_id, cached) -> None:
        self.entries[user_id] = cached


class FakeQueue:
    """Records what was handed to Celery, and hands it to nobody.

    Shared rather than redefined per module: `TaskQueue` grows a method every
    time a feature schedules something, and a local fake that implements only
    yesterday's methods fails as an AttributeError in the middle of an
    unrelated test.
    """

    def __init__(self) -> None:
        self.enqueued: list = []
        self.ingested: list = []
        self.embedded: list = []

    def enqueue_transcode(self, video_asset_id) -> None:
        self.enqueued.append(video_asset_id)

    def enqueue_ingest(self, course_id) -> None:
        self.ingested.append(course_id)

    def enqueue_course_embedding(self, course_id) -> None:
        self.embedded.append(course_id)


class MemoryLeaderboard:
    """The leaderboard's sorted sets as dictionaries.

    Ordered the way Redis orders a `ZREVRANGE`: highest score first, and equal
    scores by member, descending. Keeps what the adapter keeps -- which keys
    have been rebuilt from the ledger and with what TTL -- so a test can ask
    whether a read rebuilt a board rather than guess from its contents.
    """

    def __init__(self) -> None:
        self.boards: dict[str, dict[str, int]] = {}
        self.built: set[str] = set()
        self.ttls: dict[str, int | None] = {}
        self.fail = False

    def add(self, increments) -> None:
        if self.fail:
            raise ConnectionError("Redis is down")
        for key, member, amount, ttl in increments:
            board = self.boards.setdefault(key, {})
            board[member] = board.get(member, 0) + amount
            self.ttls[key] = ttl

    def replace(self, key, scores, ttl) -> None:
        if scores:
            self.boards[key] = dict(scores)
        else:
            self.boards.pop(key, None)
        self.built.add(key)
        self.ttls[key] = ttl

    def is_built(self, key) -> bool:
        return key in self.built

    def snapshot(self, key, offset, limit, member):
        from app.services.leaderboard import Snapshot

        board = self.boards.get(key, {})
        ordered = sorted(board.items(), key=lambda row: (row[1], row[0]), reverse=True)
        rows = ordered[offset : offset + limit]

        def above(score: int) -> int:
            return sum(1 for value in board.values() if value > score)

        mine = board.get(member)
        return Snapshot(
            rows=rows,
            total=len(board),
            above_first=above(rows[0][1]) if rows else 0,
            my_score=mine,
            my_above=above(mine) if mine is not None else None,
        )
