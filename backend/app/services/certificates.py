"""Certificates of completion: issued with the completion, drawn afterwards.

**Issuing** happens inside the transaction that finishes a course --
`progress._refresh_course_completion`, the one place a course becomes finished
whichever kind of lesson finished it. One per enrolment, never re-issued: a
course unticked and finished again is the same completion. What the
certificate says (who, which course, taught by whom, on what day) is copied
there and then, and never follows later edits.

**Drawing** the PDF is slow (WeasyPrint lays out a page) and needs Pango, so it
is not done in the request. The new certificate's id is staged on the session,
and whoever commits calls `after_commit.run`, which queues the Celery job --
never for a certificate whose transaction rolled back. The job is idempotent,
and a download of a PDF that was never drawn queues it again: a lost job costs
a retry, not a certificate.

**Verifying** needs only the code. The public view is exactly what is printed
on the paper -- the frozen names, the course, the date -- and never the
learner's email or account.
"""

import asyncio
import html
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import status
from sqlalchemy import Select, delete, event, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.clock import VIETNAM
from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.models import (
    CERTIFICATE_CODE_ALPHABET,
    CERTIFICATE_CODE_LENGTH,
    Certificate,
    Course,
    Enrollment,
    User,
)
from app.services.storage import ObjectStorage

logger = logging.getLogger(__name__)

#: Where new certificates wait on the session for their commit.
STAGED = "certificates.staged"
#: A collision in 80 random bits is not going to happen twice in a row.
CODE_ATTEMPTS = 5


class CertificateNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "CERTIFICATE_NOT_FOUND"


class CertificateNotReadyError(DomainError):
    """The certificate is valid; its PDF has not been drawn yet."""

    status_code = status.HTTP_409_CONFLICT
    code = "CERTIFICATE_NOT_READY"


# --- Codes ---------------------------------------------------------------------


def new_code() -> str:
    """Sixteen characters from 32 unambiguous ones: 80 random bits."""
    return "".join(
        secrets.choice(CERTIFICATE_CODE_ALPHABET) for _ in range(CERTIFICATE_CODE_LENGTH)
    )


def normalize_code(raw: str) -> str | None:
    """A code as somebody may type it -- lower case, grouped with dashes or
    spaces -- or None if it cannot be one."""
    code = "".join(raw.split()).replace("-", "").upper()
    if len(code) != CERTIFICATE_CODE_LENGTH or not set(code) <= set(CERTIFICATE_CODE_ALPHABET):
        return None
    return code


def display_code(code: str) -> str:
    """ABCD-EFGH-JKLM-NPQR: four groups, readable off a page."""
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))


def pdf_key(code: str) -> str:
    return f"certificates/{code}.pdf"


def verify_url(code: str) -> str:
    return f"{get_settings().frontend_url.rstrip('/')}/cert/{code}"


# --- Issuing -------------------------------------------------------------------


async def issue(
    session: AsyncSession, enrollment: Enrollment, *, issued_at: datetime
) -> Certificate | None:
    """Issue the certificate for a finished enrolment, unless it has one.

    Returns the new certificate, or None if there already was one. Does not
    commit; stages the new id so the PDF is asked for after the commit.
    """
    if await session.scalar(
        select(Certificate.id).where(Certificate.enrollment_id == enrollment.id)
    ):
        return None

    learner = await session.get(User, enrollment.user_id)
    course = await session.get(Course, enrollment.course_id)
    instructor = await session.get(User, course.instructor_id) if course else None
    if learner is None or course is None or instructor is None:
        # The foreign keys make all three exist; this is here for the type
        # checker, not for a case that happens.
        return None

    for _ in range(CODE_ATTEMPTS):
        certificate_id = await session.scalar(
            insert(Certificate)
            .values(
                enrollment_id=enrollment.id,
                code=new_code(),
                recipient_name=learner.full_name,
                course_title=course.title,
                instructor_name=instructor.full_name,
                issued_at=issued_at,
            )
            # Either unique key: the enrolment (somebody got there first) or
            # the code (drawn twice). The check below says which.
            .on_conflict_do_nothing()
            .returning(Certificate.id)
        )
        if certificate_id is not None:
            session.info.setdefault(STAGED, []).append(certificate_id)
            return await session.get(Certificate, certificate_id)
        if await session.scalar(
            select(Certificate.id).where(Certificate.enrollment_id == enrollment.id)
        ):
            return None
    raise RuntimeError("could not draw an unused certificate code")


