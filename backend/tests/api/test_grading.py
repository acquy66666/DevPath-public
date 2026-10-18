"""Code exercises, test cases and submissions over HTTP.

The test this file exists for is `test_a_student_never_receives_an_answer_key`.
Everything else here is ordinary CRUD coverage; that one is the property the
whole feature depends on, and it is asserted against the raw response body
rather than against a parsed field, because a leak that appears in a key
nobody thought to check is exactly the kind that ships.

The second thing worth reading is the pair of constraint tests at the bottom.
A submission may not carry a verdict before it is `done`, and that is enforced
by the database rather than by the worker that will write those rows -- so it
is tested where it lives, with SQL, not through the API.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import (
    Category,
    CodeExercise,
    Course,
    Enrollment,
    Submission,
    TestCase,
    User,
)
from app.services import grading as grading_service
from app.services import grading_events
from app.services.rate_limit import get_rate_limiter
from app.workers.grading import CaseOutcome, GradingOutcome, run_grading
from tests.api.fakes import MemoryRateLimiter

PASSWORD = "mật-khẩu-đủ-dài"
COURSES = "/api/v1/courses"

# The answer to a hidden case. If this string ever reaches a student's
# response body, the exercise is worthless and the test that finds it says so
# by name.
SECRET_ANSWER = "SECRET-ANSWER-DO-NOT-LEAK"
SECRET_INPUT = "SECRET-INPUT-DO-NOT-LEAK"
# What a program printed when it was fed the secret input. It describes that
# input one round trip later, so it is on the same list.
SECRET_STDOUT = "SECRET-STDOUT-DO-NOT-LEAK"


async def make_user(session: AsyncSession, role: str, email: str | None = None) -> User:
    user = User(
        email=email or f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        full_name=role.title(),
        password_hash=hash_password(PASSWORD),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def sign_in(client: AsyncClient, user: User) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(autouse=True)
def queued(monkeypatch: pytest.MonkeyPatch) -> list:
    """Submissions are handed to Celery; these tests are not about Celery.

    Autouse, and replacing the function rather than the broker URL: without it
    every submission test would need a running Redis, and on a developer
    machine that has one it would enqueue real jobs against rows this
    transaction is about to roll back.
    """
    ids: list = []
    monkeypatch.setattr(grading_service, "enqueue_grading", ids.append)
    return ids


@pytest.fixture
async def owner_user(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def owner(api_client: AsyncClient, owner_user: User) -> dict[str, str]:
    return await sign_in(api_client, owner_user)


@pytest.fixture
async def lesson(
    api_client: AsyncClient,
    db_session: AsyncSession,
    owner_user: User,
    owner: dict[str, str],
) -> dict:
    """A published course with one `code_exercise` lesson in it.

    Published, and built through the model rather than by walking the review
    workflow: a draft course is invisible to students, so every enrolment and
    submission test below would fail on the course being unreadable long
    before it reached anything this file is about.
    """
    category = Category(name="Python", slug=f"python-{uuid.uuid4().hex[:8]}")
    db_session.add(category)
    await db_session.flush()

    course = Course(
        instructor_id=owner_user.id,
        category_id=category.id,
        title="Lập trình Python cơ bản",
        slug=f"python-co-ban-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    db_session.add(course)
    await db_session.flush()

    section = (
        await api_client.post(
            f"{COURSES}/{course.id}/sections", json={"title": "Chương 1"}, headers=owner
        )
    ).json()
    created = await api_client.post(
        f"/api/v1/sections/{section['id']}/lessons",
        json={"title": "Bài tập: tổng hai số", "type": "code_exercise"},
        headers=owner,
    )
    assert created.status_code == 201, created.text
    return created.json() | {"course_id": str(course.id)}


@pytest.fixture
async def exercise(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str]
) -> dict:
    response = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/code-exercise",
        json={
            "statement_md": "Đọc hai số, in ra tổng.",
            "starter_code": "a, b = input().split()\n",
            "time_limit_ms": 2000,
            "memory_limit_mb": 128,
        },
        headers=owner,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def student_user(db_session: AsyncSession, lesson: dict) -> User:
    """A student enrolled in the course, so the lesson is theirs to open."""
    user = await make_user(db_session, "student")
    db_session.add(Enrollment(user_id=user.id, course_id=uuid.UUID(lesson["course_id"])))
    await db_session.flush()
    return user


@pytest.fixture
async def student(api_client: AsyncClient, student_user: User) -> dict[str, str]:
    return await sign_in(api_client, student_user)


async def add_case(
    client: AsyncClient,
    exercise: dict,
    headers: dict[str, str],
    *,
    input: str = "",
    expected_output: str = "3\n",
    is_hidden: bool = True,
    score_weight: int = 1,
) -> dict:
    response = await client.post(
        f"/api/v1/code-exercises/{exercise['id']}/test-cases",
        json={
            "input": input,
            "expected_output": expected_output,
            "is_hidden": is_hidden,
            "score_weight": score_weight,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Authoring the exercise ------------------------------------------------


async def test_the_owner_creates_an_exercise_on_a_code_lesson(exercise: dict):
    assert exercise["language"] == "python"
    assert exercise["time_limit_ms"] == 2000
    assert exercise["starter_code"].startswith("a, b =")


async def test_a_lesson_of_the_wrong_type_cannot_carry_an_exercise(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str]
):
    """An article lesson with an exercise behind it would never be reachable."""
    article = await api_client.post(
        f"/api/v1/sections/{lesson['section_id']}/lessons",
        json={"title": "Bài giảng", "type": "article"},
        headers=owner,
    )
    response = await api_client.post(
        f"/api/v1/lessons/{article.json()['id']}/code-exercise",
        json={"statement_md": "..."},
        headers=owner,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "LESSON_NOT_CODE_EXERCISE"


async def test_one_exercise_per_lesson(
    api_client: AsyncClient, lesson: dict, exercise: dict, owner: dict[str, str]
):
    response = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/code-exercise",
        json={"statement_md": "Bài thứ hai"},
        headers=owner,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EXERCISE_EXISTS"


async def test_creating_an_exercise_needs_a_sign_in(
    api_client: AsyncClient, lesson: dict
):
    response = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/code-exercise",
        json={"statement_md": "..."},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NOT_AUTHENTICATED"


async def test_another_instructor_cannot_touch_this_exercise(
    api_client: AsyncClient, db_session: AsyncSession, exercise: dict
):
    stranger = await sign_in(api_client, await make_user(db_session, "instructor"))

    response = await api_client.patch(
        f"/api/v1/code-exercises/{exercise['id']}",
        json={"statement_md": "đổi đề bài của người khác"},
        headers=stranger,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("time_limit_ms", 50),  # below the floor
        ("time_limit_ms", 60_000),  # a minute per test case, on a shared VPS
        ("memory_limit_mb", 8),
        ("memory_limit_mb", 4096),
    ],
)
async def test_limits_outside_the_ceiling_are_refused(
    api_client: AsyncClient, lesson: dict, owner: dict[str, str], field: str, value: int
):
    """The numbers on this form are multiplied by every student who submits."""
    response = await api_client.post(
        f"/api/v1/lessons/{lesson['id']}/code-exercise",
        json={"statement_md": "...", field: value},
        headers=owner,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


async def test_an_unknown_exercise_is_a_404(
    api_client: AsyncClient, owner: dict[str, str]
):
    response = await api_client.get(
        f"/api/v1/code-exercises/{uuid.uuid4()}/test-cases", headers=owner
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "EXERCISE_NOT_FOUND"


# --- Test cases ------------------------------------------------------------


async def test_cases_are_appended_in_order_and_renumbered_after_a_delete(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str]
):
    first = await add_case(api_client, exercise, owner, expected_output="1\n")
    second = await add_case(api_client, exercise, owner, expected_output="2\n")
    third = await add_case(api_client, exercise, owner, expected_output="3\n")
    assert [first["position"], second["position"], third["position"]] == [0, 1, 2]

    deleted = await api_client.delete(
        f"/api/v1/test-cases/{second['id']}", headers=owner
    )
    assert deleted.status_code == 204

    remaining = (
        await api_client.get(
            f"/api/v1/code-exercises/{exercise['id']}/test-cases", headers=owner
        )
    ).json()
    assert [case["position"] for case in remaining] == [0, 1]
    assert [case["expected_output"] for case in remaining] == ["1\n", "3\n"]


async def test_cases_can_be_reordered_as_a_whole_list(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str]
):
    first = await add_case(api_client, exercise, owner, expected_output="1\n")
    second = await add_case(api_client, exercise, owner, expected_output="2\n")

    response = await api_client.put(
        f"/api/v1/code-exercises/{exercise['id']}/test-cases/order",
        json={"test_case_ids": [second["id"], first["id"]]},
        headers=owner,
    )

    assert response.status_code == 200
    assert [case["expected_output"] for case in response.json()] == ["2\n", "1\n"]


async def test_a_partial_order_is_refused_rather_than_half_applied(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str]
):
    first = await add_case(api_client, exercise, owner)
    await add_case(api_client, exercise, owner)

    response = await api_client.put(
        f"/api/v1/code-exercises/{exercise['id']}/test-cases/order",
        json={"test_case_ids": [first["id"]]},
        headers=owner,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_ORDER"


async def test_a_case_is_hidden_unless_the_instructor_says_otherwise(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str]
):
    """The mistake that costs an exercise its integrity must be deliberate."""
    response = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/test-cases",
        json={"expected_output": "3\n"},
        headers=owner,
    )

    assert response.json()["is_hidden"] is True


# --- The rule the feature depends on ---------------------------------------


async def test_a_student_never_receives_an_answer_key(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str], student: dict[str, str]
):
    """Hidden inputs and expected outputs do not appear in the response. At all.

    Asserted against the raw body, not against parsed fields: a leak through a
    key nobody thought to check is exactly the kind that gets shipped. The
    sample case is the control -- it proves the endpoint is really returning
    the cases rather than passing by being empty.
    """
    await add_case(
        api_client,
        exercise,
        owner,
        input="1 2\n",
        expected_output="3\n",
        is_hidden=False,
    )
    await add_case(
        api_client,
        exercise,
        owner,
        input=SECRET_INPUT,
        expected_output=SECRET_ANSWER,
        is_hidden=True,
        score_weight=3,
    )

    response = await api_client.get(
        f"/api/v1/code-exercises/{exercise['id']}/test-cases", headers=student
    )
    body = response.text
    cases = response.json()

    assert response.status_code == 200
    assert SECRET_ANSWER not in body
    assert SECRET_INPUT not in body

    sample, hidden = cases
    # The sample is the question, and the student reads it.
    assert sample["sample_input"] == "1 2\n"
    assert sample["sample_output"] == "3\n"
    # The hidden one is present -- knowing there are eight cases and what each
    # is worth is how the exercise is marked, not how to pass it.
    assert hidden["is_hidden"] is True
    assert hidden["sample_input"] is None
    assert hidden["sample_output"] is None
    assert hidden["score_weight"] == 3


async def test_the_owner_does_receive_the_answer_key(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str]
):
    """The other half: the instructor has to be able to edit what they wrote."""
    await add_case(api_client, exercise, owner, expected_output=SECRET_ANSWER)

    response = await api_client.get(
        f"/api/v1/code-exercises/{exercise['id']}/test-cases", headers=owner
    )

    assert SECRET_ANSWER in response.text
    assert response.json()[0]["expected_output"] == SECRET_ANSWER


async def test_someone_who_has_not_enrolled_cannot_read_the_exercise(
    api_client: AsyncClient, db_session: AsyncSession, exercise: dict, lesson: dict
):
    outsider = await sign_in(api_client, await make_user(db_session, "student"))

    response = await api_client.get(
        f"/api/v1/lessons/{lesson['id']}/code-exercise", headers=outsider
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "LESSON_LOCKED"


# --- The same rule, one layer further out ----------------------------------
#
# The tests above are about the endpoint that lists test cases. These are
# about every other way the answer key could get out: the routes that return
# `TestCaseOut` in full, and the results of a grading run -- which is where a
# hidden case stops being a row in a table and becomes something a student is
# shown.


ANSWER_KEY_ROUTES = [
    ("POST", "/api/v1/code-exercises/{exercise}/test-cases"),
    ("PATCH", "/api/v1/test-cases/{case}"),
    ("DELETE", "/api/v1/test-cases/{case}"),
    ("PUT", "/api/v1/code-exercises/{exercise}/test-cases/order"),
]


@pytest.mark.parametrize(("method", "path"), ANSWER_KEY_ROUTES)
async def test_no_authoring_route_hands_a_student_the_answer_key(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    method: str,
    path: str,
):
    """Every route that answers with `TestCaseOut` refuses a student.

    The list endpoint chooses a model by who is asking; these four have only
    one model, the one with the answers in it, so the caller is refused
    instead. An enrolled student is the caller that matters here -- they can
    read the exercise legitimately, so nothing but the ownership check stands
    between them and the key.
    """
    case = await add_case(
        api_client, exercise, owner, input=SECRET_INPUT, expected_output=SECRET_ANSWER
    )

    response = await api_client.request(
        method,
        path.format(exercise=exercise["id"], case=case["id"]),
        json={"input": "1 2\n", "expected_output": "3\n", "test_case_ids": [case["id"]]},
        headers=student,
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"
    assert SECRET_ANSWER not in response.text
    assert SECRET_INPUT not in response.text


async def graded_submission(
    client: AsyncClient,
    session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
) -> str:
    """One submission, graded for real by the worker's own code path.

    The judge is faked -- Docker is not what is under test here -- but
    everything that decides what is written down is the code that runs in
    production.
    """
    await add_case(
        client, exercise, owner, input="1 2\n", expected_output="3\n", is_hidden=False
    )
    await add_case(
        client, exercise, owner, input=SECRET_INPUT, expected_output=SECRET_ANSWER
    )

    created = await client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print(1)"},
        headers=student,
    )
    assert created.status_code == 201, created.text

    def judge(code, cases, **limits):
        # Both cases print the secret. If any of it survives to an endpoint,
        # the assertions below find it wherever it ended up.
        return GradingOutcome(
            verdict="WA",
            cases=(
                CaseOutcome(verdict="AC", run_time_ms=11, stdout="3\n"),
                CaseOutcome(verdict="WA", run_time_ms=12, stdout=SECRET_STDOUT),
            ),
        )

    await run_grading(session, uuid.UUID(created.json()["id"]), judge=judge)
    return created.json()["id"]


async def test_a_graded_hidden_case_gives_up_its_verdict_and_nothing_else(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    """What a program printed on a secret input describes the secret input.

    The verdict is not the leak -- knowing case 2 failed is how marking works.
    The output is, and it is absent from the row as well as from the response.
    """
    submission_id = await graded_submission(
        api_client, db_session, exercise, owner, student
    )

    response = await api_client.get(
        f"/api/v1/submissions/{submission_id}", headers=student
    )
    body = response.text
    results = response.json()["results"]

    assert response.status_code == 200
    assert SECRET_STDOUT not in body
    assert SECRET_ANSWER not in body
    assert SECRET_INPUT not in body

    sample, hidden = results
    # The sample case is the control: without it this test would pass on an
    # endpoint that returned no results at all.
    assert sample["is_hidden"] is False
    assert sample["stdout_trunc"] == "3\n"
    # And the hidden one is still marked, and still says so.
    assert hidden["is_hidden"] is True
    assert hidden["verdict"] == "WA"
    assert hidden["stdout_trunc"] is None


async def test_the_owner_reading_a_submission_gets_no_hidden_output_either(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    """Stricter than it strictly needs to be, deliberately.

    The instructor wrote the hidden case, so showing them what a submission
    printed on it would leak nothing they do not know. It is still not shown:
    the worker never stored it, so there is no path that depends on the API
    remembering who is asking.
    """
    submission_id = await graded_submission(
        api_client, db_session, exercise, owner, student
    )

    response = await api_client.get(
        f"/api/v1/submissions/{submission_id}", headers=owner
    )

    assert response.status_code == 200
    assert SECRET_STDOUT not in response.text
    assert response.json()["results"][1]["stdout_trunc"] is None


# --- Submitting ------------------------------------------------------------


async def test_a_submission_arrives_pending_with_no_verdict(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    queued: list,
):
    """Nothing grades it yet, and the API says so rather than inventing one."""
    await add_case(api_client, exercise, owner)

    response = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print(sum(map(int, input().split())))"},
        headers=student,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["verdict"] is None
    assert body["score"] is None
    # From the exercise, not from the client: what a submission is graded as
    # is not the submitter's decision.
    assert body["language"] == "python"

    # And it is on its way: the row is committed first, then queued, so the
    # worker cannot be handed an id the database has not seen yet.
    assert queued == [uuid.UUID(body["id"])]


async def test_a_queue_that_refuses_the_job_does_not_report_success(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    """A 201 would leave a student watching a row no worker will ever pick up.

    The row is kept -- as `error`, with a message -- rather than deleted: it is
    the record that they did submit, and deleting it would make the failure
    disappear from the one place anybody looks.
    """
    await add_case(api_client, exercise, owner)

    def refuse(submission_id):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(grading_service, "enqueue_grading", refuse)

    response = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print(1)"},
        headers=student,
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "GRADING_UNAVAILABLE"

    # Scoped to this exercise: the suite runs against the development database,
    # where a submission made by hand is a row like any other.
    parked = (
        await db_session.scalars(
            select(Submission).where(
                Submission.exercise_id == uuid.UUID(exercise["id"])
            )
        )
    ).all()
    assert [row.status for row in parked] == ["error"]
    assert parked[0].verdict is None
    assert parked[0].message


async def test_an_exercise_with_no_test_cases_refuses_submissions(
    api_client: AsyncClient, exercise: dict, student: dict[str, str]
):
    """Queueing work whose only outcome is a system error helps nobody."""
    response = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print(1)"},
        headers=student,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EXERCISE_NOT_READY"


async def test_submitting_needs_a_sign_in(api_client: AsyncClient, exercise: dict):
    response = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions", json={"code": "print(1)"}
    )

    assert response.status_code == 401


async def test_someone_who_has_not_enrolled_cannot_submit(
    api_client: AsyncClient, db_session: AsyncSession, exercise: dict, owner: dict[str, str]
):
    await add_case(api_client, exercise, owner)
    outsider = await sign_in(api_client, await make_user(db_session, "student"))

    response = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print(1)"},
        headers=outsider,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "LESSON_LOCKED"


async def test_empty_code_is_refused(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str], student: dict[str, str]
):
    await add_case(api_client, exercise, owner)

    response = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": ""},
        headers=student,
    )

    assert response.status_code == 422


@pytest.mark.parametrize("route", ["submissions", "trial-runs"])
async def test_code_with_a_nul_byte_is_refused_before_it_is_stored(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    route: str,
):
    """A Postgres text column cannot hold `\\0`, so the insert would raise and
    the student would get a 500. Python refuses such a file anyway ("source
    code cannot contain null bytes"): the honest answer is a 422, now."""
    await add_case(api_client, exercise, owner, is_hidden=False)

    response = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/{route}",
        json={"code": "print(1)\x00"},
        headers=student,
    )

    assert response.status_code == 422, response.text


