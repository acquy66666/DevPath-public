"""The one place the rest of the codebase talks to a language model.

The plan requires it: "Mọi call LLM đi qua adapter -- đổi model/provider không
sửa business code." So the ingest job asks for embeddings and knows nothing
about Gemini, about HTTP, or about the fact that a free-tier key runs out of
quota on a bad afternoon.

Three things live here that a caller should never have to think about:

* **Normalisation.** At 768 dimensions `gemini-embedding-001` returns a
  *truncation* of its native 3072-wide vector, and truncated vectors are not
  unit length -- measured norm 0.57. Cosine distance would paper over it, but
  every hand-checked number in the evidence files would be wrong, and a later
  switch to inner product would be silently wrong instead of loudly.

* **Asymmetry.** The same model gives a different vector for a passage than
  for a question about that passage (measured cosine between the two: 0.893).
  Using the wrong `taskType` on either side costs retrieval quality and shows
  up as nothing more specific than "the chatbot is a bit bad".

* **Quota.** 429 is the expected failure here, not the exceptional one, and it
  is the kind that goes away on its own. It is retried with a backoff; a 400
  is not, because a malformed request will still be malformed the third time
  and the quota it burns is the thing the 429 was asking us to conserve.

Everything that goes wrong leaves as a `DomainError`, so a router answers with
the project's error envelope and the worker can record which lesson failed
instead of dying on an `httpx` exception.
"""

import asyncio
import math
from collections.abc import Sequence
from typing import Any, Protocol

import httpx
from fastapi import status

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.models.rag import EMBEDDING_DIMENSIONS

#: Gemini's own names for the two sides of a retrieval pair.
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"

#: Retried: the server is busy, out of quota, or briefly broken.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class LLMError(DomainError):
    """Anything that stops an LLM call from producing a usable answer."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "LLM_UNAVAILABLE"


class LLMNotConfiguredError(LLMError):
    """No API key. Fixed by pasting one into `infra/.env`, not by waiting --
    which is why it is a different code from the one below."""

    code = "LLM_NOT_CONFIGURED"


class LLMUnavailableError(LLMError):
    """The call was made and did not come back usable."""

    code = "LLM_UNAVAILABLE"


class Embedder(Protocol):
    """What the ingest job and the retrieval step actually depend on."""

    @property
    def model(self) -> str:
        """Recorded per row in `doc_chunks.embedding_model`."""

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


def _normalise(values: list[float], *, model: str) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if len(values) != EMBEDDING_DIMENSIONS:
        raise LLMUnavailableError(
            f"Model {model} trả về vector {len(values)} chiều, "
            f"cần {EMBEDDING_DIMENSIONS} chiều"
        )
    if norm == 0:
        # Storing it would put a row in the index that is equally close to
        # every question ever asked.
        raise LLMUnavailableError(f"Model {model} trả về vector rỗng (norm = 0)")
    return [value / norm for value in values]


class GeminiEmbedder:
    """Gemini's embedding endpoints, with the retries and the arithmetic."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_s: float,
        max_attempts: int,
        batch_size: int,
        retry_base_delay_s: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_attempts = max(1, max_attempts)
        self._batch_size = max(1, batch_size)
        self._retry_base_delay_s = retry_base_delay_s
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/models/{self._model}:{method}"
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        last: str = ""

        async with httpx.AsyncClient(
            timeout=self._timeout_s, transport=self._transport
        ) as client:
            for attempt in range(self._max_attempts):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except httpx.HTTPError as error:
                    # A timeout or a dropped connection: worth another go, and
                    # indistinguishable from the server being busy.
                    last = f"{type(error).__name__}: {error}"
                else:
                    if response.status_code == 200:
                        return response.json()

                    last = f"HTTP {response.status_code}: {response.text[:200]}"
                    if response.status_code not in RETRYABLE_STATUS:
                        break

                if attempt + 1 < self._max_attempts and self._retry_base_delay_s:
                    await asyncio.sleep(self._retry_base_delay_s * (2**attempt))

        raise LLMUnavailableError(f"Gọi Gemini thất bại ({last})")

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed passages, in batches, preserving order.

        Order is the only thing tying a vector back to the chunk it belongs
        to -- nothing in the response identifies the input it came from.
        """
        vectors: list[list[float]] = []

        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            payload = {
                "requests": [
                    {
                        "model": f"models/{self._model}",
                        "content": {"parts": [{"text": text}]},
                        "taskType": TASK_DOCUMENT,
                        "outputDimensionality": EMBEDDING_DIMENSIONS,
                    }
                    for text in batch
                ]
            }
            data = await self._post("batchEmbedContents", payload)
            returned = data.get("embeddings", [])
            if len(returned) != len(batch):
                raise LLMUnavailableError(
                    f"Gửi {len(batch)} đoạn, nhận về {len(returned)} vector"
                )
            vectors.extend(
                _normalise(item["values"], model=self._model) for item in returned
            )

        return vectors

    async def embed_query(self, text: str) -> list[float]:
        data = await self._post(
            "embedContent",
            {
                "content": {"parts": [{"text": text}]},
                "taskType": TASK_QUERY,
                "outputDimensionality": EMBEDDING_DIMENSIONS,
            },
        )
        return _normalise(data["embedding"]["values"], model=self._model)


def build_embedder(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> Embedder:
    """The configured embedder, or a stated refusal.

    Arguments exist for the tests and for the one-off scripts; everything in
    the application passes nothing and gets what `infra/.env` says.
    """
    settings = get_settings()
    key = settings.gemini_api_key if api_key is None else api_key

    if not key:
        raise LLMNotConfiguredError(
            "Chưa cấu hình GEMINI_API_KEY nên không tạo được embedding",
        )

    return GeminiEmbedder(
        api_key=key,
        model=model or settings.gemini_embedding_model,
        base_url=settings.gemini_base_url,
        timeout_s=settings.gemini_timeout_s,
        max_attempts=settings.gemini_max_attempts,
        batch_size=settings.gemini_embedding_batch_size,
    )
