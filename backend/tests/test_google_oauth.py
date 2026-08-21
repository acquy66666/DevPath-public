"""The parts of the Google adapter that do not need the network."""

from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import Settings
from app.services.google_oauth import (
    AUTHORIZATION_ENDPOINT,
    GoogleAuthError,
    GoogleOAuth,
    identity_from_claims,
)

CLAIMS = {
    "sub": "1234567890",
    "email": "someone@gmail.com",
    "email_verified": True,
    "name": "Some One",
    "picture": "https://lh3.googleusercontent.com/a",
}


def settings() -> Settings:
    return Settings(
        google_client_id="client-id.apps.googleusercontent.com",
        google_client_secret="client-secret",
        google_redirect_uri="http://localhost:8000/api/v1/auth/google/callback",
    )


# --- Reading the id_token payload ------------------------------------------


def test_claims_become_an_identity() -> None:
    identity = identity_from_claims(CLAIMS)

    assert identity.sub == "1234567890"
    assert identity.email == "someone@gmail.com"
    assert identity.email_verified is True
    assert identity.full_name == "Some One"


@pytest.mark.parametrize("missing", ["sub", "email"])
def test_claims_without_an_identifier_are_rejected(missing: str) -> None:
    claims = {key: value for key, value in CLAIMS.items() if key != missing}

    with pytest.raises(GoogleAuthError):
        identity_from_claims(claims)


def test_a_missing_email_verified_claim_means_unverified() -> None:
    """This flag decides whether Google may take over an existing account.

    Anything other than a literal true has to read as false, or the check is
    only as strong as Google's least careful response.
    """
    claims = {key: value for key, value in CLAIMS.items() if key != "email_verified"}

    assert identity_from_claims(claims).email_verified is False


@pytest.mark.parametrize("value", ["true", "1", 1, "yes", None])
def test_a_truthy_but_not_true_email_verified_claim_means_unverified(value: object) -> None:
    assert identity_from_claims({**CLAIMS, "email_verified": value}).email_verified is False


def test_an_account_without_a_name_or_picture_is_fine() -> None:
    identity = identity_from_claims({"sub": "s", "email": "a@b.com", "name": ""})

    assert identity.full_name is None
    assert identity.picture is None


# --- Building the authorization URL ----------------------------------------


def test_authorization_url_carries_everything_google_needs() -> None:
    url = GoogleOAuth(settings()).authorization_url(state="the-state")
    query = parse_qs(urlparse(url).query)

    assert url.startswith(AUTHORIZATION_ENDPOINT)
    assert query["client_id"] == ["client-id.apps.googleusercontent.com"]
    assert query["response_type"] == ["code"]
    assert query["state"] == ["the-state"]
    assert query["redirect_uri"] == [
        "http://localhost:8000/api/v1/auth/google/callback"
    ]


def test_authorization_url_asks_for_the_identity_scopes() -> None:
    url = GoogleOAuth(settings()).authorization_url(state="s")
    scopes = parse_qs(urlparse(url).query)["scope"][0].split()

    assert set(scopes) == {"openid", "email", "profile"}


def test_authorization_url_shows_the_account_chooser() -> None:
    """Otherwise a shared browser signs the previous person straight back in."""
    url = GoogleOAuth(settings()).authorization_url(state="s")

    assert parse_qs(urlparse(url).query)["prompt"] == ["select_account"]
