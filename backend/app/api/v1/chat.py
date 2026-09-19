"""The course assistant over HTTP: conversations, and answers as a stream.

Asking is `POST /chat-sessions/{id}/messages`, and it answers with server-sent
events rather than JSON (the four event types are in `schemas/chat.py`). SSE
over a POST rather than `EventSource`, because `EventSource` can neither send
a body nor an `Authorization` header; the page reads the stream with `fetch`.

The split between a status code and an `error` event is exactly the split
between `prepare_answer` and `answer_events`: everything that can be refused
is refused before `StreamingResponse` exists, so a refusal still arrives with
its status and the usual error envelope.

`X-Accel-Buffering: no` is for nginx, which buffers proxied responses by
default and would otherwise deliver the whole answer at once, at the end --
the stream would work in development and silently stop streaming in
production.
"""

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.deps import CurrentUser, DbSession
from app.models import ChatMessage
from app.schemas.chat import (
    ChatCitationOut,
    ChatMessageOut,
    ChatQuestion,
    ChatSessionOut,
    ChatSourceOut,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import chat as chat_service
from app.services.llm import (
    ChatModel,
    Embedder,
    get_chat_model_factory,
    get_embedder_factory,
)
from app.services.rate_limit import RateLimiter, get_rate_limiter

router = APIRouter(tags=["chat"])

RateLimit = Annotated[RateLimiter, Depends(get_rate_limiter)]
EmbedderFactory = Annotated[Callable[[], Embedder], Depends(get_embedder_factory)]
ChatModelFactory = Annotated[Callable[[], ChatModel], Depends(get_chat_model_factory)]


def message_out(message: ChatMessage) -> ChatMessageOut:
    out = ChatMessageOut.model_validate(message)
    out.citations = [
        ChatCitationOut(number=number, lesson_id=lesson_id)
        for number, lesson_id in chat_service.numbered_citations(
            message.content, message.cited_lesson_ids
        )
    ]
    return out


def sse(event: str, payload: BaseModel) -> str:
    return f"event: {event}\ndata: {payload.model_dump_json()}\n\n"


def encode(event: chat_service.ChatEvent) -> str:
    """One service event as one SSE frame."""
    match event:
        case chat_service.SourcesReady(sources=sources):
            return sse(
                "sources",
                SourcesEvent(
                    sources=[
                        ChatSourceOut(
                            number=source.number,
                            lesson_id=source.lesson_id,
                            lesson_title=source.lesson_title,
                            section_title=source.section_title,
                            score=round(source.score, 4),
                        )
                        for source in sources
                    ]
                ),
            )
        case chat_service.AnswerPiece(text=text):
            return sse("delta", DeltaEvent(text=text))
        case chat_service.AnswerStored(message=message, cited_numbers=numbers):
            return sse("done", DoneEvent(message=message_out(message), cited_numbers=numbers))
        case chat_service.AnswerFailed(code=code, message=message):
            return sse("error", ErrorEvent(code=code, message=message))


@router.post(
    "/courses/{course_id}/chat-sessions",
    response_model=ChatSessionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> ChatSessionOut:
    """Start a conversation with the assistant of a course you are enrolled in."""
    chat_session = await chat_service.create_session(session, course_id, current_user)
    return ChatSessionOut.model_validate(chat_session)


@router.get("/courses/{course_id}/chat-sessions", response_model=Page[ChatSessionOut])
async def list_sessions(
    course_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[ChatSessionOut]:
    """Your own conversations in this course, most recently answered first."""
    sessions, total = await chat_service.list_sessions(
        session, course_id, current_user, page=page, page_size=page_size
    )
    return Page[ChatSessionOut](
        items=[ChatSessionOut.model_validate(item) for item in sessions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/chat-sessions/{session_id}/messages", response_model=Page[ChatMessageOut])
async def list_messages(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[ChatMessageOut]:
    """One of your conversations, oldest message first."""
    messages, total = await chat_service.list_messages(
        session, session_id, current_user, page=page, page_size=page_size
    )
    return Page[ChatMessageOut](
        items=[message_out(message) for message in messages],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/chat-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Delete one of your conversations and every message in it."""
    await chat_service.delete_session(session, session_id, current_user)


@router.post(
    "/chat-sessions/{session_id}/messages",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-sent events: `sources`, `delta`…, then `done` or `error`",
            "content": {"text/event-stream": {}},
        }
    },
)
async def ask(
    session_id: uuid.UUID,
    payload: ChatQuestion,
    current_user: CurrentUser,
    session: DbSession,
    limiter: RateLimit,
    make_embedder: EmbedderFactory,
    make_chat_model: ChatModelFactory,
) -> StreamingResponse:
    """Ask the course assistant; the answer arrives as it is written.

    Answers only from this course's material and cites it as `[n]`, where n
    is a number from the `sources` event. Refusals before the stream --
    404/403/429/503 -- come back as JSON with the usual error envelope.
    """
    prepared = await chat_service.prepare_answer(
        session,
        session_id,
        current_user,
        payload.content,
        limiter=limiter,
        make_embedder=make_embedder,
        make_chat_model=make_chat_model,
    )

    async def frames() -> AsyncIterator[str]:
        async for event in chat_service.answer_events(session, prepared):
            yield encode(event)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