async def test_a_nul_byte_in_what_the_instructor_writes_is_refused(
    api_client: AsyncClient, lesson: dict, exercise: dict, owner: dict[str, str]
):
    """Same column type, same 500 -- on the authoring side."""
    case = await add_case(api_client, exercise, owner)
    writes = [
        ("post", f"/api/v1/code-exercises/{exercise['id']}/test-cases",
         {"input": "1\x00", "expected_output": "3\n"}),
        ("post", f"/api/v1/code-exercises/{exercise['id']}/test-cases",
         {"input": "", "expected_output": "3\x00"}),
        ("patch", f"/api/v1/test-cases/{case['id']}", {"input": "\x00"}),
        ("patch", f"/api/v1/test-cases/{case['id']}", {"expected_output": "\x00"}),
        ("patch", f"/api/v1/code-exercises/{exercise['id']}", {"starter_code": "\x00"}),
        ("patch", f"/api/v1/code-exercises/{exercise['id']}", {"statement_md": "Đề\x00"}),
    ]

    for method, url, body in writes:
        response = await getattr(api_client, method)(url, json=body, headers=owner)
        assert response.status_code == 422, (method, url, body, response.text)


async def test_the_history_is_newest_first_and_paged(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str], student: dict[str, str]
):
    await add_case(api_client, exercise, owner)
    for attempt in range(3):
        await api_client.post(
            f"/api/v1/code-exercises/{exercise['id']}/submissions",
            json={"code": f"print({attempt})"},
            headers=student,
        )

    response = await api_client.get(
        f"/api/v1/code-exercises/{exercise['id']}/submissions?page=1&page_size=2",
        headers=student,
    )

    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_the_history_holds_only_your_own_attempts(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    lesson: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    await add_case(api_client, exercise, owner)
    await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print('mine')"},
        headers=student,
    )

    classmate_user = await make_user(db_session, "student")
    db_session.add(
        Enrollment(user_id=classmate_user.id, course_id=uuid.UUID(lesson["course_id"]))
    )
    await db_session.flush()
    classmate = await sign_in(api_client, classmate_user)

    response = await api_client.get(
        f"/api/v1/code-exercises/{exercise['id']}/submissions", headers=classmate
    )

    assert response.json()["total"] == 0


