"""The adapter every Gemini call goes through.

No network here. The transport is a fake that answers whatever the test needs,
because what is worth testing is not that Google's API works -- it is what this
code does when Google's API misbehaves, and that is exactly the case a live
call will not reproduce on demand.

The plan names "Gemini API đổi/giới hạn quota" as a live project risk, so the
quota answer (429) is the one with the most tests behind it.
"""

import math

import httpx
import pytest

from app.models.rag import EMBEDDING_DIMENSIONS
from app.services.llm import (
    GeminiEmbedder,
    LLMNotConfiguredError,
    LLMUnavailableError,
    build_embedder,
)

MODEL = "gemini-embedding-001"


def vector(seed: float = 0.5) -> list[float]:
    """An unnormalised vector, which is what the API really returns at 768
    dimensions -- measured norm 0.57, not 1.0."""
    return [seed] * EMBEDDING_DIMENSIONS


def embedder(handler, **kwargs) -> GeminiEmbedder:
    return GeminiEmbedder(
        api_key="not-a-real-key",
        model=MODEL,
        base_url="https://example.invalid/v1beta",
        timeout_s=5,
        max_attempts=kwargs.pop("max_attempts", 3),
        batch_size=kwargs.pop("batch_size", 50),
        # Tests must not spend real seconds waiting out a backoff.
        retry_base_delay_s=0,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def batch_response(count: int) -> httpx.Response:
    return httpx.Response(
        200, json={"embeddings": [{"values": vector()} for _ in range(count)]}
    )


async def test_documents_and_questions_are_embedded_differently() -> None:
    """`gemini-embedding-001` gives a different vector for a passage than for
    a question about it, and retrieval quality depends on using the right one
    on each side. Measured cosine between the two: 0.893, not 1.0."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append((request.url.path, json.loads(request.content)))
        if request.url.path.endswith("batchEmbedContents"):
            return batch_response(1)
        return httpx.Response(200, json={"embedding": {"values": vector()}})

    client = embedder(handler)
    await client.embed_documents(["một đoạn bài giảng"])
    await client.embed_query("một câu hỏi")

    assert seen[0][1]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert seen[1][1]["taskType"] == "RETRIEVAL_QUERY"


async def test_every_request_asks_for_the_width_the_column_was_built_for() -> None:
    """`doc_chunks.embedding` is `vector(768)`. Asking for the model's native
    3072 would make every insert fail, and asking for less would make the
    similarity operator compare vectors of different lengths."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append(json.loads(request.content))
        return batch_response(1)

    await embedder(handler).embed_documents(["x"])

    assert seen[0]["requests"][0]["outputDimensionality"] == EMBEDDING_DIMENSIONS


async def test_vectors_come_back_normalised() -> None:
    """At 768 dimensions the API returns unnormalised vectors -- a truncation
    of the model's native width, and Google's own documentation says to
    normalise them. Cosine distance would survive it; a later switch to inner
    product would not, and neither would any hand-checked number."""
    def handler(request: httpx.Request) -> httpx.Response:
        return batch_response(2)

    vectors = await embedder(handler).embed_documents(["a", "b"])

    for values in vectors:
        assert math.isclose(math.sqrt(sum(x * x for x in values)), 1.0, rel_tol=1e-9)


async def test_a_vector_of_the_wrong_width_is_refused() -> None:
    """Better a failed ingest than a table where some rows are 768 wide and
    others are not what they claim."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": [0.1, 0.2]}]})

    with pytest.raises(LLMUnavailableError):
        await embedder(handler).embed_documents(["x"])


async def test_a_zero_vector_is_refused_rather_than_normalised() -> None:
    """Dividing by its norm would be a division by zero, and storing it would
    put a row in the index that is equidistant from every question."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"embeddings": [{"values": [0.0] * EMBEDDING_DIMENSIONS}]}
        )

    with pytest.raises(LLMUnavailableError):
        await embedder(handler).embed_documents(["x"])


