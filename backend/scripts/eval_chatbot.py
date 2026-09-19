"""Put the course assistant through its 20 questions and mark the answers.

    python -m scripts.eval_chatbot                 # 3 runs of the 20 questions
    python -m scripts.eval_chatbot --runs 1
    python -m scripts.eval_chatbot --scores-only   # retrieval scores, no model call
    python -m scripts.eval_chatbot --keep          # leave the conversations in the UI

The questions are `scripts/eval_data/chatbot_questions.json`: 14 the course
answers (with the lesson that answers each and what the answer must say) and 6
it must refuse. Each is asked as a student would ask it -- through
`services.chat.prepare_answer` and `answer_events`, the two halves of
`POST /chat-sessions/{id}/messages`, with the real embedder, the real model and
the real database -- so what is marked is what a student gets. Questions that
share a `session` are asked one after another in one conversation.

The model does not answer the same question the same way twice, so the set is
asked `--runs` times, each run in fresh conversations, and every rate in the
report is out of all of them. One run is an anecdote.

Marking (`grade`) is mechanical, so it can be rerun and argued with:

* **answer**: not a refusal, every `must_match` pattern present, at least one
  of the expected lessons cited. Patterns are the facts the course states, not
  phrasings -- "3.5" or "3,5", not a sentence.
* **refuse**: the refusal the system prompt asks for, and no citation.
* separately, every line of code in the answer that is not in the material the
  model was given -- the model writing examples of its own (chat-ui.txt §6).

A mechanical mark reads words, not meaning, so the evidence file also records
a person reading the answers; the disagreements are the interesting part.

The file also holds `probes`: ways students really ask (no diacritics, English,
one word) and near misses (Java instead of Python). They are only embedded and
searched -- no model call, no marking -- because what they answer is where a
refusal threshold could sit without refusing a real question.

The rate limiter is bypassed (this is not a student) and `--pause` spaces the
calls instead. Conversations are deleted afterwards unless `--keep`. Output is
Markdown on stdout, progress on stderr:

    docker compose -f infra/docker-compose.yml exec -T backend \\
        python -m scripts.eval_chatbot > docs/report/assets/phase-4/chatbot-eval.md
"""

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.exceptions import DomainError
from app.models import Course, CourseSection, DocChunk, Lesson, User
from app.services import chat
from app.services.llm import Embedder, build_chat_model, build_embedder

QUESTIONS = Path(__file__).parent / "eval_data" / "chatbot_questions.json"

EXPECTATIONS = ("answer", "refuse")


# --- The question set -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    kind: str
    text: str
    expect: str
    lessons: list[str]
    must_match: list[str]
    session: str | None
    note: str


@dataclass(frozen=True, slots=True)
class Probe:
    """A question only searched for, never asked."""

    id: str
    text: str
    expect: str
    note: str


@dataclass(frozen=True, slots=True)
class Suite:
    course: str
    student: str
    questions: list[Question]
    probes: list[Probe] = field(default_factory=list)


def _expectation(raw: dict) -> str:
    if raw.get("expect") not in EXPECTATIONS:
        raise SystemExit(f"{raw.get('id')}: expect phải là một trong {EXPECTATIONS}")
    return raw["expect"]


def load_suite(path: Path) -> Suite:
    data = json.loads(path.read_text("utf-8"))
    questions = [
        Question(
            id=raw["id"],
            kind=raw["kind"],
            text=raw["text"],
            expect=_expectation(raw),
            lessons=raw.get("lessons", []),
            must_match=raw.get("must_match", []),
            session=raw.get("session"),
            note=raw.get("note", ""),
        )
        for raw in data["questions"]
    ]
    probes = [
        Probe(id=raw["id"], text=raw["text"], expect=_expectation(raw), note=raw.get("note", ""))
        for raw in data.get("probes", [])
    ]
    return Suite(course=data["course"], student=data["student"], questions=questions, probes=probes)


