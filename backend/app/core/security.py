"""Password hashing.

bcrypt directly rather than passlib: passlib is unmaintained and breaks
against bcrypt 4.x. Phase 2 adds verification and JWT handling here.
"""

import bcrypt

# bcrypt hashes at most 72 bytes and silently ignores the rest, which would
# let two different long passwords open the same account.
MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    """Return a salted bcrypt hash. Raises ValueError if the password is too long."""
    encoded = plain.encode("utf-8")

    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password is {len(encoded)} bytes; bcrypt accepts at most "
            f"{MAX_PASSWORD_BYTES}."
        )

    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")