@event.listens_for(Session, "after_soft_rollback")
def _drop_staged(session: Session, previous_transaction) -> None:
    if previous_transaction.parent is None:
        session.info.pop(STAGED, None)


def enqueue_render(certificate_id: uuid.UUID) -> None:
    """Hand a certificate to the worker. Tests replace this (conftest)."""
    from app.workers.certificates import render_certificate

    render_certificate.delay(str(certificate_id))


def dispatch_staged(session: AsyncSession) -> None:
    """Queue the PDFs of what the last commit issued. Call after `commit()`.

    Never raises: the certificate is committed and valid, and a PDF whose job
    was lost is queued again by the first download that finds it missing.
    """
    for certificate_id in session.info.pop(STAGED, []):
        try:
            enqueue_render(certificate_id)
        except Exception as exc:  # noqa: BLE001 - see the docstring
            logger.warning("certificate %s not queued for drawing: %s", certificate_id, exc)


# --- Drawing -------------------------------------------------------------------


def _qr_svg(url: str) -> str:
    import segno

    # No width or height, so the SVG gets a viewBox and CSS decides its size.
    return segno.make(url, error="m").svg_inline(border=0, omitsize=True, dark="#111827")


PAGE = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Chứng nhận hoàn thành — {course_title}</title>
<style>
@page {{ size: A4 landscape; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "DejaVu Serif", serif; color: #111827; }}
.sheet {{ width: 297mm; height: 210mm; padding: 12mm; }}
.frame {{ height: 100%; border: 2.2mm solid #1e3a8a; padding: 2.5mm; }}
.inner {{
  height: 100%; border: 0.4mm solid #93c5fd; padding: 12mm 22mm 0;
  position: relative; text-align: center;
}}
.brand {{
  font-family: "DejaVu Sans", sans-serif; font-weight: bold; font-size: 15pt;
  color: #1e3a8a; letter-spacing: 0.5pt;
}}
.kicker {{
  margin-top: 9mm; font-family: "DejaVu Sans", sans-serif; font-size: 10pt;
  letter-spacing: 3pt; color: #6b7280;
}}
h1 {{ margin: 3mm 0 0; font-size: 28pt; color: #1e3a8a; }}
.to {{ margin-top: 9mm; font-size: 12pt; color: #4b5563; }}
.name {{
  display: inline-block; margin-top: 3mm; padding: 0 12mm 2mm;
  border-bottom: 0.3mm solid #d1d5db; font-size: 28pt; font-weight: bold;
}}
.for {{ margin-top: 8mm; font-size: 12pt; color: #4b5563; }}
.course {{ margin-top: 2mm; font-size: 18pt; font-weight: bold; }}
.footer {{
  position: absolute; left: 22mm; right: 22mm; bottom: 10mm;
  font-family: "DejaVu Sans", sans-serif; font-size: 9pt; color: #374151;
}}
.left {{ position: absolute; left: 0; bottom: 0; text-align: left; }}
.right {{ position: absolute; right: 0; bottom: 0; text-align: right; }}
.label {{ color: #6b7280; }}
.strong {{ font-size: 11pt; font-weight: bold; color: #111827; }}
.qr {{ display: inline-block; width: 27mm; height: 27mm; vertical-align: bottom; }}
.qr svg {{ width: 27mm; height: 27mm; }}
.verify {{ display: inline-block; vertical-align: bottom; margin-right: 4mm; }}
.code {{ font-family: "DejaVu Sans Mono", monospace; font-size: 11pt; font-weight: bold; }}
.url {{ font-size: 7.5pt; color: #6b7280; }}
</style>
</head>
<body>
<div class="sheet"><div class="frame"><div class="inner">
  <div class="brand">DevPath</div>
  <div class="kicker">CERTIFICATE OF COMPLETION</div>
  <h1>Chứng nhận hoàn thành</h1>
  <div class="to">Trao cho</div>
  <div class="name">{recipient_name}</div>
  <div class="for">đã hoàn thành toàn bộ khóa học</div>
  <div class="course">{course_title}</div>
  <div class="footer">
    <div class="left">
      <div class="label">Giảng viên</div>
      <div class="strong">{instructor_name}</div>
      <div class="label" style="margin-top: 3mm">Ngày hoàn thành</div>
      <div class="strong">{issued_on}</div>
    </div>
    <div class="right">
      <div class="verify">
        <div class="label">Mã chứng chỉ</div>
        <div class="code">{display_code}</div>
        <div class="url">Xác thực tại {verify_url}</div>
      </div>
      <div class="qr">{qr}</div>
    </div>
  </div>
</div></div></div>
</body>
</html>
"""


def build_html(
    *,
    code: str,
    recipient_name: str,
    course_title: str,
    instructor_name: str,
    issued_on: date,
    verify_url: str,
) -> str:
    """The certificate as a page. Everything a person typed is escaped."""
    return PAGE.format(
        recipient_name=html.escape(recipient_name),
        course_title=html.escape(course_title),
        instructor_name=html.escape(instructor_name),
        issued_on=issued_on.strftime("%d/%m/%Y"),
        display_code=display_code(code),
        verify_url=html.escape(verify_url),
        qr=_qr_svg(verify_url),
    )


def draw_pdf(page: str) -> bytes:
    """Lay the page out into a PDF. Imported here: WeasyPrint needs Pango,
    which the API image has and a Windows laptop does not."""
    from weasyprint import HTML

    return HTML(string=page).write_pdf()


async def render(session: AsyncSession, storage: ObjectStorage, certificate_id: uuid.UUID) -> bool:
    """Draw a certificate's PDF and store it. Returns whether it drew one.

    Idempotent: a certificate that already has its PDF is left alone, so a
    job delivered twice -- or queued again by an impatient download -- does
    no harm.
    """
    certificate = await session.get(Certificate, certificate_id)
    if certificate is None or certificate.pdf_key is not None:
        return False

    page = build_html(
        code=certificate.code,
        recipient_name=certificate.recipient_name,
        course_title=certificate.course_title,
        instructor_name=certificate.instructor_name,
        issued_on=certificate.issued_at.astimezone(VIETNAM).date(),
        verify_url=verify_url(certificate.code),
    )
    data = await asyncio.to_thread(draw_pdf, page)
    key = pdf_key(certificate.code)
    await asyncio.to_thread(storage.upload_bytes, data, key, "application/pdf")

    certificate.pdf_key = key
    await session.commit()
    return True


# --- Reading -------------------------------------------------------------------


@dataclass(frozen=True)
class PublicCertificate:
    certificate: Certificate
    #: The course page to link to, while the course is still on sale.
    course_slug: str | None


async def get_public(session: AsyncSession, raw_code: str) -> PublicCertificate:
    """A certificate by its code, for anybody holding the code."""
    code = normalize_code(raw_code)
    row = (
        await session.execute(
            select(Certificate, Course)
            .join(Enrollment, Enrollment.id == Certificate.enrollment_id)
            .join(Course, Course.id == Enrollment.course_id)
            .where(Certificate.code == code)
        )
        if code
        else None
    )
    found = row.first() if row is not None else None
    if found is None:
        raise CertificateNotFoundError("Không tìm thấy chứng chỉ với mã này")

    certificate, course = found
    on_sale = course.status == "published" and course.deleted_at is None
    return PublicCertificate(certificate, course.slug if on_sale else None)


async def pdf_bytes(
    session: AsyncSession, storage: ObjectStorage, raw_code: str
) -> tuple[Certificate, bytes]:
    """The PDF of a certificate, or `CertificateNotReadyError` after queueing it."""
    certificate = (await get_public(session, raw_code)).certificate
    if certificate.pdf_key is None:
        try:
            enqueue_render(certificate.id)
        except Exception as exc:  # noqa: BLE001 - the answer is "not ready" either way
            logger.warning("certificate %s not queued for drawing: %s", certificate.id, exc)
        raise CertificateNotReadyError(
            "Tệp PDF của chứng chỉ đang được tạo. Vui lòng thử lại sau ít phút."
        )
    data = await asyncio.to_thread(storage.read_bytes, certificate.pdf_key)
    return certificate, data


async def delete_for_enrollments(session: AsyncSession, enrollment_ids: Select) -> int:
    """Remove the certificates of these enrolments. Returns how many.

    Only for tearing down what a script built -- the seed scripts' `--purge`,
    the grading benchmark. `certificates.enrollment_id` is RESTRICT so that
    nothing else removes a certificate by accident; this is the deliberate
    way. The PDFs are left in storage: a dev bucket with a stray file is not
    worth a script that hangs when MinIO is down.
    """
    result = await session.execute(
        delete(Certificate).where(Certificate.enrollment_id.in_(enrollment_ids))
    )
    return result.rowcount or 0


async def codes_for(session: AsyncSession, enrollment_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Enrolment id → certificate code, for the enrolments that have one."""
    if not enrollment_ids:
        return {}
    rows = await session.execute(
        select(Certificate.enrollment_id, Certificate.code).where(
            Certificate.enrollment_id.in_(enrollment_ids)
        )
    )
    return dict(rows.tuples().all())
