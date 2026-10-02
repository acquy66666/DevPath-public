"""The decisions the backup service makes on its own, at night, unwatched:
which object is a backup, which ones to delete, when to run next, where to
upload, and whether it is healthy. Talking to Postgres and S3 is proven by the
restore drill (docs/report/assets/phase-6/db-backup-restore.txt); these are the
parts a wrong answer from would go unnoticed until the day a backup is needed.

    python -m pytest infra/backup
"""

import os
from datetime import UTC, datetime, timedelta

import devpath_backup as b
import pytest


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


# --- object names --------------------------------------------------------------


def test_a_key_carries_the_database_and_the_utc_time_it_was_taken() -> None:
    key = b.backup_key("devpath", utc(2026, 10, 2, 19, 0, 5))
    assert key == "postgres/devpath-20261002T190005Z.dump"
    assert b.key_time(key, "devpath") == utc(2026, 10, 2, 19, 0, 5)


def test_a_naive_time_is_refused_rather_than_guessed() -> None:
    with pytest.raises(ValueError):
        b.backup_key("devpath", datetime(2026, 10, 2, 19, 0))


@pytest.mark.parametrize(
    "key",
    [
        "postgres/devpath-20261002T190005Z.dump.tmp",
        "media/devpath-20261002T190005Z.dump",
        "postgres/devpath-2026-10-02.dump",
        "postgres/other-20261002T190005Z.dump",
        "notes.txt",
    ],
)
def test_anything_this_service_did_not_name_is_not_a_backup(key: str) -> None:
    assert b.key_time(key, "devpath") is None


# --- retention -----------------------------------------------------------------


def keys_for(days: list[int]) -> list[str]:
    return [b.backup_key("devpath", utc(2026, 9, day, 19)) for day in days]


def test_the_newest_are_kept_whatever_order_the_listing_comes_in() -> None:
    keys = keys_for([3, 1, 5, 2, 4])
    assert sorted(b.to_prune(keys, "devpath", keep=3)) == sorted(keys_for([1, 2]))


def test_nothing_is_pruned_while_there_are_no_more_than_keep() -> None:
    assert b.to_prune(keys_for([1, 2, 3]), "devpath", keep=3) == []


def test_keep_below_one_is_refused() -> None:
    # Retention by count can never delete the newest backup -- unless the count
    # is zero, and a typo in .env.prod should not be able to say that.
    with pytest.raises(ValueError):
        b.to_prune(keys_for([1, 2]), "devpath", keep=0)


def test_another_database_and_foreign_objects_are_never_pruned() -> None:
    ours = keys_for([1, 2, 3])
    theirs = [b.backup_key("devpath_prodtest", utc(2026, 9, 1, 19)), "postgres/README.txt"]
    assert b.to_prune(ours + theirs, "devpath", keep=1) == keys_for([1, 2])


# --- schedule ------------------------------------------------------------------


def test_the_next_run_is_later_today_in_vietnam_when_the_hour_is_still_ahead() -> None:
    # 18:00 UTC is 01:00 in Vietnam; 02:00 Vietnam is 19:00 UTC the same day.
    assert b.next_run(utc(2026, 10, 2, 18, 0), hour_vn=2) == utc(2026, 10, 2, 19, 0)


def test_the_next_run_is_tomorrow_once_the_hour_has_passed() -> None:
    assert b.next_run(utc(2026, 10, 2, 19, 30), hour_vn=2) == utc(2026, 10, 3, 19, 0)


def test_the_next_run_is_strictly_after_now() -> None:
    # Woken exactly on the hour, a run has just happened; the next is a day on.
    assert b.next_run(utc(2026, 10, 2, 19, 0), hour_vn=2) == utc(2026, 10, 3, 19, 0)


def test_the_vietnam_day_boundary_is_handled() -> None:
    # 17:30 UTC is 00:30 on the 3rd in Vietnam, so 02:00 on the 3rd is ahead.
    assert b.next_run(utc(2026, 10, 2, 17, 30), hour_vn=2) == utc(2026, 10, 2, 19, 0)


@pytest.mark.parametrize("hour", [-1, 24])
def test_an_hour_outside_the_day_is_refused(hour: int) -> None:
    with pytest.raises(ValueError):
        b.next_run(utc(2026, 10, 2), hour_vn=hour)


def test_no_backup_at_all_is_stale() -> None:
    assert b.is_stale(None, utc(2026, 10, 2), max_age=timedelta(hours=24)) is True


def test_a_backup_from_last_night_is_not_stale() -> None:
    now = utc(2026, 10, 2, 12)
    assert b.is_stale(now - timedelta(hours=17), now, max_age=timedelta(hours=24)) is False


def test_a_missed_night_is_stale() -> None:
    now = utc(2026, 10, 2, 12)
    assert b.is_stale(now - timedelta(hours=25), now, max_age=timedelta(hours=24)) is True


def test_a_fresh_start_runs_at_once_when_the_last_backup_is_stale() -> None:
    now = utc(2026, 10, 2, 12)
    assert b.first_due(None, now, hour_vn=2) == now


def test_a_fresh_start_waits_for_the_hour_when_last_night_is_there() -> None:
    now = utc(2026, 10, 2, 12)
    assert b.first_due(now - timedelta(hours=17), now, hour_vn=2) == utc(2026, 10, 2, 19)


# --- where it goes -------------------------------------------------------------

R2 = {
    "R2_ACCOUNT_ID": "acc123",
    "R2_ACCESS_KEY_ID": "media-key",
    "R2_SECRET_ACCESS_KEY": "media-secret",
    "R2_BUCKET": "devpath-media",
}


