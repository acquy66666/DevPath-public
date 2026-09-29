"""Issue the certificates for courses finished before certificates existed.

    python -m scripts.issue_certificates
    python -m scripts.issue_certificates --dry-run

A course finished from now on gets its certificate in the transaction that
finishes it. One finished earlier -- `enrollments.completed_at` set, no row in
`certificates` -- gets it here, through the same `certificates.issue`, dated
the day it was actually finished rather than today. `completed_at` is the
authority, as it is for the instructor dashboard.

Then every certificate that has no PDF yet is drawn, in this process rather
than through the queue: it needs Pango, so **run it inside the backend
container**, which has it.

Idempotent: a second run issues nothing and draws nothing.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Certificate, Enrollment
from app.services import certificates
from app.services.storage import build_storage


async def main(dry_run: bool) -> None:
    async with SessionLocal() as session:
        missing = list(
            await session.scalars(
                select(Enrollment)
                .outerjoin(Certificate, Certificate.enrollment_id == Enrollment.id)
                .where(Enrollment.completed_at.is_not(None), Certificate.id.is_(None))
                .order_by(Enrollment.completed_at)
            )
        )
        undrawn = await session.scalar(
            select(Certificate.id).where(Certificate.pdf_key.is_(None)).limit(1)
        )
        if dry_run:
            print(f"Sẽ cấp {len(missing)} chứng chỉ cho các khóa đã hoàn thành trước đó.")
            return

        for enrollment in missing:
            await certificates.issue(session, enrollment, issued_at=enrollment.completed_at)
        # Drawn below, here; nothing for the queue to do.
        session.info.pop(certificates.STAGED, None)
        await session.commit()
        print(f"Đã cấp {len(missing)} chứng chỉ.")

        if not missing and undrawn is None:
            print("Mọi chứng chỉ đã có PDF.")
            return

        storage = build_storage()
        ids = list(
            await session.scalars(select(Certificate.id).where(Certificate.pdf_key.is_(None)))
        )
        drawn = 0
        for certificate_id in ids:
            drawn += await certificates.render(session, storage, certificate_id)
        print(f"Đã vẽ {drawn} tệp PDF.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm, không ghi gì")
    asyncio.run(main(parser.parse_args().dry_run))
