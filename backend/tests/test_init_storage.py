"""`scripts.init_storage`: what the media bucket lets an anonymous visitor do.

The rules themselves were checked against a real RustFS server in
docs/report/assets/phase-6/storage-decision/ (anonymous GET 200, listing 403,
unsigned PUT/DELETE 403). These pin the documents that produce them, and the
idempotence `docker compose up` relies on.
"""

import json

import pytest
from botocore.exceptions import ClientError

from scripts.init_storage import cors_rules, ensure_bucket, parse_origins, public_read_policy


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "Operation")


class FakeS3:
    def __init__(self, *, bucket_exists: bool = False, has_cors: bool = True) -> None:
        self.bucket_exists = bucket_exists
        self.has_cors = has_cors
        self.calls: list[tuple[str, dict]] = []

    def head_bucket(self, **kwargs: object) -> None:
        self.calls.append(("head_bucket", kwargs))
        if not self.bucket_exists:
            raise client_error("404")

    def create_bucket(self, **kwargs: object) -> None:
        # Like RustFS: creating a bucket that exists is a 200, not an error --
        # which is why the script asks head_bucket first.
        self.calls.append(("create_bucket", kwargs))
        self.bucket_exists = True

    def put_bucket_policy(self, **kwargs: object) -> None:
        self.calls.append(("put_bucket_policy", kwargs))

    def put_bucket_cors(self, **kwargs: object) -> None:
        self.calls.append(("put_bucket_cors", kwargs))
        self.has_cors = True

    def delete_bucket_cors(self, **kwargs: object) -> None:
        self.calls.append(("delete_bucket_cors", kwargs))
        if not self.has_cors:
            raise client_error("NoSuchCORSConfiguration")
        self.has_cors = False

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


def test_anonymous_visitors_may_read_objects_and_nothing_else() -> None:
    policy = public_read_policy("devpath-media")

    (statement,) = policy["Statement"]
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"AWS": ["*"]}
    # GetObject on objects, not ListBucket on the bucket: certificate PDFs
    # carry learners' names, and a listing would hand out every key.
    assert statement["Action"] == ["s3:GetObject"]
    assert statement["Resource"] == ["arn:aws:s3:::devpath-media/*"]


def test_cors_allows_the_page_to_upload_and_play_and_nothing_more() -> None:
    (rule,) = cors_rules(["http://localhost:3000"])

    assert rule["AllowedOrigins"] == ["http://localhost:3000"]
    assert sorted(rule["AllowedMethods"]) == ["GET", "HEAD", "PUT"]
    assert "DELETE" not in rule["AllowedMethods"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", []),
        ("  ", []),
        ("http://localhost:3000", ["http://localhost:3000"]),
        ("http://a.test, http://b.test ,", ["http://a.test", "http://b.test"]),
    ],
)
def test_origins_are_read_from_a_comma_separated_value(raw: str, expected: list[str]) -> None:
    assert parse_origins(raw) == expected


def test_a_fresh_server_gets_the_bucket_policy_and_cors() -> None:
    s3 = FakeS3()

    ensure_bucket(s3, "devpath-media", ["http://localhost:3000"])

    assert s3.names() == ["head_bucket", "create_bucket", "put_bucket_policy", "put_bucket_cors"]
    policy = json.loads(s3.calls[2][1]["Policy"])
    assert policy == public_read_policy("devpath-media")


def test_running_again_keeps_the_bucket_and_rewrites_the_rules() -> None:
    """Every `docker compose up` runs it; the second run must not fail, and a
    changed value must win over the stored one."""
    s3 = FakeS3(bucket_exists=True)

    done = ensure_bucket(s3, "devpath-media", ["http://localhost:3000"])

    assert s3.names() == ["head_bucket", "put_bucket_policy", "put_bucket_cors"]
    assert "devpath-media already there" in done
    assert not any(line.startswith("created") for line in done)


def test_same_origin_removes_cors_left_from_before() -> None:
    s3 = FakeS3(bucket_exists=True, has_cors=True)

    ensure_bucket(s3, "devpath-media", [])

    assert "delete_bucket_cors" in s3.names()
    assert not s3.has_cors


def test_same_origin_with_no_cors_to_remove_is_not_an_error() -> None:
    s3 = FakeS3(bucket_exists=True, has_cors=False)

    done = ensure_bucket(s3, "devpath-media", [])

    assert done[-1] == "no CORS (same origin)"


def test_a_real_failure_is_not_swallowed() -> None:
    class Refusing(FakeS3):
        def head_bucket(self, **kwargs: object) -> None:
            raise client_error("AccessDenied")

    with pytest.raises(ClientError):
        ensure_bucket(Refusing(), "devpath-media", [])