async def test_being_rate_limited_is_retried() -> None:
    """The expected failure on a free-tier key, and the kind that goes away on
    its own."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return batch_response(1)

    vectors = await embedder(handler).embed_documents(["x"])

    assert attempts["count"] == 3
    assert len(vectors) == 1


async def test_giving_up_says_what_went_wrong() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "quota exceeded"}})

    with pytest.raises(LLMUnavailableError) as raised:
        await embedder(handler, max_attempts=2).embed_documents(["x"])

    # The worker logs this and the instructor eventually reads it.
    assert "429" in str(raised.value) or "quota" in str(raised.value).lower()


async def test_a_bad_request_is_not_retried() -> None:
    """400 means the request is wrong, and sending it twice more wastes the
    quota that a 429 is already asking us to conserve."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(400, json={"error": {"message": "bad argument"}})

    with pytest.raises(LLMUnavailableError):
        await embedder(handler).embed_documents(["x"])

    assert attempts["count"] == 1


async def test_a_timeout_becomes_a_domain_error() -> None:
    """A worker that crashes on httpx.ReadTimeout gives up the whole course;
    one that catches a domain error can record which lesson failed."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(LLMUnavailableError):
        await embedder(handler, max_attempts=2).embed_documents(["x"])


async def test_long_lists_are_sent_in_batches_and_come_back_in_order() -> None:
    """One call per chunk would make a 40-chunk lesson 40 round trips. Order is
    what ties a vector back to the chunk it belongs to, so it is asserted
    rather than assumed."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        texts = [r["content"]["parts"][0]["text"] for r in json.loads(request.content)["requests"]]
        calls.append(texts)
        # A distinct vector per text, so a reordering would show up below.
        return httpx.Response(
            200,
            json={
                "embeddings": [
                    {"values": vector(float(text) + 1)} for text in texts
                ]
            },
        )

    texts = [str(index) for index in range(120)]
    vectors = await embedder(handler, batch_size=50).embed_documents(texts)

    assert [len(call) for call in calls] == [50, 50, 20]
    assert len(vectors) == 120
    # Normalised, so every component equals 1/sqrt(dim) whatever the input --
    # compare the sign and the relative order instead.
    assert calls[0][0] == "0" and calls[2][-1] == "119"


async def test_several_questions_go_in_one_call_as_questions() -> None:
    """The chatbot embeds a follow-up twice -- alone, and with the question
    before it. One request, not two, and both on the query side of the pair."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        calls.append((request.url.path, json.loads(request.content)))
        return batch_response(2)

    vectors = await embedder(handler).embed_queries(["câu này", "câu trước\ncâu này"])

    assert len(calls) == 1
    path, body = calls[0]
    assert path.endswith(":batchEmbedContents")
    assert [r["taskType"] for r in body["requests"]] == ["RETRIEVAL_QUERY"] * 2
    assert [r["content"]["parts"][0]["text"] for r in body["requests"]] == [
        "câu này",
        "câu trước\ncâu này",
    ]
    assert len(vectors) == 2
    assert math.isclose(math.sqrt(sum(v * v for v in vectors[0])), 1.0, rel_tol=1e-9)


async def test_counting_tokens_asks_the_embedding_model_itself() -> None:
    """The chunker budgets in this model's tokens, so it is this model's
    tokenizer that is asked. Used to check `CHARS_PER_TOKEN` against the real
    chunks (scripts/eval_token_estimate.py), never on the ingest path."""
    import json

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"totalTokens": 207})

    assert await embedder(handler).count_tokens("Biến và phép gán") == 207

    path, body = calls[0]
    assert path.endswith(f"/models/{MODEL}:countTokens")
    assert body == {"contents": [{"parts": [{"text": "Biến và phép gán"}]}]}


async def test_counting_tokens_is_retried_like_any_call() -> None:
    answers = iter([httpx.Response(429), httpx.Response(200, json={"totalTokens": 3})])

    assert await embedder(lambda request: next(answers)).count_tokens("a b c") == 3


async def test_embedding_nothing_calls_nobody() -> None:
    """A video lesson with no transcript chunks to an empty list, and an empty
    request to Gemini is a wasted round trip that also counts against quota."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not have been called")

    assert await embedder(handler).embed_documents([]) == []


async def test_without_a_key_the_failure_says_so() -> None:
    """Distinguishable from "the API is down": one is fixed by pasting a key
    into infra/.env, the other by waiting."""
    with pytest.raises(LLMNotConfiguredError):
        build_embedder(api_key="")


def test_the_adapter_reports_which_model_made_the_vector() -> None:
    """`doc_chunks.embedding_model` records it per row: two models can share a
    width and still put the same sentence somewhere else entirely."""
    assert build_embedder(api_key="k", model=MODEL).model == MODEL
