"""The one place the rest of the codebase talks to a language model.

The plan requires it: "Mọi call LLM đi qua adapter -- đổi model/provider không
sửa business code." So the ingest job asks for embeddings and knows nothing
about Gemini, about HTTP, or about the fact that a free-tier key runs out of
quota on a bad afternoon.

Four things live here that a caller should never have to think about:

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

* **Streams that fail halfway.** Generation is streamed, and Gemini can
  answer 200, send part of an answer, and then end with a bare JSON error
  body instead of another SSE event (seen while choosing the model: `503
  UNAVAILABLE, "high demand"` after six pieces). Before the first piece that
  is retried like any other failure; after it, it is raised, because the
  student has already read text that a second attempt would not continue.

Everything that goes wrong leaves as a `DomainError`, so a router answers with
the project's error envelope and the worker can record which lesson failed
instead of dying on an `httpx` exception.
"""

import asyncio
import json
import logging
import math
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
from fastapi import status

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.models.rag import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

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

    async def embed_queries(self, texts: Sequence[str]) -> list[list[float]]: ...


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
        """Embed passages, in batches, preserving order."""
        return await self._embed_batched(texts, TASK_DOCUMENT)

    async def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed several questions in one call -- the chatbot searches a
        follow-up both alone and together with the question before it."""
        return await self._embed_batched(texts, TASK_QUERY)

    async def _embed_batched(
        self, texts: Sequence[str], task_type: str
    ) -> list[list[float]]:
        """`batchEmbedContents`, `batch_size` texts at a time, in order.

        Order is the only thing tying a vector back to the text it belongs
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
                        "taskType": task_type,
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

    async def count_tokens(self, text: str) -> int:
        """What `text` really costs in this model's tokens.

        Not on the ingest path -- one network call per chunk would be slower
        than the embedding it budgets for, which is why `chunking.py` estimates
        instead. This is how that estimate is checked.
        """
        data = await self._post("countTokens", {"contents": [{"parts": [{"text": text}]}]})
        return int(data["totalTokens"])


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


def get_embedder_factory() -> Callable[[], Embedder]:
    """FastAPI dependency: how a route gets an embedder, *when it needs one*.

    A factory rather than an embedder, because building one fails without a
    key -- and a dependency that failed would answer 503 to a caller who is
    not even signed in. The service calls it after its own checks. Tests
    override this with one that returns a fake.
    """
    return build_embedder


# --- Generation -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """One turn of a conversation, in Gemini's own role names."""

    role: Literal["user", "model"]
    text: str


class ChatModel(Protocol):
    """What the chat service depends on: a system prompt and turns in, text out."""

    @property
    def model(self) -> str:
        """Which model wrote the answer, for the evidence and the logs."""

    def stream(self, *, system: str, turns: Sequence[ChatTurn]) -> AsyncIterator[str]:
        """The answer, piece by piece, as the model produces it."""
        ...


