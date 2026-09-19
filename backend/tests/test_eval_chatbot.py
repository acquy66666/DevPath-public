"""How the chatbot evaluation marks an answer, and the question set it marks.

The marking is what the thesis quotes, so it is tested like code: an answer
that covers every point but cites nothing is not a pass, a refusal that still
cites a lesson is not a clean refusal, and a line of code the course never
showed is flagged even when the prose around it is cited. No model and no
database here -- `scripts/eval_chatbot.py` runs those live.
"""

import re

import pytest

from app.services.chat import NO_MATERIAL_ANSWER
from scripts.eval_chatbot import (
    QUESTIONS,
    Question,
    code_outside_material,
    grade,
    is_refusal,
    load_questions,
)
from scripts.seed_courses import COURSES

MATERIAL = '`input()` luôn trả về chuỗi. `int("12")` cho ra 12.\n\ntuoi = int(input("Tuổi: ")) + 1'


def question(**overrides) -> Question:
    fields = {
        "id": "q01",
        "kind": "trong-pham-vi",
        "text": "Vì sao input() + 1 bị lỗi?",
        "expect": "answer",
        "lessons": ["Ép kiểu"],
        "must_match": ["chuỗi", r"int\("],
        "session": None,
        "note": "",
    }
    fields.update(overrides)
    return Question(**fields)


REFUSE = question(expect="refuse", lessons=[], must_match=[], kind="ngoai-pham-vi")


# --- Refusals -----------------------------------------------------------------


def test_a_refusal_is_recognised_by_what_the_prompt_tells_the_model_to_say():
    assert is_refusal("Nội dung này nằm ngoài phạm vi tài liệu của khóa học.")
    assert is_refusal("Xin lỗi, câu hỏi này không có trong tài liệu của khóa học.")
    assert is_refusal(NO_MATERIAL_ANSWER)
    assert not is_refusal("`input()` luôn trả về chuỗi [1].")


def test_a_clean_refusal_passes():
    result = grade(
        REFUSE,
        answer="Nội dung này nằm ngoài phạm vi tài liệu của khóa học.",
        sources=["Ép kiểu", "Biến"],
        cited=[],
        material=MATERIAL,
    )
    assert result.refused
    assert result.verdict == "đạt"


def test_a_refusal_that_still_cites_a_lesson_is_its_own_failure():
    """The prompt's rule 3: refuse, and cite nothing. A refusal that points at
    a lesson sends the student there for something it does not contain."""
    result = grade(
        REFUSE,
        answer="Nội dung này nằm ngoài phạm vi tài liệu. Bạn xem bài Biến [2] nhé.",
        sources=["Ép kiểu", "Biến"],
        cited=["Biến"],
        material=MATERIAL,
    )
    assert not result.refused
    assert result.verdict == "từ chối nhưng vẫn trích nguồn"


def test_answering_what_should_have_been_refused_fails():
    result = grade(
        REFUSE,
        answer="Decorator là hàm nhận một hàm và trả về hàm khác.",
        sources=["Ép kiểu"],
        cited=[],
        material=MATERIAL,
    )
    assert result.verdict == "lẽ ra phải từ chối"


def test_refusing_an_answerable_question_fails():
    result = grade(
        question(),
        answer="Nội dung này nằm ngoài phạm vi tài liệu của khóa học.",
        sources=["Ép kiểu"],
        cited=[],
        material=MATERIAL,
    )
    assert result.verdict == "từ chối nhầm"


# --- Answers ------------------------------------------------------------------


def test_an_answer_that_covers_every_point_and_cites_the_right_lesson_passes():
    result = grade(
        question(),
        answer="`input()` luôn trả về chuỗi [1], nên phải ép bằng `int(...)` [1].",
        sources=["Ép kiểu", "Biến"],
        cited=["Ép kiểu"],
        material=MATERIAL,
    )
    assert result.verdict == "đạt"
    assert result.missing == []
    assert result.gold_rank == 1


def test_points_are_matched_ignoring_case():
    result = grade(
        question(must_match=["PATH"]),
        answer="Bạn quên đánh dấu ô Add python.exe to path [1].",
        sources=["Ép kiểu"],
        cited=["Ép kiểu"],
        material=MATERIAL,
    )
    assert result.missing == []


def test_a_missing_point_is_named():
    result = grade(
        question(),
        answer="`input()` luôn trả về chuỗi [1].",
        sources=["Ép kiểu"],
        cited=["Ép kiểu"],
        material=MATERIAL,
    )
    assert result.verdict == "thiếu ý"
    assert result.missing == [r"int\("]


