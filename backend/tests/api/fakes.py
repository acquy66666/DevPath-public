"""Stand-ins for the things this app talks to but the tests must not.

`ObjectStorage` is a Protocol precisely so the routes can be exercised without
a bucket: the fake below records what was asked of it and signs nothing real.
Videos and avatars both go through it, so it lives here rather than in either
test module.
"""


class FakeStorage:
    """Records what was signed, deleted, and moved. Reaches no network."""

    def __init__(self) -> None:
        self.signed: list[tuple[str, str, int]] = []
        self.deleted_prefixes: list[str] = []
        self.uploaded: list[tuple[str, str]] = []
        self.downloaded: list[str] = []

    def presigned_put_url(self, key: str, content_type: str, expires_in: int) -> str:
        self.signed.append((key, content_type, expires_in))
        return f"https://bucket.example/{key}?signature=fake"

    def public_url(self, key: str) -> str:
        return f"https://cdn.example/{key}"

    def download_file(self, key: str, destination: str) -> None:
        self.downloaded.append(key)

    def upload_file(self, source: str, key: str, content_type: str | None = None) -> None:
        self.uploaded.append((source, key))

    def delete_prefix(self, prefix: str) -> None:
        self.deleted_prefixes.append(prefix)


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
