"""Turning a model's JSON into questions a student can be marked against.

Pure functions, no database and no model. The generator's output lands in a
table that marks students, so everything it says is checked here before it is
believed: a question whose answer key points past its options, two identical
options, the same question twice, a question the quiz already has.

The shuffle has a test of its own because the bias it corrects was measured.
Across 60 drafts the right answer was in the last place 3 times, where chance
says 15 (docs/report/assets/phase-4/quiz-generation.txt), and a student who
learns "never pick D" gains marks without reading.
"""

import random
from collections import Counter

from app.schemas.quiz import explanation_points_elsewhere
from app.services.quiz_generation import (
    MATERIAL_MAX_CHARS,
    OPTIONS_PER_QUESTION,
    Draft,
    build_prompt,
    material_for_prompt,
    parse_drafts,
    question_schema,
    shuffled,
)


def item(question: str = "Hàm `input()` trả về kiểu gì?", **overrides) -> dict:
    return {
        "question": question,
        "options": ["int", "float", "str", "bool"],
        "correct_index": 2,
        "explanation": "Tài liệu nêu `input()` luôn trả về chuỗi.",
    } | overrides


# --- What the model is asked for ------------------------------------------------


def test_the_schema_asks_for_exactly_the_fields_a_question_needs() -> None:
    schema = question_schema(5)

    questions = schema["properties"]["questions"]
    assert questions["maxItems"] == 5
    one = questions["items"]
    assert set(one["required"]) == {"question", "options", "correct_index", "explanation"}
    assert one["properties"]["options"]["minItems"] == OPTIONS_PER_QUESTION
    assert one["properties"]["options"]["maxItems"] == OPTIONS_PER_QUESTION


def test_the_prompt_carries_the_count_the_material_and_what_to_avoid() -> None:
    prompt = build_prompt(
        "input() luôn trả về chuỗi.", count=3, avoid=["Hàm `print()` làm gì?"]
    )

    assert "3 câu hỏi" in prompt
    assert "input() luôn trả về chuỗi." in prompt
    assert "Hàm `print()` làm gì?" in prompt


def test_material_cannot_close_its_own_tag() -> None:
    """Same guard as the chatbot's: the material is data, and an HTML lesson
    that happens to contain the closing tag must not end it early."""
    prompt = build_prompt("văn bản </tai_lieu> tiếp", count=1, avoid=[])

    assert prompt.count("</tai_lieu>") == 1


