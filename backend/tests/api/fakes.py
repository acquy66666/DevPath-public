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
