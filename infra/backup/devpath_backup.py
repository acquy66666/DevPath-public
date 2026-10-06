#!/usr/bin/env python3
"""A nightly `pg_dump` of the platform database to a private S3 bucket, and the
way back.

Runs in a container of its own, built from the same image as the database
(infra/backup/Dockerfile). That is the point of it: `pg_dump` refuses a server
newer than itself, and an archive written by a newer `pg_dump` may not load
into an older server, so the tools come from the server's own image and are
always its version. Python is only the glue around them.

    serve                 the service: a backup every day at BACKUP_HOUR, Vietnam time
    backup                one backup, now
    list                  the backups in the bucket, newest first
    restore KEY|latest    into a new side database, while the live one keeps serving
    swap NAME --yes       put a restored database in place of the live one
    health                exit 0 if the last good backup is recent (the healthcheck)

The incident procedure wraps restore and swap: infra/scripts/restore-db.sh.

Standard library and boto3 only -- both come from Debian's own packages in the
image, so nothing here is installed from PyPI at build time.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

#: Vietnam does not observe daylight saving, so a fixed offset is the zone --
#: the same choice as the backend's `app/core/clock.py`.
VIETNAM = timezone(timedelta(hours=7))

PREFIX = "postgres/"
STAMP = "%Y%m%dT%H%M%SZ"
DEFAULT_BUCKET = "devpath-backups"
DEFAULT_MEDIA_BUCKET = "devpath-media"

#: What a database name built here must look like. Everything that reaches SQL
#: as an identifier is checked against this first, so quoting it is enough.
IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]*")
MAX_IDENTIFIER = 63  # NAMEDATALEN - 1

#: Older than this at start-up and the service runs a backup at once instead
#: of waiting for the night: the server was off at the hour, or a run failed.
STALE_AFTER = timedelta(hours=24)
#: The healthcheck's limit: a day, plus slack for a slow run and one retry.
UNHEALTHY_AFTER = timedelta(hours=26)
RETRY_AFTER = timedelta(minutes=30)

MARKER = Path("/tmp/devpath-backup-ok")


class ConfigError(Exception):
    """The environment does not say where backups go, or says somewhere unsafe."""


# --- names ---------------------------------------------------------------------


def backup_key(database: str, now: datetime) -> str:
    """`postgres/<db>-<UTC time>.dump`: sorts by time, and says what it holds."""
    if now.tzinfo is None:
        raise ValueError("backup_key needs an aware datetime")
    return f"{PREFIX}{database}-{now.astimezone(UTC).strftime(STAMP)}.dump"


def key_time(key: str, database: str) -> datetime | None:
    """When a backup of `database` was taken, or None for anything else --
    another database's backups, a stray upload, a file someone put there by
    hand. Only objects this service named are ever listed as its, or deleted.
    """
    match = re.fullmatch(rf"{re.escape(PREFIX)}{re.escape(database)}-(\d{{8}}T\d{{6}}Z)\.dump", key)
    if match is None:
        return None
    return datetime.strptime(match.group(1), STAMP).replace(tzinfo=UTC)


def _side_name(database: str, label: str, now: datetime) -> str:
    name = f"{database}_{label}_{now.astimezone(UTC).strftime(STAMP).lower()}"
    if len(name) > MAX_IDENTIFIER or not IDENTIFIER.fullmatch(name):
        raise ValueError(f"cannot build a database name from {database!r}")
    return name


def restore_target_name(database: str, now: datetime) -> str:
    """The side database a backup is restored into, next to the live one."""
    return _side_name(database, "restore", now)


def parked_name(database: str, now: datetime) -> str:
    """Where the live database goes when a restored one takes its name."""
    return _side_name(database, "before_restore", now)


# --- retention -----------------------------------------------------------------


def _ours(keys: Iterable[str], database: str) -> list[tuple[datetime, str]]:
    found = ((key_time(key, database), key) for key in keys)
    return sorted(((taken, key) for taken, key in found if taken is not None), reverse=True)


def to_prune(keys: Iterable[str], database: str, *, keep: int) -> list[str]:
    """The backups of `database` beyond the newest `keep`, oldest first.

    By count, not by age: a clock that is wrong, or a month with no backups,
    cannot make this delete the only copy there is.
    """
    if keep < 1:
        raise ValueError("keep must be at least 1")
    return [key for _, key in sorted(_ours(keys, database)[keep:])]


# --- schedule ------------------------------------------------------------------


def next_run(now: datetime, *, hour_vn: int) -> datetime:
    """The next `hour_vn`:00 in Vietnam strictly after `now`, in UTC."""
    if not 0 <= hour_vn <= 23:
        raise ValueError("hour_vn must be 0-23")
    local = now.astimezone(VIETNAM)
    candidate = local.replace(hour=hour_vn, minute=0, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)


def is_stale(latest: datetime | None, now: datetime, *, max_age: timedelta) -> bool:
    return latest is None or now - latest > max_age


def first_due(latest: datetime | None, now: datetime, *, hour_vn: int) -> datetime:
    """When a freshly started service runs first: now if last night is
    missing, otherwise at the usual hour."""
    if is_stale(latest, now, max_age=STALE_AFTER):
        return now
    return next_run(now, hour_vn=hour_vn)


# --- storage -------------------------------------------------------------------


@dataclass(frozen=True)
class Storage:
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket: str


def _r2_endpoint(env: Mapping[str, str]) -> str:
    if env.get("R2_ENDPOINT_URL"):
        return env["R2_ENDPOINT_URL"]
    if env.get("R2_ACCOUNT_ID"):
        return f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    return ""


def storage_from_env(env: Mapping[str, str]) -> Storage:
    """Where backups go: BACKUP_* if set, else the R2 credentials the app uses,
    else -- outside production -- the storage service of the dev stack, the
    same fallback the backend makes (infra/docker-compose.yml). Never that in
    production: there it runs on the same machine as the database, and a
    backup that dies with the server is not one (Backblaze B2 instead,
    docs/huong-dan-deploy-vps.md).

    The bucket is never the media one. That bucket answers anonymous GETs so
    the player can fetch video, and a dump holds every email and password hash
    on the platform.
    """
    bucket = env.get("BACKUP_BUCKET") or DEFAULT_BUCKET
    if bucket == (env.get("R2_BUCKET") or DEFAULT_MEDIA_BUCKET):
        raise ConfigError(
            f"BACKUP_BUCKET={bucket} là bucket media (công khai) -- dùng một bucket riêng, private"
        )

    if env.get("BACKUP_ACCESS_KEY_ID") and env.get("BACKUP_SECRET_ACCESS_KEY"):
        endpoint = env.get("BACKUP_ENDPOINT_URL") or _r2_endpoint(env)
        if not endpoint:
            raise ConfigError(
                "có BACKUP_ACCESS_KEY_ID nhưng thiếu BACKUP_ENDPOINT_URL / R2_ACCOUNT_ID"
            )
        return Storage(
            endpoint, env["BACKUP_ACCESS_KEY_ID"], env["BACKUP_SECRET_ACCESS_KEY"], bucket
        )

    endpoint = _r2_endpoint(env)
    if endpoint and env.get("R2_ACCESS_KEY_ID") and env.get("R2_SECRET_ACCESS_KEY"):
        return Storage(endpoint, env["R2_ACCESS_KEY_ID"], env["R2_SECRET_ACCESS_KEY"], bucket)

    if env.get("ENV") == "production":
        raise ConfigError(
            "chưa có nơi lưu backup: đặt BACKUP_* hoặc R2_* trong .env.prod, "
            "hoặc BACKUP_ENABLED=false nếu cố ý chạy không có backup"
        )
    return Storage(
        "http://storage:9000",
        env.get("STORAGE_ACCESS_KEY") or "devpath",
        env.get("STORAGE_SECRET_KEY") or "devpath-storage",
        bucket,
    )


#: Backblaze B2's S3 endpoints name their region, and B2 checks the region in
#: the signature against it -- "auto", which is what R2 wants, is refused.
B2_ENDPOINT = re.compile(r"^https?://s3\.([a-z0-9-]+)\.backblazeb2\.com/?$")


def signing_region(endpoint_url: str) -> str:
    """The region to sign with: the one in a B2 endpoint, else "auto" (R2's;
    the self-hosted RustFS accepts it too)."""
    match = B2_ENDPOINT.match(endpoint_url.strip().lower())
    return match.group(1) if match else "auto"


def list_keys(s3, bucket: str) -> Iterator[str]:
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIX):
        for item in page.get("Contents", []):
            yield item["Key"]


def latest(s3, bucket: str, database: str) -> tuple[str | None, datetime | None]:
    ours = _ours(list_keys(s3, bucket), database)
    if not ours:
        return None, None
    taken, key = ours[0]
    return key, taken


def prune(s3, bucket: str, database: str, *, keep: int) -> list[str]:
    doomed = to_prune(list(list_keys(s3, bucket)), database, keep=keep)
    for start in range(0, len(doomed), 1000):  # the S3 limit per request
        batch = doomed[start : start + 1000]
        s3.delete_objects(
            Bucket=bucket, Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True}
        )
    return doomed


# --- health --------------------------------------------------------------------


def enabled(env: Mapping[str, str]) -> bool:
    return env.get("BACKUP_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def healthy(env: Mapping[str, str], marker: Path, *, now: datetime) -> bool:
    """Healthy if the last good backup is under a day and a bit old -- or the
    service was switched off on purpose, which is the only way to deploy
    without backups and not have `deploy.sh` stop on an unhealthy container."""
    if not enabled(env):
        return True
    try:
        last = datetime.fromtimestamp(marker.stat().st_mtime, UTC)
    except FileNotFoundError:
        return False
    return now - last <= UNHEALTHY_AFTER


def _mark_success(at: datetime) -> None:
    MARKER.touch()
    stamp = at.timestamp()
    os.utime(MARKER, (stamp, stamp))


# --- the parts that touch the world ----------------------------------------------


def log(message: str) -> None:
    print(f"{datetime.now(VIETNAM):%Y-%m-%d %H:%M:%S} [backup] {message}", flush=True)


def s3_client(storage: Storage):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=storage.endpoint_url,
        aws_access_key_id=storage.access_key,
        aws_secret_access_key=storage.secret_key,
        region_name=signing_region(storage.endpoint_url),
        config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
    )


def ensure_bucket(s3, bucket: str) -> None:
    """Create the bucket if it is missing and the credentials may -- the dev
    storage, where a new bucket is private until given a policy. On B2 or R2
    the bucket is made by hand (the runbook), private, and a key scoped to it
    may not even be allowed to ask; then the upload is what reports a problem."""
    from botocore.exceptions import ClientError

    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchBucket", "NotFound"}:
            s3.create_bucket(Bucket=bucket)
            log(f"đã tạo bucket {bucket} (private)")


def _database(env: Mapping[str, str]) -> str:
    database = env.get("PGDATABASE", "")
    if not IDENTIFIER.fullmatch(database):
        raise ConfigError(f"PGDATABASE={database!r} không phải tên CSDL hợp lệ")
    return database


def _psql(sql: str, *, database: str = "postgres") -> str:
    out = subprocess.run(
        ["psql", "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-d", database, "-c", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_archive(path: Path) -> int:
    """Read the archive's table of contents back. A dump that pg_restore cannot
    list will not restore either, and this is the moment to find out -- not the
    night it is needed. Returns how many entries it holds."""
    listing = subprocess.run(
        ["pg_restore", "--list", str(path)], check=True, capture_output=True, text=True
    ).stdout
    if "alembic_version" not in listing:
        raise RuntimeError("bản dump không có bảng alembic_version -- không phải CSDL của DevPath?")
    return sum(1 for line in listing.splitlines() if line and not line.startswith(";"))


def run_backup(env: Mapping[str, str], storage: Storage, s3) -> str:
    database = _database(env)
    keep = int(env.get("BACKUP_KEEP") or 14)
    started = datetime.now(UTC)
    key = backup_key(database, started)

    with tempfile.TemporaryDirectory(prefix="devpath-backup-") as tmp:
        path = Path(tmp) / "db.dump"
        # Custom format: compressed, and pg_restore can pick it apart -- one
        # table back, or the whole database into a side copy.
        subprocess.run(["pg_dump", "--format=custom", "--file", str(path), database], check=True)
        entries = _check_archive(path)
        digest = _sha256(path)
        size = path.stat().st_size
        version = subprocess.run(
            ["pg_dump", "--version"], check=True, capture_output=True, text=True
        ).stdout.strip()
        s3.upload_file(
            str(path),
            storage.bucket,
            key,
            ExtraArgs={"Metadata": {"sha256": digest, "database": database, "pg-dump": version}},
        )

    _mark_success(started)
    pruned = prune(s3, storage.bucket, database, keep=keep)
    took = (datetime.now(UTC) - started).total_seconds()
    log(
        f"xong {key}: {size / 1_048_576:.1f} MB, {entries} mục, sha256 {digest[:12]}…, "
        f"{took:.1f} s; xóa {len(pruned)} bản cũ (giữ {keep})"
    )
    return key


TABLE_COUNTS = """
select table_name || '=' ||
       (xpath('/row/c/text()',
              query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name),
                           false, true, '')))[1]::text