def load_questions(path: Path) -> list[Question]:
    return load_suite(path).questions


# --- Marking --------------------------------------------------------------------

# What rule 3 of the system prompt tells the model to say, and what the
# service says itself when a course has no material. Deliberately wider than
# `chat.is_refusal`, which is the code under test here: the examiner should
# not share the examinee's definition of the thing it examines.
_REFUSAL = re.compile(
    r"ngoài phạm vi|không (có|nằm|được đề cập) trong (phần )?tài liệu|chưa có tài liệu",
    re.IGNORECASE,
)
# A fenced block, closed or cut off by the end of the answer. Inline `code` is
# a word in a sentence and is left to the prose.
_FENCE = re.compile(r"```[^\n]*\n(.*?)(?:```|\Z)", re.DOTALL)
_WHITESPACE = re.compile(r"\s+")


def is_refusal(answer: str) -> bool:
    return _REFUSAL.search(answer) is not None


def _squash(text: str) -> str:
    return _WHITESPACE.sub("", text)


def code_outside_material(answer: str, material: str) -> list[str]:
    """Lines of code in the answer that the material does not contain.

    Compared with all whitespace removed: a transcript loses its indentation
    on the way to the chunker, and `x=1` is the same line as `x = 1`. Comments
    are skipped -- a comment the model adds is commentary, not an example.
    """
    flat = _squash(material)
    outside = []
    for block in _FENCE.findall(answer):
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if _squash(line) not in flat:
                outside.append(line)
    return outside


@dataclass(frozen=True, slots=True)
class Grade:
    #: The answer says it is out of scope -- cited or not.
    refusal_phrase: bool
    #: ...and cites nothing, which is what rule 3 asks for.
    refused: bool
    #: Rank of the first expected lesson among the sources, from 1. None: missed.
    gold_rank: int | None
    #: `must_match` patterns the answer does not contain.
    missing: list[str]
    code_outside: list[str]
    verdict: str

    @property
    def passed(self) -> bool:
        return self.verdict == "đạt"


def grade(
    question: Question,
    *,
    answer: str,
    sources: list[str],
    cited: list[str],
    material: str,
) -> Grade:
    """Mark one answer. `sources` and `cited` are lesson titles, `sources` in
    the order they were numbered; `material` is the text the model was given."""
    phrase = is_refusal(answer)
    refused = phrase and not cited
    gold = set(question.lessons)
    rank = next(
        (position for position, title in enumerate(sources, start=1) if title in gold),
        None,
    )
    missing = [
        pattern
        for pattern in question.must_match
        if re.search(pattern, answer, re.IGNORECASE) is None
    ]

    if question.expect == "refuse":
        if refused:
            verdict = "đạt"
        elif phrase:
            verdict = "từ chối nhưng vẫn trích nguồn"
        else:
            verdict = "lẽ ra phải từ chối"
    elif refused:
        verdict = "từ chối nhầm"
    elif missing:
        verdict = "thiếu ý"
    elif not cited:
        verdict = "không trích nguồn"
    elif not gold & set(cited):
        verdict = "trích sai bài"
    else:
        verdict = "đạt"

    return Grade(
        refusal_phrase=phrase,
        refused=refused,
        gold_rank=rank,
        missing=missing,
        code_outside=code_outside_material(answer, material),
        verdict=verdict,
    )


# --- Asking ---------------------------------------------------------------------


class _NoLimits:
    """The evaluation is not a student; `--pause` spaces the calls instead."""

    async def claim(self, key: str, seconds: int) -> int:
        return 0

    async def count(self, key: str, limit: int, window_seconds: int) -> int:
        return 0


@dataclass(slots=True)
class Asked:
    question: Question
    run: int
    sources: list[chat.Source] = field(default_factory=list)
    search_scores: list[float] = field(default_factory=list)
    answer: str = ""
    cited: list[str] = field(default_factory=list)
    #: Answered without calling the model: the course had no material.
    model_called: bool = True
    #: A refusal the model gave citation marks anyway, which the service took
    #: out before storing it -- rule 3 broken by the model, caught by the code.
    marks_removed: bool = False
    first_piece_s: float | None = None
    total_s: float = 0.0
    error: str | None = None
    grade: Grade | None = None


