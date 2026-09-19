"""The streaming half of the LLM adapter: generating an answer, piece by piece.

No network, for the same reason as `test_llm.py`: what is worth testing is what
this code does when Gemini misbehaves, and a live call will not misbehave on
demand. The misbehaviour with the most tests here is one that was *seen*, not
imagined: while probing models for this task, `streamGenerateContent` answered
200, streamed six pieces of an answer, and then ended with a bare JSON error
body -- `503 UNAVAILABLE, "experiencing high demand"` -- that is not an SSE
event at all. A parser that only reads `data:` lines drops it silently and
the student gets half an answer presented as a whole one.

The rule the tests pin down: a failure **before the first piece** is retried
like any other call; a failure **after** it is not, because the student has
already seen text that a second attempt would contradict, so it surfaces as
an error the endpoint can put in front of them.
"""

import json

import httpx
import pytest

from app.services.llm import (
    ChatTurn,
    GeminiChat,
    LLMNotConfiguredError,
    LLMUnavailableError,
    build_chat_model,
)

MODEL = "gemini-test-flash"


def event(*texts: str, finish: str | None = None, thought: bool = False) -> str:
    candidate: dict = {
        "content": {
            "parts": [{"text": text, **({"thought": True} if thought else {})} for text in texts],
            "role": "model",
        },
        "index": 0,
    }
    if finish:
        candidate["finishReason"] = finish
    return "data: " + json.dumps({"candidates": [candidate]}, ensure_ascii=False) + "\r\n\r\n"


def sse(*events: str) -> httpx.Response:
    return httpx.Response(
        200,
        content="".join(events).encode(),
        headers={"Content-Type": "text/event-stream"},
    )


# Exactly what arrived during the probe, after the last `data:` event.
MID_STREAM_503 = (
    '{\n  "error": {\n    "code": 503,\n    "message": "This model is currently '
    'experiencing high demand. Spikes in demand are usually temporary. Please try '
    'again later.",\n    "status": "UNAVAILABLE"\n  }\n}\n'
)


def chat(handler, **kwargs) -> GeminiChat:
    return GeminiChat(
        api_key="not-a-real-key",
        model=MODEL,
        base_url="https://example.invalid/v1beta",
        timeout_s=5,
        max_attempts=kwargs.pop("max_attempts", 3),
        max_output_tokens=kwargs.pop("max_output_tokens", 1024),
        thinking_level=kwargs.pop("thinking_level", "low"),
        retry_base_delay_s=0,
        transport=httpx.MockTransport(handler),
    )


async def collect(model: GeminiChat, turns=None) -> list[str]:
    turns = turns or [ChatTurn(role="user", text="Vòng lặp for là gì?")]
    return [piece async for piece in model.stream(system="Bạn là trợ giảng.", turns=turns)]


async def test_pieces_arrive_in_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return sse(event("Vòng lặp "), event("for duyệt "), event("từng phần tử.", finish="STOP"))

    assert await collect(chat(handler)) == ["Vòng lặp ", "for duyệt ", "từng phần tử."]


async def test_the_request_carries_the_system_prompt_the_turns_and_the_limits() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return sse(event("ok", finish="STOP"))

    turns = [
        ChatTurn(role="user", text="câu trước"),
        ChatTurn(role="model", text="đáp trước"),
        ChatTurn(role="user", text="câu này"),
    ]
    await collect(chat(handler, max_output_tokens=777), turns)

    request = seen[0]
    assert request.url.path.endswith(f"/models/{MODEL}:streamGenerateContent")
    assert request.url.params["alt"] == "sse"
    body = json.loads(request.content)
    assert body["systemInstruction"] == {"parts": [{"text": "Bạn là trợ giảng."}]}
    assert body["contents"] == [
        {"role": "user", "parts": [{"text": "câu trước"}]},
        {"role": "model", "parts": [{"text": "đáp trước"}]},
        {"role": "user", "parts": [{"text": "câu này"}]},
    ]
    # Thinking tokens are paid out of maxOutputTokens: at a limit of 200 the
    # probe got 188 tokens of thinking and an eight-token answer cut off
    # mid-sentence. So the adapter always says how much thinking it wants.
    assert body["generationConfig"] == {
        "maxOutputTokens": 777,
        "thinkingConfig": {"thinkingLevel": "low"},
    }


async def test_no_thinking_level_means_no_thinking_config() -> None:
    """Gemini 2.5 models take a thinking *budget* and reject a level, so
    leaving the level empty must leave the field out entirely."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return sse(event("ok", finish="STOP"))

    await collect(chat(handler, thinking_level=""))

    assert "thinkingConfig" not in seen[0]["generationConfig"]


async def test_thought_parts_are_not_part_of_the_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return sse(event("suy nghĩ nội bộ", thought=True), event("Câu trả lời.", finish="STOP"))

    assert await collect(chat(handler)) == ["Câu trả lời."]


async def test_being_rate_limited_before_the_first_piece_is_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})
        return sse(event("Được rồi.", finish="STOP"))

    assert await collect(chat(handler)) == ["Được rồi."]
    assert len(calls) == 2


async def test_a_bad_request_is_not_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, json={"error": {"message": "invalid thinking level"}})

    with pytest.raises(LLMUnavailableError, match="HTTP 400"):
        await collect(chat(handler))
    assert len(calls) == 1


async def test_an_error_body_after_part_of_the_answer_is_an_error_not_an_ending() -> None:
    """The probe's exact failure. The pieces already sent stay sent -- they
    are on the student's screen -- and then the stream raises instead of
    ending as if the answer were whole. No retry: a second answer would not
    continue the first one, it would contradict it."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return sse(event("Vòng lặp "), event("for trong "), MID_STREAM_503)

    received: list[str] = []
    with pytest.raises(LLMUnavailableError, match="503"):
        async for piece in chat(handler).stream(
            system="s", turns=[ChatTurn(role="user", text="q")]
        ):
            received.append(piece)

    assert received == ["Vòng lặp ", "for trong "]
    assert len(calls) == 1


async def test_an_error_body_before_any_piece_is_retried_like_a_status_code() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return sse(MID_STREAM_503)
        return sse(event("Lần hai thì được.", finish="STOP"))

    assert await collect(chat(handler)) == ["Lần hai thì được."]
    assert len(calls) == 2


async def test_giving_up_says_what_went_wrong() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})

    with pytest.raises(LLMUnavailableError, match="HTTP 503"):
        await collect(chat(handler, max_attempts=2))


async def test_a_timeout_becomes_a_domain_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(LLMUnavailableError, match="ReadTimeout"):
        await collect(chat(handler, max_attempts=2))


async def test_an_answer_with_no_text_at_all_is_an_error() -> None:
    """A blocked prompt comes back 200 with no candidates. Streaming nothing
    and calling it an answer would leave an empty bubble on the page."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {"promptFeedback": {"blockReason": "SAFETY"}}
        return sse("data: " + json.dumps(body) + "\r\n\r\n")

    with pytest.raises(LLMUnavailableError, match="SAFETY"):
        await collect(chat(handler))


async def test_without_a_key_the_failure_says_so() -> None:
    with pytest.raises(LLMNotConfiguredError):
        build_chat_model(api_key="")


def test_the_adapter_reports_which_model_answers() -> None:
    assert build_chat_model(api_key="k", model=MODEL).model == MODEL
