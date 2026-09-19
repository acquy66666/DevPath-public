"""Request and response shapes for the course assistant.

The answer itself is not a response model: it arrives as a stream of
server-sent events, and the four event payloads are described here so that
there is one place saying what the page will receive, in which order:

1. `sources` -- once, before any text: the lessons this answer may cite,
   numbered the way the answer will cite them. Sent first so the page can
   draw the citation list while the text is still arriving.
2. `delta` -- any number of times: the next piece of the answer.
3. `done` -- once, last: the stored answer and which sources it really cited.
4. `error` -- instead of `done`, when the model fails after the stream has
   started (`LLM_UNAVAILABLE`), or the answer could not be stored because the
   conversation was deleted meanwhile (`CHAT_NOT_SAVED`). Nothing was stored;
   the student can ask again.

Failures *before* the stream starts -- not enrolled, rate limited, Gemini not
configured or not answering -- are ordinary JSON errors with a status code,
because no byte of the stream has been sent yet.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Long enough for a question that pastes a traceback, short enough that one
#: request cannot fill the prompt budget the course material needs.
QUESTION_MAX_CHARS = 2000


class ChatQuestion(BaseModel):
    content: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Câu hỏi không được để trống")
        return stripped


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    #: The first question, cut to fit; null until one has been answered.
    title: str | None
    created_at: datetime
    #: When the last answer finished -- the list is sorted by it.
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    #: Lessons the answer cited, in order of first mention. Empty for a
    #: question, and for an answer that cited nothing (a refusal).
    cited_lesson_ids: list[uuid.UUID]
    created_at: datetime


# --- Stream events ------------------------------------------------------------


class ChatSourceOut(BaseModel):
    """`[number]` in the answer is this lesson."""

    number: int
    lesson_id: uuid.UUID
    lesson_title: str
    section_title: str
    #: Cosine similarity of its best passage to the question, 0..1.
    score: float


class SourcesEvent(BaseModel):
    sources: list[ChatSourceOut]


class DeltaEvent(BaseModel):
    text: str


class DoneEvent(BaseModel):
    #: The stored answer, including its full text: what the page should keep,
    #: in case a piece was lost on the way.
    message: ChatMessageOut
    #: The source numbers the answer cited, in order of first mention.
    cited_numbers: list[int]


class ErrorEvent(BaseModel):
    code: str
    message: str
