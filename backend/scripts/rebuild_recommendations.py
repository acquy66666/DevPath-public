"""Run the nightly recommendation batch now, without waiting for 03:00.

    python -m scripts.rebuild_recommendations

Two reasons this exists rather than telling people to trigger the Celery task:

* a demo cannot wait for a cron. After seeding interaction data, the cache is
  empty until beat next fires, and an empty "Gợi ý cho bạn" block looks like a
  broken feature rather than an unfilled cache.
* the thesis has to be reproducible. Evaluation numbers are worthless if the
  only way to regenerate the state behind them is to leave a container running
  overnight.

It runs the same `rebuild` the Celery task runs, in this process, against the
same Redis -- so what it writes is what the nightly job would have written,
not an approximation of it.

**Run `scripts.rebuild_course_embeddings` first.** Since the blend, this job
reads `course_embeddings` for its content-based half; with that table empty it
still succeeds and writes collaborative-only lists, which look perfectly
normal and are not what the nightly pair produces. It logs a warning when it
finds no vectors, and this paragraph is the other half of that warning.
"""

import asyncio

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import CourseEmbedding
from app.services.recommendations import DEFAULT_TOP_N, build_writer, rebuild


async def main() -> None:
    async with SessionLocal() as session:
        written = await rebuild(session, build_writer())
        # The same question `rebuild` asks before its content-based half, so
        # the last line says which recommender actually ran. It used to say
        # "trộn collaborative + content-based" right under the warning that
        # there was no content-based half at all.
        vectors = await session.scalar(
            select(func.count())
            .select_from(CourseEmbedding)
            .where(CourseEmbedding.embedding_model == get_settings().gemini_embedding_model)
        )

    blend = (
        "trộn collaborative + content-based"
        if vectors
        else "chỉ collaborative (chưa có vector khóa học: scripts.rebuild_course_embeddings)"
    )
    print(f"Đã ghi gợi ý cho {written} người dùng (top {DEFAULT_TOP_N} mỗi người), {blend}.")
    if written == 0:
        print(
            "Không có ai để tính: chưa có lượt đăng ký khóa học nào trong CSDL. "
            "Chạy `python -m scripts.seed` trước."
        )


if __name__ == "__main__":
    asyncio.run(main())
