"""How far `CHARS_PER_TOKEN` is from Gemini's own count, on the real chunks.

    python -m scripts.eval_token_estimate
    python -m scripts.eval_token_estimate python-co-ban-cho-nguoi-moi-bat-dau

The chunker never calls the tokenizer: a network call per chunk would be
slower than the embedding it budgets for, so it divides characters by 3.5, a
ratio measured on four hand-picked samples (embedding-model.txt §3). This
asks `countTokens` about every chunk actually in `doc_chunks` and prints how
the estimate held up -- and whether any chunk came near the 2048-token input
limit, past which the API truncates without an error.

Costs one `countTokens` call per chunk and no embedding quota. Output is plain
text for docs/report/assets/phase-4/.
"""

import argparse
import asyncio
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.models import Course, DocChunk, Lesson
from app.services.chunking import CHARS_PER_TOKEN, MAX_CHUNK_TOKENS
from app.services.llm import LLMError, build_embedder

#: gemini-embedding-001's input limit. Past it the text is cut, silently.
MODEL_INPUT_LIMIT = 2048


@dataclass(frozen=True, slots=True)
class Measured:
    course: str
    lesson: str
    source: str
    chunk_index: int
    chars: int
    estimated: int
    real: int

    @property
    def chars_per_token(self) -> float:
        return self.chars / self.real

    @property
    def error(self) -> float:
        """Estimate minus truth, as a share of the truth. Positive is safe:
        the chunk holds fewer real tokens than it was budgeted for."""
        return (self.estimated - self.real) / self.real


def _pct(value: float) -> str:
    return f"{value * 100:+.1f}%"


def _num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def report(rows: list[Measured], *, model: str) -> str:
    lines = [
        "ƯỚC LƯỢNG TOKEN CỦA CHUNKER SO VỚI countTokens CỦA GEMINI",
        f"Ngày chạy: {datetime.now(UTC):%d/%m/%Y %H:%M} UTC · model: {model} · "
        f"CHARS_PER_TOKEN = {_num(CHARS_PER_TOKEN, 1)} · MAX_CHUNK_TOKENS = {MAX_CHUNK_TOKENS}",
        "Tái tạo: docker compose exec backend python -m scripts.eval_token_estimate",
        "",
        f"{'khóa':<24} {'bài':<34} {'nguồn':<10} {'#':>2} {'ký tự':>6} "
        f"{'ước':>5} {'thật':>5} {'ký tự/tok':>9} {'sai số':>8}",
    ]
    for row in rows:
        lines.append(
            f"{row.course[:24]:<24} {row.lesson[:34]:<34} {row.source:<10} "
            f"{row.chunk_index:>2} {row.chars:>6} {row.estimated:>5} {row.real:>5} "
            f"{_num(row.chars_per_token):>9} {_pct(row.error):>8}"
        )

    ratios = [row.chars_per_token for row in rows]
    total_chars = sum(row.chars for row in rows)
    total_real = sum(row.real for row in rows)
    total_estimated = sum(row.estimated for row in rows)
    under = [row for row in rows if row.estimated < row.real]
    biggest = max(rows, key=lambda row: row.real)

    lines += [
        "",
        f"Chunk đo: {len(rows)} · tổng {total_chars} ký tự · ước {total_estimated} token · "
        f"thật {total_real} token",
        f"Ký tự/token thật: gộp cả kho {_num(total_chars / total_real)} · "
        f"trung vị {_num(statistics.median(ratios))} · "
        f"thấp nhất {_num(min(ratios))} · cao nhất {_num(max(ratios))}",
        f"Sai số của ước lượng: gộp {_pct((total_estimated - total_real) / total_real)} · "
        f"trung vị {_pct(statistics.median(row.error for row in rows))}",
        f"Ước THẤP hơn thật (phía nguy hiểm): {len(under)}/{len(rows)} chunk"
        + (
            " — "
            + ", ".join(f"{row.lesson[:30]} #{row.chunk_index} {_pct(row.error)}" for row in under)
            if under
            else ""
        ),
        f"Chunk lớn nhất: {biggest.real} token thật ({biggest.lesson} #{biggest.chunk_index}), "
        f"giới hạn đầu vào của model {MODEL_INPUT_LIMIT}",
    ]
    for source in sorted({row.source for row in rows}):
        group = [row for row in rows if row.source == source]
        chars = sum(row.chars for row in group)
        real = sum(row.real for row in group)
        lines.append(
            f"  theo nguồn — {source}: {len(group)} chunk, {_num(chars / real)} ký tự/token"
        )
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("course", nargs="?", help="Slug khóa học. Bỏ trống: mọi chunk.")
    args = parser.parse_args()
    # The report goes to stdout, and the dev engine echoes every query there.
    engine.echo = False

    try:
        embedder = build_embedder()
    except LLMError as error:
        raise SystemExit(error.message) from None

    async with SessionLocal() as session:
        query = (
            select(Course.slug, Lesson.title, Lesson.type, DocChunk)
            .join(Course, Course.id == DocChunk.course_id)
            .join(Lesson, Lesson.id == DocChunk.lesson_id)
            .where(DocChunk.embedding_model == embedder.model)
            .order_by(Course.slug, Lesson.title, DocChunk.chunk_index)
        )
        if args.course:
            query = query.where(Course.slug == args.course)
        found = (await session.execute(query)).all()

    if not found:
        raise SystemExit("Không có chunk nào. Chạy scripts.ingest_course trước.")

    rows = []
    for number, (slug, title, lesson_type, chunk) in enumerate(found, start=1):
        print(f"  {number}/{len(found)}", end="\r", file=sys.stderr)
        rows.append(
            Measured(
                course=slug,
                lesson=title,
                source="transcript" if lesson_type == "video" else lesson_type,
                chunk_index=chunk.chunk_index,
                chars=len(chunk.content),
                estimated=chunk.token_count,
                real=await embedder.count_tokens(chunk.content),
            )
        )

    print(report(rows, model=embedder.model))


if __name__ == "__main__":
    asyncio.run(main())