from information_schema.tables
where table_schema = 'public' and table_type = 'BASE TABLE'
order by table_name
"""


def _table_counts(database: str) -> dict[str, int]:
    rows = _psql(TABLE_COUNTS, database=database).splitlines()
    return {name: int(count) for name, count in (row.split("=", 1) for row in rows if row)}


def restore(env: Mapping[str, str], storage: Storage, s3, which: str) -> str:
    """Restore a backup into a new side database and say how it compares with
    the live one. The live database is not touched: the site keeps serving
    while this runs, and `swap` is a separate, deliberate step."""
    database = _database(env)
    if which == "latest":
        key, _ = latest(s3, storage.bucket, database)
        if key is None:
            raise SystemExit(f"Bucket {storage.bucket} chưa có bản backup nào của {database}.")
    else:
        key = which
        if key_time(key, database) is None:
            raise SystemExit(f"{key!r} không phải tên một bản backup của {database}.")

    target = restore_target_name(database, datetime.now(UTC))
    with tempfile.TemporaryDirectory(prefix="devpath-restore-") as tmp:
        path = Path(tmp) / "db.dump"
        log(f"tải {key}")
        s3.download_file(storage.bucket, key, str(path))
        expected = s3.head_object(Bucket=storage.bucket, Key=key).get("Metadata", {}).get("sha256")
        actual = _sha256(path)
        if expected and expected != actual:
            raise SystemExit(f"sha256 không khớp: tải về {actual}, lúc tải lên {expected}.")
        _check_archive(path)

        log(f"khôi phục vào CSDL mới {target}")
        subprocess.run(["createdb", target], check=True)
        subprocess.run(
            [
                "pg_restore",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "--dbname",
                target,
                str(path),
            ],
            check=True,
        )

    version = _psql("select version_num from alembic_version", database=target)
    restored = _table_counts(target)
    live = _table_counts(database)
    log(
        f"{target}: {len(restored)} bảng, {sum(restored.values())} dòng, alembic {version}"
        f" (đang chạy: {len(live)} bảng, {sum(live.values())} dòng)"
    )
    for table in sorted(set(restored) | set(live)):
        if restored.get(table) != live.get(table):
            was, now = restored.get(table, "—"), live.get(table, "—")
            log(f"  {table}: bản backup {was}, đang chạy {now}")
    print(f"RESTORED={target}", flush=True)
    return target


def swap(env: Mapping[str, str], name: str) -> str:
    """Give the restored database the live one's name, and park the live one
    under another -- two renames, so going back is two renames as well."""
    database = _database(env)
    if not (IDENTIFIER.fullmatch(name) and name.startswith(f"{database}_restore_")):
        raise SystemExit(f"{name!r} không phải một CSDL do `restore` tạo.")
    if _psql(f"select count(*) from pg_database where datname = '{name}'") != "1":
        raise SystemExit(f"Không có CSDL {name}.")

    others = int(
        _psql(
            "select count(*) from pg_stat_activity "
            f"where datname in ('{database}', '{name}') and pid <> pg_backend_pid()"
        )
    )
    if others:
        raise SystemExit(
            f"Còn {others} kết nối vào {database}/{name}. Dừng backend, worker, beat, "
            "grading-worker trước -- infra/scripts/restore-db.sh làm việc này."
        )

    parked = parked_name(database, datetime.now(UTC))
    _psql(f'alter database "{database}" rename to "{parked}"')
    try:
        _psql(f'alter database "{name}" rename to "{database}"')
    except subprocess.CalledProcessError:
        _psql(f'alter database "{parked}" rename to "{database}"')
        raise
    log(f"{name} giờ là {database}; bản cũ giữ ở {parked} (xóa khi đã chắc: dropdb {parked})")
    return parked


def _sleep_until(due: datetime) -> None:
    while (remaining := (due - datetime.now(UTC)).total_seconds()) > 0:
        time.sleep(min(remaining, 300))


def _idle(reason: str) -> None:
    """Stay up and say why, rather than exit: a restart loop would only repeat
    the message, and the healthcheck already reports the state."""
    while True:
        log(reason)
        time.sleep(6 * 3600)


def serve(env: Mapping[str, str]) -> None:
    if not enabled(env):
        _idle("BACKUP_ENABLED=false -- không sao lưu (cố ý)")
    try:
        storage = storage_from_env(env)
        _database(env)
    except ConfigError as exc:
        _idle(f"không sao lưu được: {exc}")

    hour = int(env.get("BACKUP_HOUR") or 2)
    s3 = s3_client(storage)
    try:
        ensure_bucket(s3, storage.bucket)
        _, taken = latest(s3, storage.bucket, env["PGDATABASE"])
    except Exception as exc:  # the first run below reports the same problem, with a retry
        log(f"không đọc được bucket {storage.bucket}: {exc!r}")
        taken = None
    now = datetime.now(UTC)
    if taken is not None and not is_stale(taken, now, max_age=STALE_AFTER):
        _mark_success(taken)

    due = first_due(taken, now, hour_vn=hour)
    while True:
        log(f"lần chạy tới: {due.astimezone(VIETNAM):%Y-%m-%d %H:%M} giờ Việt Nam")
        _sleep_until(due)
        try:
            run_backup(env, storage, s3)
            due = next_run(datetime.now(UTC), hour_vn=hour)
        except Exception as exc:
            minutes = int(RETRY_AFTER.total_seconds() // 60)
            log(f"sao lưu lỗi: {exc!r} -- thử lại sau {minutes} phút")
            due = datetime.now(UTC) + RETRY_AFTER


def _list(env: Mapping[str, str], storage: Storage, s3) -> None:
    database = _database(env)
    now = datetime.now(UTC)
    sizes = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=storage.bucket, Prefix=PREFIX):
        for item in page.get("Contents", []):
            sizes[item["Key"]] = item["Size"]
    ours = _ours(sizes, database)
    if not ours:
        print(f"(chưa có bản backup nào của {database} trong {storage.bucket})")
    for taken, key in ours:
        age = now - taken
        print(
            f"{key}  {taken.astimezone(VIETNAM):%Y-%m-%d %H:%M} VN  "
            f"{sizes[key] / 1_048_576:7.1f} MB  {age.days} ngày {age.seconds // 3600} giờ trước"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devpath-backup", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    commands.add_parser("backup")
    commands.add_parser("list")
    commands.add_parser("health")
    restore_cmd = commands.add_parser("restore")
    restore_cmd.add_argument("which", help="tên bản backup, hoặc `latest`")
    swap_cmd = commands.add_parser("swap")
    swap_cmd.add_argument("name", help="CSDL do `restore` tạo")
    swap_cmd.add_argument("--yes", action="store_true", help="xác nhận thay CSDL đang chạy")
    args = parser.parse_args(argv)
    env = os.environ

    # `docker stop` sends SIGTERM to PID 1, which Python ignores by default;
    # without this every stop waits out the ten-second grace and gets killed.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    if args.command == "health":
        return 0 if healthy(env, MARKER, now=datetime.now(UTC)) else 1
    if args.command == "serve":
        serve(env)
        return 0
    if args.command == "swap":
        if not args.yes:
            raise SystemExit("swap thay CSDL đang chạy -- thêm --yes nếu đúng là muốn vậy.")
        swap(env, args.name)
        return 0

    try:
        storage = storage_from_env(env)
    except ConfigError as exc:
        raise SystemExit(f"Không biết lưu backup ở đâu: {exc}") from None
    s3 = s3_client(storage)
    if args.command == "backup":
        ensure_bucket(s3, storage.bucket)
        print(run_backup(env, storage, s3), flush=True)
    elif args.command == "list":
        _list(env, storage, s3)
    elif args.command == "restore":
        restore(env, storage, s3, args.which)
    return 0


if __name__ == "__main__":
    sys.exit(main())
