"""The structured half of the LLM adapter: one prompt in, one JSON document out.

What the quiz generator asks for. No network, for the reason `test_llm.py`
gives. What is worth pinning down is how each way of *not* getting a usable
document is treated, because they need different handling:

* the server is busy or out of quota → retried, like every other call here;
* the answer was cut off at `maxOutputTokens` → not retried: the same prompt
  under the same limit is cut off in the same place, and the quota a retry
  burns is the thing a quota error was asking us to save;
* the prompt was blocked, or nothing came back → not retried, same argument;
* the text is not JSON → retried: the schema makes it rare, sampling makes it
  unlikely to happen twice.
"""

import json

import httpx
import pytest

from app.services.llm import (
    GeminiJson,
    LLMNotConfiguredError,
    LLMUnavailableError,
    build_quiz_model,
)

MODEL = "gemini-test-flash"
SCHEMA = {
    "type": "OBJECT",
    "properties": {"questions": {"type": "ARRAY", "items": {"type": "STRING"}}},
    "required": ["questions"],
}


def answer(text: str, *, finish: str = "STOP", thought: str | None = None) -> httpx.Response:
    parts = ([{"text": thought, "thought": True}] if thought else []) + [{"text": text}]
    candidate = {"content": {"parts": parts, "role": "model"}, "finishReason": finish}
    return httpx.Response(200, json={"candidates": [candidate]})


def model(handler, **kwargs) -> GeminiJson:
    return GeminiJson(
        api_key="not-a-real-key",
        model=MODEL,
        base_url="https://example.invalid/v1beta",
        timeout_s=5,
        max_attempts=kwargs.pop("max_attempts", 3),
        max_output_tokens=kwargs.pop("max_output_tokens", 4096),
        thinking_level=kwargs.pop("thinking_level", "minimal"),
        retry_base_delay_s=0,
        transport=httpx.MockTransport(handler),
    )


async def generate(json_model: GeminiJson):
    return await json_model.generate(
        system="Bạn soạn câu hỏi trắc nghiệm.", prompt="TÀI LIỆU: ...", schema=SCHEMA
    )


async def test_the_document_comes_back_parsed() -> None:
    result = await generate(model(lambda request: answer('{"questions": ["a", "b"]}')))

    assert result == {"questions": ["a", "b"]}


async def test_the_request_asks_for_json_in_the_given_shape() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answer('{"questions": []}')

    await generate(model(handler, max_output_tokens=2048, thinking_level="minimal"))

    request = seen[0]
    assert request.url.path.endswith(f"/models/{MODEL}:generateContent")
    assert request.headers["x-goog-api-key"] == "not-a-real-key"
    body = json.loads(request.content)
    assert body["systemInstruction"] == {"parts": [{"text": "Bạn soạn câu hỏi trắc nghiệm."}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "TÀI LIỆU: ..."}]}]
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseSchema"] == SCHEMA
    assert config["maxOutputTokens"] == 2048
    assert config["thinkingConfig"] == {"thinkingLevel": "minimal"}


async def test_no_thinking_level_means_no_thinking_config() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return answer("{}")

    await generate(model(handler, thinking_level=""))

    assert "thinkingConfig" not in seen[0]["generationConfig"]


async def test_thought_parts_are_not_part_of_the_document() -> None:
    result = await generate(model(lambda request: answer('{"questions": []}', thought="hmm {")))

    assert result == {"questions": []}


async def test_being_rate_limited_is_retried() -> None:
    replies = iter([httpx.Response(429, json={"error": {"code": 429}}), answer('{"ok": 1}')])

    assert await generate(model(lambda request: next(replies))) == {"ok": 1}


async def test_a_bad_request_is_not_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, json={"error": {"message": "Invalid schema"}})

    with pytest.raises(LLMUnavailableError, match="HTTP 400"):
        await generate(model(handler))
    assert len(calls) == 1


async def test_text_that_is_not_json_is_retried() -> None:
    replies = iter([answer('{"questions": [ "cut'), answer('{"questions": []}')])

    assert await generate(model(lambda request: next(replies))) == {"questions": []}


async def test_text_that_is_never_json_gives_up_and_says_so() -> None:
    with pytest.raises(LLMUnavailableError, match="JSON"):
        await generate(model(lambda request: answer("không phải JSON"), max_attempts=2))


async def test_an_answer_cut_off_at_the_token_limit_is_not_retried() -> None:
    """Same prompt, same limit, same cut. Retrying buys the same half answer."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return answer('{"questions": ["a", "b', finish="MAX_TOKENS")

    with pytest.raises(LLMUnavailableError, match="maxOutputTokens"):
        await generate(model(handler))
    assert len(calls) == 1


async def test_a_blocked_prompt_is_not_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})

    with pytest.raises(LLMUnavailableError, match="SAFETY"):
        await generate(model(handler))
    assert len(calls) == 1


async def test_a_timeout_becomes_a_domain_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMUnavailableError, match="ReadTimeout"):
        await generate(model(handler, max_attempts=2))


def test_without_a_key_the_failure_says_so() -> None:
    with pytest.raises(LLMNotConfiguredError):
        build_quiz_model(api_key="")


def test_the_quiz_model_is_the_one_configured_for_quizzes() -> None:
    assert build_quiz_model(api_key="k").model == "gemini-3.5-flash"