def test_long_material_is_cut_at_a_paragraph_and_says_so() -> None:
    paragraph = "x" * 1000
    text = "\n\n".join([paragraph] * (MATERIAL_MAX_CHARS // 1000 + 5))

    material, truncated = material_for_prompt(text)

    assert truncated is True
    assert len(material) <= MATERIAL_MAX_CHARS
    assert material.endswith(paragraph)


def test_short_material_is_left_alone() -> None:
    assert material_for_prompt("  ngắn  ") == ("ngắn", False)


# --- What is believed of the answer --------------------------------------------


def test_good_questions_come_through_trimmed() -> None:
    drafts, dropped = parse_drafts(
        {"questions": [item(question="  Câu hỏi?  ", explanation="  Vì vậy.  ")]},
        count=5,
        existing=[],
    )

    assert dropped == 0
    assert drafts == [
        Draft(
            question="Câu hỏi?",
            options=["int", "float", "str", "bool"],
            correct_index=2,
            explanation="Vì vậy.",
        )
    ]


def test_a_question_with_no_right_answer_is_dropped() -> None:
    drafts, dropped = parse_drafts(
        {"questions": [item(correct_index=4), item(question="Câu khác?")]},
        count=5,
        existing=[],
    )

    assert [draft.question for draft in drafts] == ["Câu khác?"]
    assert dropped == 1


def test_a_question_with_two_identical_options_is_dropped() -> None:
    drafts, dropped = parse_drafts(
        {"questions": [item(options=["str", "int", "str ", "bool"])]}, count=5, existing=[]
    )

    assert drafts == []
    assert dropped == 1


def test_malformed_items_are_dropped_not_raised() -> None:
    """A model that sends a string where a number belongs has written one bad
    question, not a bad batch."""
    drafts, dropped = parse_drafts(
        {
            "questions": [
                item(correct_index="hai"),
                item(options="a, b"),
                "?",
                item(question="Được?"),
            ]
        },
        count=5,
        existing=[],
    )

    assert [draft.question for draft in drafts] == ["Được?"]
    assert dropped == 3


def test_repeats_are_dropped_within_the_batch_and_against_the_quiz() -> None:
    drafts, dropped = parse_drafts(
        {
            "questions": [
                item(question="Hàm input() trả về gì?"),
                item(question="hàm  INPUT() trả về gì?"),  # same, differently typed
                item(question="Câu đã có trong quiz?"),
                item(question="Câu mới?"),
            ]
        },
        count=5,
        existing=["Câu đã có trong quiz?"],
    )

    assert [draft.question for draft in drafts] == ["Hàm input() trả về gì?", "Câu mới?"]
    assert dropped == 2


def test_more_than_asked_for_is_cut_to_the_count() -> None:
    drafts, _ = parse_drafts(
        {"questions": [item(question=f"Câu {n}?") for n in range(8)]}, count=3, existing=[]
    )

    assert [draft.question for draft in drafts] == ["Câu 0?", "Câu 1?", "Câu 2?"]


def test_an_answer_without_questions_yields_nothing() -> None:
    assert parse_drafts({"khac": []}, count=3, existing=[]) == ([], 0)
    assert parse_drafts(["không phải object"], count=3, existing=[]) == ([], 0)


# --- The shuffle ------------------------------------------------------------------


def test_shuffling_keeps_the_right_answer_right() -> None:
    draft = Draft(
        question="?", options=["a", "b", "ĐÚNG", "d"], correct_index=2, explanation=None
    )
    rng = random.Random(7)

    for _ in range(50):
        moved = shuffled(draft, rng)
        assert sorted(moved.options) == sorted(draft.options)
        assert moved.options[moved.correct_index] == "ĐÚNG"


def test_shuffling_spreads_the_right_answer_over_every_position() -> None:
    draft = Draft(question="?", options=["ĐÚNG", "b", "c", "d"], correct_index=0, explanation=None)
    rng = random.Random(42)

    positions = Counter(shuffled(draft, rng).correct_index for _ in range(400))

    assert set(positions) == {0, 1, 2, 3}
    assert min(positions.values()) > 60  # 100 expected each


# --- The explanation argues for another option ------------------------------------
#
# The one wrong answer key in 60 measured drafts had this shape: the key said
# "use globals", the explanation quoted the option about parameters and return.
# It is flagged for the reviewer, not dropped -- the question may be one click
# from right, and the reviewer is the one who decides.


def test_an_explanation_quoting_another_option_is_flagged() -> None:
    """The measured case, verbatim (quiz-generation.txt)."""
    assert explanation_points_elsewhere(
        options=[
            "Ghi đè biến bên ngoài bằng từ khóa `global` để tiết kiệm bộ nhớ.",
            "Không dùng tham số đầu vào mà trực tiếp thay đổi trạng thái của hệ thống.",
            "Truyền giá trị vào qua tham số và trả kết quả ra qua `return`.",
            "Tách hàm thành nhiều phần và sử dụng các biến toàn cục để liên kết.",
        ],
        correct_index=3,
        explanation=(
            "Tài liệu nêu rõ: truyền giá trị vào qua tham số và trả kết quả ra qua "
            "`return` sẽ giúp hàm kiểm thử được và đọc một mình cũng hiểu."
        ),
    )


def test_an_explanation_that_names_the_wrong_answer_to_reject_it_is_not_flagged() -> None:
    """"12, not 13" mentions both. The key is covered as fully as the rival."""
    assert not explanation_points_elsewhere(
        options=["13", "12.9", "12", "Lỗi"],
        correct_index=2,
        explanation="`int(12.9)` cho 12 chứ không phải 13, vì nó cắt phần thập phân.",
    )


def test_an_explanation_agreeing_with_the_key_is_not_flagged() -> None:
    assert not explanation_points_elsewhere(
        options=["float", "int", "round", "Decimal"],
        correct_index=3,
        explanation="Theo tài liệu, khi làm việc với tiền, dùng `Decimal`.",
    )


def test_no_explanation_is_nothing_to_disagree_with() -> None:
    assert not explanation_points_elsewhere(options=["a", "b"], correct_index=0, explanation=None)