def test_r2_credentials_are_used_for_the_backup_bucket() -> None:
    storage = b.storage_from_env({**R2, "ENV": "production"})
    assert storage == b.Storage(
        endpoint_url="https://acc123.r2.cloudflarestorage.com",
        access_key="media-key",
        secret_key="media-secret",
        bucket="devpath-backups",
    )


def test_an_explicit_endpoint_beats_the_account_id() -> None:
    env = {**R2, "R2_ENDPOINT_URL": "https://s3.example.com"}
    assert b.storage_from_env(env).endpoint_url == "https://s3.example.com"


def test_backup_credentials_of_their_own_take_precedence() -> None:
    env = {
        **R2,
        "BACKUP_ENDPOINT_URL": "https://backups.example.com",
        "BACKUP_ACCESS_KEY_ID": "backup-key",
        "BACKUP_SECRET_ACCESS_KEY": "backup-secret",
        "BACKUP_BUCKET": "offsite",
    }
    assert b.storage_from_env(env) == b.Storage(
        endpoint_url="https://backups.example.com",
        access_key="backup-key",
        secret_key="backup-secret",
        bucket="offsite",
    )


def test_development_falls_back_to_the_minio_of_the_dev_stack() -> None:
    storage = b.storage_from_env({"MINIO_ROOT_USER": "u", "MINIO_ROOT_PASSWORD": "p"})
    assert storage == b.Storage("http://minio:9000", "u", "p", "devpath-backups")


def test_production_without_storage_is_an_error_not_a_minio_that_is_not_there() -> None:
    with pytest.raises(b.ConfigError):
        b.storage_from_env({"ENV": "production"})


def test_the_public_media_bucket_is_refused() -> None:
    # The media bucket serves videos to anyone; a dump holds every email and
    # password hash on the platform.
    with pytest.raises(b.ConfigError):
        b.storage_from_env({**R2, "BACKUP_BUCKET": "devpath-media"})


# --- restore names -------------------------------------------------------------


def test_side_databases_are_valid_postgres_names_that_say_what_they_are() -> None:
    now = utc(2026, 10, 2, 19, 0, 5)
    restored = b.restore_target_name("devpath", now)
    parked = b.parked_name("devpath", now)
    assert restored == "devpath_restore_20261002t190005z"
    assert parked == "devpath_before_restore_20261002t190005z"
    for name in (restored, parked):
        assert len(name) <= 63
        assert b.IDENTIFIER.fullmatch(name)


# --- against a bucket ----------------------------------------------------------


class FakeS3:
    """The three calls the service makes to list and delete, and nothing else."""

    def __init__(self, keys: list[str], page_size: int = 2) -> None:
        self.keys = list(keys)
        self.page_size = page_size
        self.deleted: list[str] = []

    def get_paginator(self, name: str) -> "FakeS3":
        assert name == "list_objects_v2"
        return self

    def paginate(self, *, Bucket: str, Prefix: str):  # noqa: N803 -- boto3's spelling
        matching = [key for key in self.keys if key.startswith(Prefix)]
        for start in range(0, max(len(matching), 1), self.page_size):
            page = matching[start : start + self.page_size]
            yield {"Contents": [{"Key": key} for key in page]} if page else {}

    def delete_objects(self, *, Bucket: str, Delete: dict) -> dict:  # noqa: N803
        for item in Delete["Objects"]:
            self.deleted.append(item["Key"])
            self.keys.remove(item["Key"])
        return {}


def test_prune_deletes_exactly_what_retention_says_across_pages() -> None:
    s3 = FakeS3(keys_for([1, 2, 3, 4, 5]), page_size=2)
    assert b.prune(s3, "devpath-backups", "devpath", keep=2) == keys_for([1, 2, 3])
    assert sorted(s3.deleted) == sorted(keys_for([1, 2, 3]))
    assert sorted(s3.keys) == sorted(keys_for([4, 5]))


def test_latest_is_the_newest_backup_of_this_database() -> None:
    s3 = FakeS3([*keys_for([2, 9, 4]), b.backup_key("other", utc(2026, 9, 30, 19))])
    key, taken = b.latest(s3, "devpath-backups", "devpath")
    assert key == keys_for([9])[0]
    assert taken == utc(2026, 9, 9, 19)


def test_latest_of_an_empty_bucket_is_none() -> None:
    assert b.latest(FakeS3([]), "devpath-backups", "devpath") == (None, None)


# --- health --------------------------------------------------------------------


def test_healthy_when_the_last_success_is_recent(tmp_path) -> None:
    marker = tmp_path / "ok"
    marker.touch()
    assert b.healthy({}, marker, now=datetime.now(UTC)) is True


def test_unhealthy_when_the_last_success_is_older_than_a_day_and_a_bit(tmp_path) -> None:
    marker = tmp_path / "ok"
    marker.touch()
    old = (datetime.now(UTC) - timedelta(hours=27)).timestamp()
    os.utime(marker, (old, old))
    assert b.healthy({}, marker, now=datetime.now(UTC)) is False


def test_unhealthy_before_any_success(tmp_path) -> None:
    assert b.healthy({}, tmp_path / "missing", now=datetime.now(UTC)) is False


def test_switched_off_on_purpose_counts_as_healthy(tmp_path) -> None:
    # The one way to deploy without backups: saying so in .env.prod.
    env = {"BACKUP_ENABLED": "false"}
    assert b.healthy(env, tmp_path / "missing", now=datetime.now(UTC)) is True
