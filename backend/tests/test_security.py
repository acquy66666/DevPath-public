import bcrypt

from app.core.security import hash_password


def test_hash_is_verifiable_by_bcrypt() -> None:
    hashed = hash_password("mật khẩu tiếng Việt")

    assert bcrypt.checkpw("mật khẩu tiếng Việt".encode(), hashed.encode())


def test_wrong_password_does_not_verify() -> None:
    hashed = hash_password("correct horse")

    assert not bcrypt.checkpw(b"battery staple", hashed.encode())


def test_same_password_hashes_differently_each_time() -> None:
    """Per-hash salt: two users with the same password must not look alike."""
    assert hash_password("repeated") != hash_password("repeated")


def test_hash_fits_the_column() -> None:
    """users.password_hash is VARCHAR(255)."""
    assert len(hash_password("x" * 72)) <= 255


def test_long_passwords_are_rejected_rather_than_silently_truncated() -> None:
    """bcrypt ignores everything past 72 bytes.

    Truncating instead of failing would mean two different long passwords
    unlocking the same account.
    """
    try:
        hash_password("y" * 200)
    except ValueError:
        return
    raise AssertionError("expected ValueError for an over-long password")
