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
"""

import asyncio

from app.core.db import SessionLocal
from app.services.recommendations import DEFAULT_TOP_N, build_writer, rebuild


async def main() -> None:
    async with SessionLocal() as session:
        written = await rebuild(session, build_writer())

    print(f"Đã ghi gợi ý cho {written} người dùng (top {DEFAULT_TOP_N} mỗi người).")
    if written == 0:
        print(
            "Không có ai để tính: chưa có lượt đăng ký khóa học nào trong CSDL. "
            "Chạy `python -m scripts.seed` trước."
        )


if __name__ == "__main__":
    asyncio.run(main())