async def test_a_submission_is_readable_by_its_author_and_by_the_owner(
    api_client: AsyncClient, exercise: dict, owner: dict[str, str], student: dict[str, str]
):
    """The instructor's view is what makes "why was I marked wrong?" answerable."""
    await add_case(api_client, exercise, owner)
    submission = (
        await api_client.post(
            f"/api/v1/code-exercises/{exercise['id']}/submissions",
            json={"code": "print('xin chao')"},
            headers=student,
        )
    ).json()

    for headers in (student, owner):
        response = await api_client.get(
            f"/api/v1/submissions/{submission['id']}", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["code"] == "print('xin chao')"
        assert response.json()["results"] == []


async def test_a_stranger_is_told_the_submission_does_not_exist(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    lesson: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    """404 rather than 403: that a given submission id exists is not their business."""
    await add_case(api_client, exercise, owner)
    submission = (
        await api_client.post(
            f"/api/v1/code-exercises/{exercise['id']}/submissions",
            json={"code": "print(1)"},
            headers=student,
        )
    ).json()

    classmate_user = await make_user(db_session, "student")
    db_session.add(
        Enrollment(user_id=classmate_user.id, course_id=uuid.UUID(lesson["course_id"]))
    )
    await db_session.flush()
    classmate = await sign_in(api_client, classmate_user)

    response = await api_client.get(
        f"/api/v1/submissions/{submission['id']}", headers=classmate
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SUBMISSION_NOT_FOUND"


# --- Not too fast ----------------------------------------------------------
#
# Grading is the most expensive thing a student can ask this platform to do:
# one submission is several containers and several seconds of a core. The
# limit exists to keep one person in a loop from being paid for by everyone
# waiting behind them.


@pytest.fixture
def limiter(app, api_client: AsyncClient) -> MemoryRateLimiter:
    """The real rules on a clock the test moves, instead of the allow-all one.

    Depends on `api_client` so it is always installed *after* the allow-all
    override that fixture sets up -- otherwise the order would decide which
    limiter is in play, and a test expecting a refusal would quietly get one
    that never refuses.
    """
    limiter = MemoryRateLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    return limiter


async def submit(client: AsyncClient, exercise: dict, headers: dict[str, str]):
    return await client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print(1)"},
        headers=headers,
    )


async def test_a_second_submission_straight_away_is_refused(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    limiter: MemoryRateLimiter,
):
    await add_case(api_client, exercise, owner)
    assert (await submit(api_client, exercise, student)).status_code == 201

    response = await submit(api_client, exercise, student)

    assert response.status_code == 429
    body = response.json()["detail"]
    assert body["code"] == "SUBMISSION_RATE_LIMITED"
    # Both places, on purpose: the header is what a proxy or curl already
    # understands, the body field is for the page that draws a countdown.
    assert response.headers["Retry-After"] == str(body["retry_after"])
    assert 0 < body["retry_after"] <= 60


async def test_a_refused_submission_reaches_neither_the_table_nor_the_queue(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    queued: list,
    limiter: MemoryRateLimiter,
):
    """The whole point. A 429 that still wrote a row and still queued a job
    would cost exactly what it was meant to save."""
    await add_case(api_client, exercise, owner)
    await submit(api_client, exercise, student)

    await submit(api_client, exercise, student)

    rows = (
        await db_session.scalars(
            select(Submission).where(
                Submission.exercise_id == uuid.UUID(exercise["id"])
            )
        )
    ).all()
    assert len(rows) == 1
    assert len(queued) == 1


async def test_the_wait_ends(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    limiter: MemoryRateLimiter,
):
    await add_case(api_client, exercise, owner)
    await submit(api_client, exercise, student)

    limiter.now += get_settings().submission_cooldown_seconds

    assert (await submit(api_client, exercise, student)).status_code == 201


async def test_one_student_waiting_does_not_make_another_wait(
    api_client: AsyncClient,
    db_session: AsyncSession,
    lesson: dict,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    limiter: MemoryRateLimiter,
):
    await add_case(api_client, exercise, owner)
    await submit(api_client, exercise, student)

    other = await make_user(db_session, "student")
    db_session.add(
        Enrollment(user_id=other.id, course_id=uuid.UUID(lesson["course_id"]))
    )
    await db_session.flush()
    classmate = await sign_in(api_client, other)

    assert (await submit(api_client, exercise, classmate)).status_code == 201


async def test_the_cooldown_is_per_exercise(
    api_client: AsyncClient,
    lesson: dict,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    limiter: MemoryRateLimiter,
):
    """Waiting on one problem is what the cooldown is for; being unable to
    start a different one is not. Moving to another exercise is not the
    behaviour this guards against -- the hourly quota below is."""
    await add_case(api_client, exercise, owner)
    await submit(api_client, exercise, student)

    section = (
        await api_client.get(f"/api/v1/lessons/{lesson['id']}", headers=owner)
    ).json()["section_id"]
    second_lesson = (
        await api_client.post(
            f"/api/v1/sections/{section}/lessons",
            json={"title": "Bài tập 2", "type": "code_exercise"},
            headers=owner,
        )
    ).json()
    second = (
        await api_client.post(
            f"/api/v1/lessons/{second_lesson['id']}/code-exercise",
            json={"statement_md": "Bài tập thứ hai."},
            headers=owner,
        )
    ).json()
    await add_case(api_client, second, owner)

    assert (await submit(api_client, second, student)).status_code == 201


async def test_the_hourly_quota_stops_a_script_that_waits_the_cooldown_out(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    limiter: MemoryRateLimiter,
    monkeypatch: pytest.MonkeyPatch,
):
    """A cooldown alone is only a speed limit; patience walks around it.

    Two here instead of the real forty so the test is three requests rather
    than forty-one -- the rule under test is the same one.
    """
    monkeypatch.setattr(get_settings(), "submission_hourly_limit", 2)
    await add_case(api_client, exercise, owner)

    for _ in range(2):
        assert (await submit(api_client, exercise, student)).status_code == 201
        limiter.now += get_settings().submission_cooldown_seconds

    response = await submit(api_client, exercise, student)

    assert response.status_code == 429
    body = response.json()["detail"]
    assert body["code"] == "SUBMISSION_RATE_LIMITED"
    # An hour, near enough: what matters is that it is not the ten seconds of
    # the cooldown, so the message cannot be telling them the wrong thing.
    assert body["retry_after"] > 60

# --- What the database refuses, whatever the worker sends ------------------


async def test_a_verdict_cannot_be_written_before_the_grading_is_done(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    """A row saying "still running, wrong answer" is a bug a student would read.

    The worker is what will write these columns, and the check constraint is
    what makes a bug in it fail loudly at the moment it happens instead of
    quietly showing a verdict for grading that never finished.
    """
    await add_case(api_client, exercise, owner)
    created = (
        await api_client.post(
            f"/api/v1/code-exercises/{exercise['id']}/submissions",
            json={"code": "print(1)"},
            headers=student,
        )
    ).json()

    submission = await db_session.get(Submission, uuid.UUID(created["id"]))
    submission.status = "running"
    submission.verdict = "WA"

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_deleting_an_exercise_takes_its_cases_and_submissions_with_it(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    await add_case(api_client, exercise, owner)
    await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print(1)"},
        headers=student,
    )

    response = await api_client.delete(
        f"/api/v1/code-exercises/{exercise['id']}", headers=owner
    )
    assert response.status_code == 204

    exercise_id = uuid.UUID(exercise["id"])
    assert await db_session.get(CodeExercise, exercise_id) is None
    assert (
        await db_session.scalars(
            select(TestCase).where(TestCase.exercise_id == exercise_id)
        )
    ).all() == []
    assert (
        await db_session.scalars(
            select(Submission).where(Submission.exercise_id == exercise_id)
        )
    ).all() == []


# --- What a watching socket is allowed to read -----------------------------


async def test_a_snapshot_says_how_far_the_grading_has_got(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    student_user: User,
):
    """The snapshot is what makes the live channel safe to lose.

    It is read from the rows, so it is true whether or not a single event was
    ever delivered -- and it counts finished cases by counting the rows that
    exist, rather than by trusting a number somebody remembered to increment.
    """
    submission_id = await graded_submission(
        api_client, db_session, exercise, owner, student
    )

    event = await grading_events.snapshot_for(
        db_session, uuid.UUID(submission_id), student_user
    )

    assert event.type == "snapshot"
    assert event.status == "done"
    assert event.total_cases == 2
    assert event.completed_cases == 2
    assert event.verdict == "WA"
    assert event.is_terminal


async def test_a_snapshot_of_a_submission_nobody_has_graded_yet_counts_zero(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    student_user: User,
):
    """Pending, with the denominator already known.

    The number of cases comes from the exercise, not from the run, so a page
    can say "0/8" before the worker has picked the job up -- which is the
    difference between a progress bar and a spinner.
    """
    await add_case(api_client, exercise, owner)
    await add_case(api_client, exercise, owner)
    created = await api_client.post(
        f"/api/v1/code-exercises/{exercise['id']}/submissions",
        json={"code": "print(3)"},
        headers=student,
    )

    event = await grading_events.snapshot_for(
        db_session, uuid.UUID(created.json()["id"]), student_user
    )

    assert event.status == "pending"
    assert event.total_cases == 2
    assert event.completed_cases == 0
    assert not event.is_terminal


async def test_a_stranger_gets_no_snapshot_to_watch(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    """Watching is reading, so it is refused by the same function.

    A socket with no snapshot is never accepted, which means there is no state
    in which someone is subscribed to a channel for a submission they were
    never allowed to see.
    """
    submission_id = await graded_submission(
        api_client, db_session, exercise, owner, student
    )
    outsider = await make_user(db_session, "student")

    assert (
        await grading_events.snapshot_for(
            db_session, uuid.UUID(submission_id), outsider
        )
        is None
    )


async def test_the_instructor_may_watch_a_submission_to_their_own_exercise(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    owner_user: User,
    student: dict[str, str],
):
    submission_id = await graded_submission(
        api_client, db_session, exercise, owner, student
    )

    event = await grading_events.snapshot_for(
        db_session, uuid.UUID(submission_id), owner_user
    )

    assert event is not None
    assert event.status == "done"


async def test_no_snapshot_carries_an_answer_key(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    owner_user: User,
    student: dict[str, str],
):
    """The same scan as the REST endpoint's, against the live channel's shape.

    The submission below was graded on a hidden case whose input, expected
    output and captured stdout are all secrets. The *instructor* reads the
    snapshot here, deliberately: they are the caller with the most rights, so
    if even their snapshot is clean, no viewer of this channel gets an answer.
    """
    submission_id = await graded_submission(
        api_client, db_session, exercise, owner, student
    )

    event = await grading_events.snapshot_for(
        db_session, uuid.UUID(submission_id), owner_user
    )
    payload = event.model_dump_json()

    assert SECRET_ANSWER not in payload
    assert SECRET_INPUT not in payload
    assert SECRET_STDOUT not in payload


async def test_polling_and_watching_agree_on_the_same_numbers(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    student_user: User,
):
    """A fallback is only a fallback if it answers the same question.

    A client whose WebSocket failed polls this endpoint instead, and it has to
    be able to render the same thing: the same status, the same verdict, and
    the same "n of m" -- which is why the denominator was added to the REST
    response rather than left as something only a live event carries.
    """
    submission_id = await graded_submission(
        api_client, db_session, exercise, owner, student
    )

    polled = (
        await api_client.get(f"/api/v1/submissions/{submission_id}", headers=student)
    ).json()
    watched = await grading_events.snapshot_for(
        db_session, uuid.UUID(submission_id), student_user
    )

    assert polled["total_cases"] == watched.total_cases == 2
    assert len(polled["results"]) == watched.completed_cases
    assert polled["status"] == watched.status
    assert polled["verdict"] == watched.verdict
    assert polled["score"] == watched.score


# --- Chạy thử: a run that does not count ------------------------------------


async def trial(client: AsyncClient, exercise: dict, headers: dict[str, str]):
    return await client.post(
        f"/api/v1/code-exercises/{exercise['id']}/trial-runs",
        json={"code": "print(1)"},
        headers=headers,
    )


async def test_a_trial_run_is_accepted_and_marked_as_one(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    await add_case(api_client, exercise, owner, is_hidden=False)

    response = await trial(api_client, exercise, student)

    assert response.status_code == 201, response.text
    assert response.json()["is_trial"] is True
    assert response.json()["status"] == "pending"


async def test_a_trial_run_stays_out_of_the_history(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    """History is the record of what was handed in.

    Both rows below exist and both are readable one at a time; only the real
    submission is part of the record. A page of forty rehearsals is not a
    history of anything.
    """
    await add_case(api_client, exercise, owner, is_hidden=False)
    trial_id = (await trial(api_client, exercise, student)).json()["id"]
    real_id = (await submit(api_client, exercise, student)).json()["id"]

    listed = await api_client.get(
        f"/api/v1/code-exercises/{exercise['id']}/submissions", headers=student
    )
    ids = [row["id"] for row in listed.json()["items"]]

    assert ids == [real_id]
    assert listed.json()["total"] == 1
    # Still readable on its own -- the page has to be able to show its result.
    assert (
        await api_client.get(f"/api/v1/submissions/{trial_id}", headers=student)
    ).status_code == 200


async def test_a_trial_run_needs_something_to_run_against(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
):
    """An exercise of hidden cases only can be submitted to, not rehearsed.

    Its own code rather than `EXERCISE_NOT_READY`: nothing is wrong with the
    exercise, so the page disables one button instead of showing an error.
    """
    await add_case(api_client, exercise, owner, is_hidden=True)

    response = await trial(api_client, exercise, student)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "NO_SAMPLE_TEST_CASES"


async def test_a_trial_run_counts_only_the_sample_cases(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    student_user: User,
):
    """The denominator has to describe this run, on both paths.

    A trial that reported "0/3" while running one sample case would be telling
    the student about a submission that is not happening.
    """
    await add_case(api_client, exercise, owner, is_hidden=False)
    await add_case(api_client, exercise, owner, is_hidden=True)
    await add_case(api_client, exercise, owner, is_hidden=True)
    trial_id = (await trial(api_client, exercise, student)).json()["id"]

    polled = await api_client.get(f"/api/v1/submissions/{trial_id}", headers=student)
    watched = await grading_events.snapshot_for(
        db_session, uuid.UUID(trial_id), student_user
    )

    assert polled.json()["total_cases"] == 1
    assert watched.total_cases == 1


async def test_a_student_may_not_run_an_exercise_they_cannot_open(
    api_client: AsyncClient,
    db_session: AsyncSession,
    exercise: dict,
    owner: dict[str, str],
):
    """Trial runs go through the same door as everything else on the lesson."""
    outsider = await sign_in(api_client, await make_user(db_session, "student"))
    await add_case(api_client, exercise, owner, is_hidden=False)

    assert (await trial(api_client, exercise, outsider)).status_code == 403


async def test_rehearsing_does_not_block_submitting(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    limiter: MemoryRateLimiter,
):
    """The sequence the page teaches must not be the sequence the limit bans.

    Try the samples, then hand it in. One shared cooldown would answer that
    with 429 and leave a student staring at a countdown for doing exactly what
    the buttons invite.
    """
    await add_case(api_client, exercise, owner, is_hidden=False)

    assert (await trial(api_client, exercise, student)).status_code == 201
    assert (await submit(api_client, exercise, student)).status_code == 201


async def test_two_trial_runs_in_a_row_are_still_refused(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    limiter: MemoryRateLimiter,
):
    """A trial costs the queue exactly what a submission costs it."""
    await add_case(api_client, exercise, owner, is_hidden=False)

    assert (await trial(api_client, exercise, student)).status_code == 201
    refused = await trial(api_client, exercise, student)

    assert refused.status_code == 429
    assert refused.json()["detail"]["code"] == "SUBMISSION_RATE_LIMITED"
    # Named after the button that was pressed: "bạn vừa nộp bài" sends someone
    # who clicked "chạy thử" to look for a submission that does not exist.
    assert "chạy thử" in refused.json()["detail"]["message"]


async def test_trial_runs_and_submissions_share_the_hourly_quota(
    api_client: AsyncClient,
    exercise: dict,
    owner: dict[str, str],
    student: dict[str, str],
    limiter: MemoryRateLimiter,
):
    """The gate that actually protects the queue counts both.

    Otherwise the hourly limit is worth nothing: a script that alternates
    between the two routes would walk straight around it while costing the
    same containers.
    """
    await add_case(api_client, exercise, owner, is_hidden=False)
    settings = get_settings()

    used = 0
    while used < settings.submission_hourly_limit:
        # Past the cooldown each time, so only the hourly quota can refuse.
        limiter.now += settings.submission_cooldown_seconds + 1
        route = trial if used % 2 == 0 else submit
        assert (await route(api_client, exercise, student)).status_code == 201
        used += 1

    limiter.now += settings.submission_cooldown_seconds + 1
    refused = await trial(api_client, exercise, student)

    assert refused.status_code == 429
    assert refused.json()["detail"]["retry_after"] > 0