async def _ask(
    session, chat_session_id: uuid.UUID, student: User, question: Question, run: int
) -> Asked:
    asked = Asked(question=question, run=run)
    started = time.perf_counter()
    try:
        prepared = await chat.prepare_answer(
            session,
            chat_session_id,
            student,
            question.text,
            limiter=_NoLimits(),
            make_embedder=build_embedder,
            make_chat_model=build_chat_model,
        )
    except DomainError as error:
        asked.error = f"{error.code}: {error.message}"
        return asked

    asked.sources = prepared.sources
    asked.search_scores = prepared.search_scores
    asked.model_called = prepared.chat_model is not None
    pieces: list[str] = []
    numbers: list[int] = []
    stored_text: str | None = None
    async for event in chat.answer_events(session, prepared):
        if isinstance(event, chat.AnswerPiece):
            if asked.first_piece_s is None:
                asked.first_piece_s = time.perf_counter() - started
            pieces.append(event.text)
        elif isinstance(event, chat.AnswerStored):
            numbers = event.cited_numbers
            stored_text = event.message.content
        elif isinstance(event, chat.AnswerFailed):
            asked.error = f"{event.code}: {event.message}"
    asked.total_s = time.perf_counter() - started
    # What is stored is what the student reads once the answer is done: the
    # page swaps the streamed text for it.
    streamed = "".join(pieces).strip()
    asked.answer = stored_text if stored_text is not None else streamed
    if asked.error:
        return asked
    asked.marks_removed = chat.is_refusal(streamed) and bool(
        chat.cited_numbers(streamed, source_count=len(prepared.sources))
    )

    by_number = {source.number: source for source in prepared.sources}
    asked.cited = [by_number[number].lesson_title for number in numbers]
    asked.grade = grade(
        question,
        answer=asked.answer,
        sources=[source.lesson_title for source in prepared.sources],
        cited=asked.cited,
        material="\n\n".join(passage for source in prepared.sources for passage in source.passages),
    )
    return asked


@dataclass(frozen=True, slots=True)
class Corpus:
    lessons: int
    lessons_with_text: int
    chunks: int


async def _corpus(session, course: Course, embedding_model: str) -> Corpus:
    lessons = await session.scalar(
        select(func.count(Lesson.id))
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .where(CourseSection.course_id == course.id)
    )
    with_text, chunks = (
        await session.execute(
            select(func.count(func.distinct(DocChunk.lesson_id)), func.count(DocChunk.id)).where(
                DocChunk.course_id == course.id, DocChunk.embedding_model == embedding_model
            )
        )
    ).one()
    return Corpus(lessons=lessons or 0, lessons_with_text=with_text, chunks=chunks)


@dataclass(frozen=True, slots=True)
class Scored:
    """A question or probe searched as the chatbot would, without asking."""

    id: str
    text: str
    expect: str
    note: str
    search_scores: list[float]
    top_lesson: str

    @property
    def best(self) -> float:
        """What the merged search starts from: the better of the two."""
        return max(self.search_scores, default=0.0)


async def _score(
    session, embedder: Embedder, course: Course, student: User, text: str, previous: str | None
) -> tuple[list[float], str]:
    history = [chat.HistoryMessage(role="user", content=previous)] if previous else []
    vectors = await embedder.embed_queries(chat.retrieval_queries(text, history=history))
    settings = get_settings()
    hits = [
        await chat.retrieve(
            session,
            course_id=course.id,
            user_id=student.id,
            query_vector=vector,
            embedding_model=embedder.model,
            k=settings.chat_top_k,
        )
        for vector in vectors
    ]
    merged = chat.merge_hits(hits, k=settings.chat_top_k)
    return (
        [found[0].score if found else 0.0 for found in hits],
        merged[0].lesson_title if merged else "",
    )


