import uuid
from datetime import timedelta

import bcrypt
import jwt
import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


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


# --- Password verification -------------------------------------------------


def test_correct_password_verifies() -> None:
    assert verify_password("correct horse", hash_password("correct horse"))


def test_wrong_password_does_not_pass_verification() -> None:
    assert not verify_password("battery staple", hash_password("correct horse"))


def test_over_long_password_fails_verification_instead_of_raising() -> None:
    """hash_password refuses >72 bytes, so no stored hash can match one.

    Raising here would turn a login attempt into a 500; the answer is simply
    "wrong password".
    """
    assert not verify_password("y" * 200, hash_password("y" * 72))


def test_malformed_stored_hash_fails_verification_instead_of_raising() -> None:
    """A corrupted or hand-edited row must not crash the login endpoint."""
    assert not verify_password("anything", "not-a-bcrypt-hash")


# --- Access tokens ---------------------------------------------------------


def test_access_token_round_trips_user_and_role() -> None:
    user_id = uuid.uuid4()

    payload = decode_access_token(create_access_token(user_id, "instructor"))

    assert payload.user_id == user_id
    assert payload.role == "instructor"


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token(uuid.uuid4(), "student", expires_in=timedelta(seconds=-1))

    with pytest.raises(TokenError):
        decode_access_token(token)


def test_token_signed_with_another_secret_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "admin", "exp": 9999999999},
        "another-secret-long-enough-to-not-warn-about",
        algorithm="HS256",
    )

    with pytest.raises(TokenError):
        decode_access_token(forged)


def test_token_without_a_signature_is_rejected() -> None:
    """The classic alg=none forgery."""
    forged = jwt.encode({"sub": str(uuid.uuid4()), "role": "admin"}, key="", algorithm="none")

    with pytest.raises(TokenError):
        decode_access_token(forged)


def test_garbage_string_is_rejected() -> None:
    with pytest.raises(TokenError):
        decode_access_token("clearly-not-a-jwt")


# --- Refresh tokens --------------------------------------------------------


def test_every_generated_refresh_token_is_unique() -> None:
    assert len({generate_refresh_token() for _ in range(100)}) == 100


def test_refresh_token_has_enough_entropy_to_be_unguessable() -> None:
    assert len(generate_refresh_token()) >= 32


def test_refresh_token_hash_is_deterministic_and_fits_the_column() -> None:
    """refresh_tokens.token_hash is VARCHAR(64) -- SHA-256 hex is exactly that."""
    raw = generate_refresh_token()

    assert hash_refresh_token(raw) == hash_refresh_token(raw)
    assert len(hash_refresh_token(raw)) == 64


def test_different_refresh_tokens_hash_differently() -> None:
    assert hash_refresh_token("token-a") != hash_refresh_token("token-b")
