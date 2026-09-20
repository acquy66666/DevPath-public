"""Response shapes for `/recommendations`.

A recommendation is a course card plus two things the catalogue never carries:
the score that ranked it, and the course in the reader's own history that
earned it. The second is what turns a list into a sentence -- "vì bạn đã học
Python cơ bản" -- and it is the reason this endpoint exists rather than the
page calling the catalogue with a sort parameter.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.courses import CourseCardOut


class ReasonOut(BaseModel):
    """The course being quoted as the reason. Enough to render a link."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str


class RecommendedCourseOut(CourseCardOut):
    #: The model's score. Sent because the thesis evaluates the ranking, and a
    #: ranking whose numbers never leave the server cannot be checked against
    #: what the page actually showed.
    score: float
    #: None when the course that earned this has since been withdrawn -- the
    #: recommendation still stands, the sentence explaining it does not -- and
    #: always None for a popular one, earned by nothing the reader did.
    because: ReasonOut | None
    #: Which halves of the hybrid put this card here: `collaborative`,
    #: `content`, both, or `popular` for a fallback row. The page uses it to
    #: label the block honestly, and the thesis uses it to show the mix -- a
    #: hybrid that cannot say which half spoke is a hybrid nobody can check.
    sources: list[str]


class RecommendationsOut(BaseModel):
    """The block, and whether it has ever been computed.

    `generated_at` is null in exactly one case: nothing is cached for this
    user. That is a different answer from an empty `items` with a timestamp,
    which means the model ran and found nothing to suggest -- and it is the
    difference between "come back tomorrow" and "we have nothing for you yet",
    which the hybrid of a later task answers with popular courses.
    """

    items: list[RecommendedCourseOut]
    generated_at: datetime | None


class SimilarCourseOut(CourseCardOut):
    """One neighbour on a course page."""

    #: Cosine similarity with the course being viewed, 1.0 being identical.
    #: Sent for the same reason `RecommendedCourseOut.score` is: the thesis
    #: evaluates this ranking, and a ranking whose numbers never leave the
    #: server cannot be checked against what the page showed.
    score: float


class SimilarCoursesOut(BaseModel):
    """The "Khóa học tương tự" block.

    No `generated_at` and no pagination, unlike the two blocks it sits next
    to. There is nothing to date -- the answer is computed from the table on
    every request rather than read out of a nightly cache -- and a page that
    offered a second page of "similar" courses would be a catalogue with a
    strange sort order, which `GET /courses` already is.

    An empty `items` has one meaning here: this course has no vector yet, or
    nothing published shares its model. Both read the same way on the page,
    which is to draw no block at all.
    """

    items: list[SimilarCourseOut]