class _StreamFailed(Exception):
    """A 200 response that did not carry a usable answer."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def _pieces_of(event: dict[str, Any], state: dict[str, str | None]) -> list[str]:
    """The answer text in one SSE event, noting why it stopped if it says."""
    feedback = event.get("promptFeedback") or {}
    state["blocked"] = feedback.get("blockReason") or state["blocked"]

    pieces = []
    for candidate in event.get("candidates") or []:
        state["finish"] = candidate.get("finishReason") or state["finish"]
        for part in (candidate.get("content") or {}).get("parts") or []:
            # Thought summaries only arrive if asked for; skipped anyway,
            # because they are the model talking to itself.
            if part.get("text") and not part.get("thought"):
                pieces.append(part["text"])
    return pieces


def _stream_error(lines: list[str]) -> _StreamFailed:
    """What a non-SSE tail of a 200 response was trying to say."""
    raw = "\n".join(lines)
    try:
        error = json.loads(raw).get("error") or {}
        code = int(error.get("code") or 0)
        detail = f"HTTP {code} {error.get('status', '')}: {str(error.get('message', ''))[:200]}"
    except (ValueError, AttributeError):
        code, detail = 0, f"phản hồi lạ: {raw[:200]}"
    return _StreamFailed(detail, retryable=code in RETRYABLE_STATUS)


async def _answer_pieces(response: httpx.Response) -> AsyncIterator[str]:
    """The text inside one `streamGenerateContent?alt=sse` response.

    Reads SSE properly -- `data:` lines up to a blank line make one event --
    and keeps every line that is *not* SSE, because that is the shape an error
    takes once the status code has already gone out as 200.
    """
    data: list[str] = []
    stray: list[str] = []
    state: dict[str, str | None] = {"finish": None, "blocked": None}
    produced = False

    def flush() -> list[str]:
        nonlocal data
        pieces = _pieces_of(json.loads("\n".join(data)), state) if data else []
        data = []
        return pieces

    async for line in response.aiter_lines():
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
            continue
        if line.strip():
            if not line.startswith(":"):  # ":" opens an SSE comment
                stray.append(line)
            continue
        for piece in flush():
            produced = True
            yield piece

    for piece in flush():
        produced = True
        yield piece

    if stray:
        raise _stream_error(stray)
    if not produced:
        # A blocked prompt, or a candidate that finished with nothing in it.
        # Not retried: the same prompt would be blocked the same way.
        raise _StreamFailed(
            "mô hình không trả về nội dung "
            f"(blockReason={state['blocked']}, finishReason={state['finish']})",
            retryable=False,
        )
    if state["finish"] == "MAX_TOKENS":
        logger.warning("Câu trả lời bị cắt vì chạm maxOutputTokens")


class GeminiChat:
    """Gemini's streaming generation endpoint, with the retries."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_s: float,
        max_attempts: int,
        max_output_tokens: int,
        thinking_level: str,
        retry_base_delay_s: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_attempts = max(1, max_attempts)
        self._max_output_tokens = max_output_tokens
        self._thinking_level = thinking_level
        self._retry_base_delay_s = retry_base_delay_s
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    def _payload(self, system: str, turns: Sequence[ChatTurn]) -> dict[str, Any]:
        config: dict[str, Any] = {"maxOutputTokens": self._max_output_tokens}
        if self._thinking_level:
            # Thinking is paid out of maxOutputTokens. Left to the model's
            # default, a 200-token limit bought 188 tokens of thinking and an
            # eight-token answer -- so the level is always stated.
            config["thinkingConfig"] = {"thinkingLevel": self._thinking_level}
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": turn.role, "parts": [{"text": turn.text}]} for turn in turns
            ],
            "generationConfig": config,
        }

    async def stream(
        self, *, system: str, turns: Sequence[ChatTurn]
    ) -> AsyncIterator[str]:
        url = f"{self._base_url}/models/{self._model}:streamGenerateContent"
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        payload = self._payload(system, turns)
        last = ""

        async with httpx.AsyncClient(
            timeout=self._timeout_s, transport=self._transport
        ) as client:
            for attempt in range(self._max_attempts):
                produced = False
                retryable = True
                try:
                    async with client.stream(
                        "POST", url, params={"alt": "sse"}, json=payload, headers=headers
                    ) as response:
                        if response.status_code == 200:
                            async for piece in _answer_pieces(response):
                                produced = True
                                yield piece
                            return

                        body = (await response.aread()).decode("utf-8", "replace")
                        last = f"HTTP {response.status_code}: {body[:200]}"
                        retryable = response.status_code in RETRYABLE_STATUS
                except _StreamFailed as error:
                    if produced:
                        raise LLMUnavailableError(
                            f"Gemini ngắt giữa câu trả lời ({error})"
                        ) from error
                    last, retryable = str(error), error.retryable
                except httpx.HTTPError as error:
                    if produced:
                        raise LLMUnavailableError(
                            "Mất kết nối giữa câu trả lời "
                            f"({type(error).__name__}: {error})"
                        ) from error
                    last = f"{type(error).__name__}: {error}"

                if not retryable:
                    break
                if attempt + 1 < self._max_attempts and self._retry_base_delay_s:
                    await asyncio.sleep(self._retry_base_delay_s * (2**attempt))

        raise LLMUnavailableError(f"Gọi Gemini thất bại ({last})")