def test_every_point_but_no_citation_is_not_a_pass():
    result = grade(
        question(),
        answer="`input()` luôn trả về chuỗi, nên phải ép bằng `int(...)`.",
        sources=["Ép kiểu"],
        cited=[],
        material=MATERIAL,
    )
    assert result.verdict == "không trích nguồn"


def test_citing_only_other_lessons_is_a_wrong_citation():
    result = grade(
        question(),
        answer="`input()` luôn trả về chuỗi [2], nên phải ép bằng `int(...)` [2].",
        sources=["Ép kiểu", "Biến"],
        cited=["Biến"],
        material=MATERIAL,
    )
    assert result.verdict == "trích sai bài"


def test_any_gold_lesson_is_enough_for_a_question_that_spans_two():
    result = grade(
        question(lessons=["Biến", "Câu lệnh if"], must_match=["gán", "so sánh"]),
        answer="= là phép gán [1], == là phép so sánh [1].",
        sources=["Câu lệnh if", "Biến"],
        cited=["Câu lệnh if"],
        material=MATERIAL,
    )
    assert result.verdict == "đạt"
    assert result.gold_rank == 1


def test_the_rank_is_of_the_first_gold_lesson_among_the_sources():
    result = grade(
        question(),
        answer="…",
        sources=["Biến", "Hàm", "Ép kiểu"],
        cited=[],
        material=MATERIAL,
    )
    assert result.gold_rank == 3

    missed = grade(question(), answer="…", sources=["Biến"], cited=[], material=MATERIAL)
    assert missed.gold_rank is None


# --- Code the course never showed -----------------------------------------------


def test_code_the_material_contains_is_not_flagged():
    answer = 'Ví dụ [1]:\n\n```python\ntuoi = int(input("Tuổi: ")) + 1\n```'
    assert code_outside_material(answer, MATERIAL) == []


def test_lines_the_material_lacks_are_flagged_one_by_one():
    answer = (
        "```python\n"
        'tuoi   =   int(input("Tuổi: ")) + 1\n'  # spacing is not content
        "# chú thích do model tự thêm\n"  # a comment is not code
        "\n"
        "print(tuoi)\n"
        "```"
    )
    assert code_outside_material(answer, MATERIAL) == ["print(tuoi)"]


def test_inline_code_is_prose_and_not_checked():
    """`int()` inline is a word in a sentence, not an example program."""
    assert code_outside_material("Dùng `float(x)` trước [1].", MATERIAL) == []


def test_an_unclosed_block_at_the_end_is_still_read():
    assert code_outside_material("```python\nprint(1)", MATERIAL) == ["print(1)"]


# --- The question set ----------------------------------------------------------


def test_the_question_set_is_twenty_questions_with_unique_ids():
    questions = load_questions(QUESTIONS)
    assert len(questions) == 20
    assert len({q.id for q in questions}) == 20


def test_every_answerable_question_says_where_the_answer_is_and_what_it_must_say():
    for q in load_questions(QUESTIONS):
        if q.expect == "answer":
            assert q.lessons and q.must_match, q.id
            for pattern in q.must_match:
                re.compile(pattern)
        else:
            assert q.expect == "refuse", q.id
            assert not q.lessons and not q.must_match, q.id


def test_the_gold_lessons_are_lessons_of_the_evaluated_course():
    """A renamed lesson would turn every hit on it into a miss, silently."""
    data = load_questions(QUESTIONS)
    python = next(c for c in COURSES if c.slug == "python-co-ban-cho-nguoi-moi-bat-dau")
    titles = {lesson.title for section in python.sections for lesson in section.lessons}

    for q in data:
        assert set(q.lessons) <= titles, q.id


def test_both_kinds_of_question_are_well_represented():
    questions = load_questions(QUESTIONS)
    refusals = [q for q in questions if q.expect == "refuse"]
    assert 5 <= len(refusals) <= 8
    # A follow-up is only a follow-up after the question it follows.
    sessions = {}
    for q in questions:
        if q.session:
            sessions.setdefault(q.session, []).append(q.id)
    assert any(len(ids) >= 2 for ids in sessions.values())


@pytest.mark.parametrize("bad", ["", "chat"])
def test_an_unknown_expectation_is_refused(tmp_path, bad):
    path = tmp_path / "q.json"
    path.write_text(
        '{"course": "c", "student": "s", "questions": [{"id": "q1", "kind": "k", '
        f'"text": "t", "expect": "{bad}"'
        "}]}",
        "utf-8",
    )
    with pytest.raises(SystemExit):
        load_questions(path)
