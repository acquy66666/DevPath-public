"""Course titles to URL slugs.

Vietnamese-aware on purpose: NFD normalisation strips the tone marks, but it
leaves "đ" alone -- that letter is not a "d" with a combining mark, it is its
own character -- so it is replaced before normalising. Without that step
"Lập trình" slugs to "lp-trnh".
"""

import re
import secrets
import unicodedata

# courses.slug is VARCHAR(220).
SLUG_MAX_LENGTH = 220

# Long enough that two courses created in the same second do not collide,
# short enough to keep the URL readable.
SUFFIX_LENGTH = 6
SUFFIX_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"

# A title made entirely of punctuation still needs a URL.
FALLBACK_SLUG = "khoa-hoc"

_STROKED_D = {"đ": "d", "Đ": "D"}


def slugify(text: str) -> str:
    """Lowercase, unaccented, hyphen-separated. Never empty."""
    for stroked, plain in _STROKED_D.items():
        text = text.replace(stroked, plain)

    # NFD splits an accented letter into letter + combining mark; Mn is the
    # category of those marks, and dropping them leaves the bare letter.
    decomposed = unicodedata.normalize("NFD", text)
    unaccented = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")

    slug = re.sub(r"[^a-z0-9]+", "-", unaccented.lower()).strip("-")
    return slug or FALLBACK_SLUG


def unique_slug(title: str) -> str:
    """A slug with a short random suffix, so titles may repeat and URLs may not.

    A counter (`-2`, `-3`) would need a query to find the next free number, and
    two requests racing would still pick the same one; random suffixes settle
    that with the unique index and no round trip.
    """
    suffix = "".join(secrets.choice(SUFFIX_ALPHABET) for _ in range(SUFFIX_LENGTH))
    base = slugify(title)[: SLUG_MAX_LENGTH - SUFFIX_LENGTH - 1].strip("-")
    return f"{base or FALLBACK_SLUG}-{suffix}"