def build_chat_model(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> ChatModel:
    """The configured generation model, or a stated refusal."""
    settings = get_settings()
    key = settings.gemini_api_key if api_key is None else api_key

    if not key:
        raise LLMNotConfiguredError(
            "Chưa cấu hình GEMINI_API_KEY nên trợ giảng AI chưa hoạt động",
        )

    return GeminiChat(
        api_key=key,
        model=model or settings.gemini_chat_model,
        base_url=settings.gemini_base_url,
        timeout_s=settings.gemini_timeout_s,
        max_attempts=settings.gemini_max_attempts,
        max_output_tokens=settings.gemini_chat_max_output_tokens,
        thinking_level=settings.gemini_chat_thinking_level,
    )


class JsonModel(Protocol):
    """What the quiz generator depends on: one prompt in, one JSON document out."""

    @property
    def model(self) -> str:
        """Which model drafted the document, for the evidence and the logs."""

    async def generate(self, *, system: str, prompt: str, schema: dict[str, Any]) -> Any:
        """The model's answer, parsed, in the shape `schema` asks for."""
        ...


class _NotRetryable(Exception):
    """A 200 whose content no second call would improve."""


class GeminiJson:
    """Gemini's `generateContent` in JSON mode, with the retries.

    Not streamed: a half-written JSON document is of no use to anybody, and the
    person waiting is an instructor who pressed a button, not a student reading
    along. The schema goes to Gemini as `responseSchema`, which constrains the
    shape; whether the *content* makes sense -- an answer key pointing past the
    options, two identical options -- is for the caller to check.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_s: float,
        max_attempts: int,
        max_output_tokens: int,
        thinking_level: str,
        retry_base_delay_s: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_attempts = max(1, max_attempts)
        self._max_output_tokens = max_output_tokens
        self._thinking_level = thinking_level
        self._retry_base_delay_s = retry_base_delay_s
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    def _payload(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        config: dict[str, Any] = {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "maxOutputTokens": self._max_output_tokens,
        }
        if self._thinking_level:
            config["thinkingConfig"] = {"thinkingLevel": self._thinking_level}
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": config,
        }

    @staticmethod
    def _document(data: dict[str, Any]) -> Any:
        """The JSON inside one response, or why there is none.

        Raises `_NotRetryable` for the answers the same prompt would get again
        -- blocked, empty, cut off -- and ValueError for text that is not JSON,
        which sampling makes unlikely to recur.
        """
        blocked = (data.get("promptFeedback") or {}).get("blockReason")
        candidates = data.get("candidates") or []
        if blocked or not candidates:
            raise _NotRetryable(f"mô hình không trả về nội dung (blockReason={blocked})")

        candidate = candidates[0]
        finish = candidate.get("finishReason")
        if finish == "MAX_TOKENS":
            # Half a JSON document. The same limit cuts the same prompt in the
            # same place, so the fix is a larger limit or a smaller request.
            raise _NotRetryable("câu trả lời bị cắt vì chạm maxOutputTokens")

        text = "".join(
            part.get("text", "")
            for part in (candidate.get("content") or {}).get("parts") or []
            if not part.get("thought")
        )
        if not text.strip():
            raise _NotRetryable(f"mô hình trả về rỗng (finishReason={finish})")
        return json.loads(text)

    async def generate(self, *, system: str, prompt: str, schema: dict[str, Any]) -> Any:
        url = f"{self._base_url}/models/{self._model}:generateContent"
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        payload = self._payload(system, prompt, schema)
        last = ""

        async with httpx.AsyncClient(
            timeout=self._timeout_s, transport=self._transport
        ) as client:
            for attempt in range(self._max_attempts):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except httpx.HTTPError as error:
                    last = f"{type(error).__name__}: {error}"
                else:
                    if response.status_code == 200:
                        try:
                            return self._document(response.json())
                        except _NotRetryable as error:
                            raise LLMUnavailableError(f"Gemini: {error}") from error
                        except ValueError as error:
                            last = f"không phải JSON hợp lệ ({error})"
                    else:
                        last = f"HTTP {response.status_code}: {response.text[:200]}"
                        if response.status_code not in RETRYABLE_STATUS:
                            break

                if attempt + 1 < self._max_attempts and self._retry_base_delay_s:
                    await asyncio.sleep(self._retry_base_delay_s * (2**attempt))

        raise LLMUnavailableError(f"Gọi Gemini thất bại ({last})")


def build_quiz_model(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> JsonModel:
    """The model that drafts quiz questions, or a stated refusal."""
    settings = get_settings()
    key = settings.gemini_api_key if api_key is None else api_key

    if not key:
        raise LLMNotConfiguredError(
            "Chưa cấu hình GEMINI_API_KEY nên chưa sinh được câu hỏi bằng AI",
        )

    return GeminiJson(
        api_key=key,
        model=model or settings.gemini_quiz_model,
        base_url=settings.gemini_base_url,
        timeout_s=settings.gemini_timeout_s,
        max_attempts=settings.gemini_max_attempts,
        max_output_tokens=settings.gemini_quiz_max_output_tokens,
        thinking_level=settings.gemini_quiz_thinking_level,
    )


def get_quiz_model_factory() -> Callable[[], JsonModel]:
    """FastAPI dependency, a factory for the same reason as the embedder's."""
    return build_quiz_model


def get_chat_model_factory() -> Callable[[], ChatModel]:
    """FastAPI dependency, a factory for the same reason as the embedder's."""
    return build_chat_model