async def score_only(session, suite: Suite, course: Course, student: User) -> list[Scored]:
    """Every question and probe, searched the way `prepare_answer` searches.

    A follow-up is searched with the question before it in its conversation,
    as it would be: `retrieval_queries` reads only the last student message.
    """
    embedder = build_embedder()
    scored: list[Scored] = []
    previous: dict[str, str] = {}
    for question in suite.questions:
        before = previous.get(question.session) if question.session else None
        scores, top = await _score(session, embedder, course, student, question.text, before)
        if question.session:
            previous[question.session] = question.text
        scored.append(
            Scored(question.id, question.text, question.expect, question.note, scores, top)
        )
    for probe in suite.probes:
        scores, top = await _score(session, embedder, course, student, probe.text, None)
        scored.append(Scored(probe.id, probe.text, probe.expect, probe.note, scores, top))
    await session.commit()
    return scored


async def run(
    suite: Suite, *, runs: int, pause: float, keep: bool, scores_only: bool
) -> tuple[list[Asked], list[Scored], Corpus]:
    settings = get_settings()
    results: list[Asked] = []

    async with SessionLocal() as session:
        course = await session.scalar(select(Course).where(Course.slug == suite.course))
        student = await session.scalar(select(User).where(User.email == suite.student))
        if course is None or student is None:
            raise SystemExit(
                "Không thấy khóa học hoặc học viên của bộ câu hỏi. Chạy scripts.seed trước."
            )
        corpus = await _corpus(session, course, settings.gemini_embedding_model)
        scored = await score_only(session, suite, course, student)
        if scores_only:
            return results, scored, corpus

        conversations: list[uuid.UUID] = []
        try:
            for run_number in range(1, runs + 1):
                opened: dict[str, uuid.UUID] = {}
                for question in suite.questions:
                    if results and pause:
                        await asyncio.sleep(pause)
                    key = question.session or question.id
                    if key not in opened:
                        created = await chat.create_session(session, course.id, student)
                        opened[key] = created.id
                        conversations.append(created.id)

                    asked = await _ask(session, opened[key], student, question, run_number)
                    results.append(asked)
                    mark = asked.error or (asked.grade.verdict if asked.grade else "?")
                    print(
                        f"  lần {run_number} {question.id} {asked.total_s:5.1f}s  {mark}",
                        file=sys.stderr,
                    )
        finally:
            if not keep:
                for conversation in conversations:
                    await chat.delete_session(session, conversation, student)

    return results, scored, corpus


# --- Report ---------------------------------------------------------------------


