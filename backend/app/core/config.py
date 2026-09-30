import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Fine for development, refused in production by the validator below.
DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    """Application configuration, read from environment or backend/.env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DevPath API"
    env: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://devpath:devpath@localhost:5432/devpath"
    redis_url: str = "redis://localhost:6379/0"

    # Auth. Short access token because it cannot be revoked; long refresh token
    # because it can (rotation + revocation live in refresh_tokens).
    jwt_secret: str = DEV_JWT_SECRET
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    refresh_cookie_name: str = "devpath_refresh"

    # Google OAuth. Empty until someone registers an OAuth client in Google
    # Cloud Console; `google_oauth_enabled` is what the routes check.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Cloudflare R2 (S3-compatible). Empty until someone creates a bucket and
    # an API token; `storage_enabled` is what the upload routes check.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "devpath-media"
    # Override for anything else that speaks S3 -- a local MinIO while
    # developing, or a self-hosted bucket later. Empty means "derive the R2
    # endpoint from the account id", which is the normal case.
    r2_endpoint_url: str = ""
    # Where the browser reads finished files from: the bucket's r2.dev
    # subdomain in development, a custom domain once there is one. Kept
    # separate from the S3 endpoint, which is for signing, not for playback.
    r2_public_base_url: str = ""
    # How long a signed upload URL stays valid. Long enough for a slow upload
    # of a lecture video, short enough that a leaked URL stops working.
    upload_url_ttl_seconds: int = 3600

    # How often one student may ask for grading. The cooldown stops a
    # double-clicked button and a script hammering one exercise; the hourly
    # quota stops a patient script that waits the cooldown out. Both protect
    # the queue -- one submission is several containers and several seconds --
    # and both are far above what iterating on an exercise looks like.
    submission_cooldown_seconds: int = 10
    submission_hourly_limit: int = 40

    # Gemini. Empty until somebody creates a key in Google AI Studio;
    # `gemini_enabled` is what the ingest job and the chat routes check, and
    # everything they do degrades to a stated "chưa cấu hình" rather than a
    # stack trace when it is off.
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    # Chosen on measurements, not on the version number -- `gemini-embedding-2`
    # exists and was tried. This is the model whose 768-wide truncation
    # `doc_chunks.embedding` was sized for, and the one that still gives a
    # different vector for a passage than for a question about it. See
    # docs/report/assets/phase-4/embedding-model.txt.
    gemini_embedding_model: str = "gemini-embedding-001"
    # How many chunks go into one `batchEmbedContents` call. A lesson is
    # usually fewer than this, so most lessons cost one round trip.
    gemini_embedding_batch_size: int = 50
    gemini_timeout_s: float = 60.0
    # Attempts, not retries: 3 means the original call plus two more. Quota
    # limits on the free tier are the expected failure, and they are the kind
    # that goes away on its own.
    gemini_max_attempts: int = 3
    # The model that writes the chatbot's answers. Chosen on measurements --
    # see docs/report/assets/phase-4/chat-api.txt for the candidates tried.
    gemini_chat_model: str = "gemini-3.5-flash-lite"
    # Gemini 3 models think before answering, and the thinking is paid out of
    # the output budget. Empty leaves the field out, for 2.5 models, which
    # take a budget instead and reject a level.
    gemini_chat_thinking_level: str = "minimal"
    gemini_chat_max_output_tokens: int = 2048
    # The model that drafts quiz questions -- the same as the chat model, and
    # chosen separately, on measurements (docs/report/assets/phase-4/
    # quiz-generation.txt). A first probe with a bare prompt had flash-lite turn
    # the lesson's `int(12.9)` into `int("12.9")` and key it as 12; with the
    # rule "copy the code exactly" in the prompt it got that right 5 runs of 5,
    # and 30 of 30 answer keys across six lessons. flash, on the same 30, wrote
    # one wrong key, took 11.5 s instead of 3.0 s, and ran out of free-tier
    # quota first. Neither is trusted blind: every draft is reviewed.
    gemini_quiz_model: str = "gemini-3.5-flash-lite"
    gemini_quiz_thinking_level: str = "minimal"
    # Five questions measured at ~600 output tokens. The limit is far above
    # that because a cut-off JSON document is worth nothing, not half.
    gemini_quiz_max_output_tokens: int = 8192

    # The course assistant. `chat_top_k` passages are read per question (about
    # 500 tokens each), and the last `chat_history_messages` messages of the
    # conversation go along with it -- enough for "giải thích thêm" to know
    # what it refers to, bounded so a long session does not grow the prompt
    # without end.
    chat_top_k: int = 6
    chat_history_messages: int = 6
    # Every question costs an embedding and a generation on a quota the plan
    # names as a risk. The cooldown stops a double-sent message, the hourly
    # limit a script; both are far above a student reading answers.
    chat_cooldown_seconds: int = 3
    chat_hourly_limit: int = 60
    # Drafting quiz questions: one call of ~10 s on the larger model. The
    # cooldown absorbs a double click; twenty an hour is several quizzes' worth
    # of drafts, reviewed properly.
    quiz_generation_cooldown_seconds: int = 10
    quiz_generation_hourly_limit: int = 20

    # VNPay. Empty until somebody registers a merchant account at
    # sandbox.vnpayment.vn; `vnpay_enabled` is what the payment route checks,
    # and it answers a stated "chưa cấu hình" rather than building a URL that
    # the gateway would refuse for a reason nobody can see.
    vnpay_tmn_code: str = ""
    vnpay_hash_secret: str = ""
    vnpay_payment_url: str = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    # Where VNPay sends the *browser* back: a page, not an API route. What the
    # browser carries is for the person to read; the money is decided by the
    # IPN, which VNPay sends to the backend directly and which is configured in
    # the merchant portal rather than here.
    vnpay_return_url: str = "http://localhost:3000/thanh-toan/ket-qua"
    # How long a payment URL stays payable. Long enough to find a card, short
    # enough that an old link cannot be paid next month at last month's price.
    vnpay_expire_minutes: int = 15

    # Where the browser lands after the OAuth round trip.
    frontend_url: str = "http://localhost:3000"

    # NoDecode: without it pydantic-settings JSON-decodes list fields straight
    # from the environment and raises before the validator below ever runs.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        """Accept a comma-separated string so .env stays readable."""
        if not isinstance(value, str):
            return value

        # A JSON array is what pydantic-settings would have produced on its own;
        # keep honouring it so either spelling works in .env.
        if value.lstrip().startswith("["):
            return json.loads(value)

        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @model_validator(mode="after")
    def reject_the_dev_secret_in_production(self) -> "Settings":
        """A shipped default signing key would let anyone mint admin tokens."""
        if self.env == "production" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set to a real secret when ENV=production")
        return self

    @property
    def google_oauth_enabled(self) -> bool:
        """Both halves or neither -- a client id without its secret cannot sign in."""
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def gemini_enabled(self) -> bool:
        """A key and nothing else -- the model names all have defaults."""
        return bool(self.gemini_api_key)

    @property
    def storage_enabled(self) -> bool:
        """Somewhere to talk to, and a key pair to talk with. All or nothing --
        an account id without keys cannot sign anything."""
        return bool(
            (self.r2_account_id or self.r2_endpoint_url)
            and self.r2_access_key_id
            and self.r2_secret_access_key
        )

    @property
    def storage_endpoint_url(self) -> str:
        """The S3 API endpoint: the override if there is one, otherwise the
        one R2 derives from the account id."""
        return (
            self.r2_endpoint_url
            or f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        )

    @property
    def vnpay_enabled(self) -> bool:
        """A merchant code and its secret. One without the other signs nothing."""
        return bool(self.vnpay_tmn_code and self.vnpay_hash_secret)

    @property
    def cookie_secure(self) -> bool:
        """Refresh cookie is HTTPS-only everywhere except local development."""
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once per process."""
    return Settings()