def _n(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _s(seconds: float | None) -> str:
    return "—" if seconds is None else f"{_n(seconds, 1)} s"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _ratio(hits: int, total: int) -> str:
    return f"{hits}/{total}" + (f" ({hits / total:.0%})" if total else "")


def _summary(results: list[Asked], runs: int, top_k: int) -> list[str]:
    answerable = [r for r in results if r.question.expect == "answer"]
    refusable = [r for r in results if r.question.expect == "refuse"]
    graded = [r for r in results if r.grade is not None]

    def count(rows, predicate) -> int:
        return sum(1 for row in rows if row.grade is not None and predicate(row))

    def rate(rows, predicate) -> str:
        return _ratio(count(rows, predicate), len(rows))

    def gold(row: Asked) -> set[str]:
        return set(row.question.lessons)

    ranks = [r.grade.gold_rank for r in answerable if r.grade is not None]
    mrr = sum(1 / rank for rank in ranks if rank) / len(answerable) if answerable else 0
    with_code = [r for r in graded if _FENCE.search(r.answer)]
    firsts = [r.first_piece_s for r in results if r.first_piece_s is not None and r.model_called]
    totals = [r.total_s for r in results if not r.error and r.model_called]
    per_run = [
        sum(1 for r in results if r.run == number and r.grade is not None and r.grade.passed)
        for number in range(1, runs + 1)
    ]
    per_question = len(results) // runs if runs else 0

    return [
        "| Chỉ số | Kết quả |",
        "|---|---|",
        f"| **Đạt (chấm tự động)** | **{_ratio(sum(per_run), len(results))}** — từng lần: "
        + " · ".join(f"{passed}/{per_question}" for passed in per_run)
        + " |",
        f"| Câu cần trả lời — đạt | {rate(answerable, lambda r: r.grade.passed)} |",
        f"| — bài đúng nằm trong các nguồn tìm được (top-{top_k} chunk) | "
        f"{_ratio(sum(1 for rank in ranks if rank), len(answerable))} · MRR {_n(mrr)} |",
        f"| — đủ ý (khớp mọi `must_match`) | {rate(answerable, lambda r: not r.grade.missing)} |",
        f"| — có trích nguồn | {rate(answerable, lambda r: bool(r.cited))} |",
        "| — trích ít nhất một bài đúng | "
        f"{rate(answerable, lambda r: bool(set(r.cited) & gold(r)))} |",
        "| — mọi bài được trích đều thuộc danh sách bài đúng | "
        f"{rate(answerable, lambda r: bool(r.cited) and set(r.cited) <= gold(r))} |",
        f"| — từ chối nhầm | {count(answerable, lambda r: r.grade.refused)} |",
        "| Câu phải từ chối — từ chối và không trích nguồn | "
        f"{rate(refusable, lambda r: r.grade.passed)} |",
        f"| — từ chối nhưng vẫn gắn số nguồn (học viên thấy) | "
        f"{count(refusable, lambda r: r.grade.verdict == 'từ chối nhưng vẫn trích nguồn')} |",
        f"| — model gắn số nguồn vào câu từ chối, service gỡ trước khi lưu | "
        f"{sum(1 for r in results if r.marks_removed)} |",
        f"| Câu trả lời có khối mã | {len(with_code)} — có dòng mã không nguyên văn "
        f"trong tài liệu: {sum(1 for r in graded if r.grade.code_outside)} |",
        "| Chữ đầu tiên (TTFT) — trung vị / lớn nhất | "
        + (f"{_s(statistics.median(firsts))} / {_s(max(firsts))}" if firsts else "—")
        + " |",
        "| Trả lời xong — trung vị / lớn nhất | "
        + (f"{_s(statistics.median(totals))} / {_s(max(totals))}" if totals else "—")
        + " |",
        f"| Lỗi (Gemini hoặc lưu) | {sum(1 for r in results if r.error)} |",
    ]


def _verdict_mark(asked: Asked) -> str:
    if asked.grade is None:
        return "⚠️ lỗi"
    return "✅" if asked.grade.passed else f"❌ {asked.grade.verdict}"


def _threshold(scored: list[Scored]) -> list[str]:
    lines = [
        "| điểm tốt nhất | riêng / ghép | câu | cần | bài gần nhất |",
        "|---|---|---|---|---|",
    ]
    for item in sorted(scored, key=lambda item: item.best, reverse=True):
        # A probe says what kind of phrasing it stands for; a question's id
        # is enough to find it in the table above.
        note = f" ({_cell(item.note)})" if item.id.startswith("p") else ""
        need = "trả lời" if item.expect == "answer" else "**từ chối**"
        lines.append(
            f"| {_n(item.best)} | {' / '.join(_n(s) for s in item.search_scores)} | "
            f"{item.id} {_cell(item.text[:58])}{note} | {need} | {_cell(item.top_lesson)} |"
        )
    answers = [item for item in scored if item.expect == "answer"]
    refusals = [item for item in scored if item.expect == "refuse"]
    if answers and refusals:
        low = min(answers, key=lambda item: item.best)
        high = max(refusals, key=lambda item: item.best)
        lines += [
            "",
            f"Câu cần trả lời thấp nhất: {_n(low.best)} ({low.id}). "
            f"Câu phải từ chối cao nhất: {_n(high.best)} ({high.id}). "
            + (
                f"Có khoảng trống {_n(low.best - high.best)} giữa hai nhóm."
                if low.best > high.best
                else f"Hai nhóm CHỒNG LÊN NHAU {_n(high.best - low.best)}: "
                "không ngưỡng nào tách được cả hai."
            ),
        ]
    return lines


def _verbatim(asked: Asked) -> list[str]:
    q = asked.question
    need = "trả lời" if q.expect == "answer" else "từ chối"
    lines = [
        f"### {q.id} · lần {asked.run} · {q.kind} · cần {need}",
        "",
        f"**Hỏi:** {q.text}",
        "",
    ]
    if q.note:
        lines.append(f"*Kiểm gì:* {q.note}")
    if q.expect == "answer":
        lines.append(
            f"*Bài đúng:* {', '.join(q.lessons)} · *phải có:* "
            + ", ".join(f"`{p}`" for p in q.must_match)
        )
    lines += [
        "",
        "*Nguồn tìm được:* "
        + (
            "; ".join(f"[{s.number}] {s.lesson_title} ({_n(s.score)})" for s in asked.sources)
            or "không có"
        )
        + ("" if asked.model_called else " — **không gọi model**"),
        "",
    ]
    if asked.answer:
        lines += ["> " + line if line else ">" for line in asked.answer.splitlines()]
    if asked.error:
        lines += ["", f"**Lỗi:** {asked.error}"]
    if asked.grade is not None:
        lines += [
            "",
            f"*Chấm:* {asked.grade.verdict}"
            + (f" · trích: {', '.join(asked.cited)}" if asked.cited else " · không trích nguồn")
            + (" · model đã gắn số nguồn, service gỡ trước khi lưu" if asked.marks_removed else "")
            + (
                " · mã không nguyên văn trong tài liệu: "
                + ", ".join(f"`{line}`" for line in asked.grade.code_outside)
                if asked.grade.code_outside
                else ""
            ),
        ]
    lines.append("")
    return lines


def report(
    suite: Suite,
    results: list[Asked],
    scored: list[Scored],
    corpus: Corpus,
    *,
    runs: int,
    pause: float,
) -> str:
    settings = get_settings()
    lines = [
        "# Đánh giá trợ giảng AI — bộ 20 câu hỏi",
        "",
        f"- Ngày chạy: {datetime.now(UTC):%d/%m/%Y %H:%M} UTC · stack dev · Gemini thật",
        f"- Khóa: `{suite.course}` — {corpus.lessons_with_text}/{corpus.lessons} bài có chữ, "
        f"{corpus.chunks} chunk trong `doc_chunks`",
        f"- Học viên hỏi: `{suite.student}` (đã ghi danh)",
        f"- Model sinh: `{settings.gemini_chat_model}` "
        f"(thinking `{settings.gemini_chat_thinking_level}`) · "
        f"model nhúng: `{settings.gemini_embedding_model}` · top-k = {settings.chat_top_k} chunk",
        f"- Số lần hỏi mỗi câu: {runs} (mỗi lần một cuộc trò chuyện mới) · "
        f"nghỉ {_n(pause, 0)} s giữa hai câu",
        "- Bộ câu hỏi: `backend/scripts/eval_data/chatbot_questions.json`",
        "- Tái tạo (từ thư mục gốc repo): `docker compose -f infra/docker-compose.yml "
        "exec -T backend python -m scripts.eval_chatbot "
        "> docs/report/assets/phase-4/chatbot-eval.md`",
        "",
    ]

    if results:
        lines += [
            "Chấm tự động theo `grade()` trong `backend/scripts/eval_chatbot.py`: câu cần "
            "trả lời đạt khi không từ chối, khớp mọi biểu thức `must_match`, và trích ít nhất "
            "một bài đúng; câu phải từ chối đạt khi từ chối và không trích nguồn nào. Mọi tỉ "
            "lệ tính trên tất cả các lần hỏi. Nguyên văn ở cuối tệp: lần 1 đầy đủ; các lần "
            "sau chỉ những câu có kết quả khác lần 1, có mã không nguyên văn trong tài liệu, "
            "hoặc có số nguồn bị service gỡ.",
            "",
            "## Tổng hợp",
            "",
            *_summary(results, runs, settings.chat_top_k),
            "",
            "## Từng câu",
            "",
            "Điểm = cosine của chunk gần nhất (lần 1): *riêng* là tìm bằng câu hỏi một mình, "
            "*ghép* là tìm bằng câu hỏi nối với câu trước (chỉ câu nối tiếp mới có). Hạng = vị "
            "trí của bài đúng đầu tiên trong các nguồn (— là không tìm thấy).",
            "",
            "| # | loại | câu hỏi | điểm riêng / ghép | hạng | kết quả từng lần "
            "| mã không nguyên văn | TTFT trung vị |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for question in suite.questions:
            mine = [r for r in results if r.question.id == question.id]
            first = mine[0]
            rank = first.grade.gold_rank if first.grade else None
            firsts = [r.first_piece_s for r in mine if r.first_piece_s is not None]
            outside = sum(1 for r in mine if r.grade and r.grade.code_outside)
            lines.append(
                f"| {question.id} | {question.kind} | {_cell(question.text)} | "
                f"{' / '.join(_n(s) for s in first.search_scores) or '—'} | "
                f"{rank or ('—' if question.expect == 'answer' else '')} | "
                f"{' · '.join(_verdict_mark(r) for r in mine)} | "
                f"{f'{outside}/{len(mine)}' if outside else ''} | "
                f"{_s(statistics.median(firsts)) if firsts else '—'} |"
            )

    lines += [
        "",
        "## Điểm truy hồi — dữ liệu cho ngưỡng từ chối",
        "",
        "Mỗi câu và mỗi câu thăm dò được nhúng và tìm đúng như `prepare_answer` tìm, không "
        "gọi model. *Điểm tốt nhất* là cosine của chunk gần nhất sau khi gộp hai lần tìm — "
        "con số mà một ngưỡng sẽ so. Một ngưỡng từ chối trước khi gọi model chỉ an toàn ở "
        "dưới mọi câu cần trả lời.",
        "",
        *_threshold(scored),
    ]

    if results:
        lines += ["", "## Nguyên văn", ""]
        first_run = [r for r in results if r.run == 1]
        for asked in first_run:
            lines += _verbatim(asked)
        differing = [
            r
            for r in results
            if r.run > 1
            and (
                _verdict_mark(r)
                != _verdict_mark(next(f for f in first_run if f.question.id == r.question.id))
                or (r.grade is not None and r.grade.code_outside)
                or r.marks_removed
            )
        ]
        if differing:
            lines += [
                "## Các lần sau — câu có kết quả khác lần 1, có mã không nguyên văn, "
                "hoặc có số nguồn bị gỡ",
                "",
            ]
            for asked in differing:
                lines += _verbatim(asked)
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--runs", type=int, default=3, help="Số lần hỏi mỗi câu.")
    parser.add_argument(
        "--pause",
        type=float,
        default=4.0,
        help="Giây nghỉ giữa hai câu hỏi, để không chạm giới hạn phút của free tier.",
    )
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="Chỉ nhúng và tìm (điểm cho ngưỡng), không hỏi model.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Giữ lại các cuộc trò chuyện (xem được trong UI của học viên).",
    )
    args = parser.parse_args()
    # The report goes to stdout, and the dev engine echoes every query there.
    engine.echo = False

    suite = load_suite(args.questions)
    results, scored, corpus = await run(
        suite, runs=args.runs, pause=args.pause, keep=args.keep, scores_only=args.scores_only
    )
    print(report(suite, results, scored, corpus, runs=args.runs, pause=args.pause))


if __name__ == "__main__":
    asyncio.run(main())
