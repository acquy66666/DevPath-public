"""Certificates of completion.

One per enrolment (`uq_certificates_enrollment`), issued in the transaction
that finishes the course and never issued again -- unticking a lesson and
finishing it a second time is the same completion, not a second certificate.

**What it says is frozen when it is issued.** `recipient_name`, `course_title`
and `instructor_name` are copied, not joined: a certificate is a statement made
on a date, and one that changed its wording when the learner edited their
profile or the instructor retitled the course would not be a record of
anything. Same reasoning as `order_items.unit_price`.

**`code` is what the QR code carries**, and the only key the public page takes.
Sixteen characters from 32 unambiguous ones (no I, O, 0 or 1) is 80 random
bits: nobody finds somebody else's certificate by counting.
`ck_certificates_code_format` makes the alphabet a rule of the table rather
than of the one function that happens to generate codes today.

**`pdf_key` is empty until the worker has drawn the PDF**, which happens after
the commit that issued it. A certificate without a PDF is still valid -- the
verification page says so from the row -- it just has nothing to download yet.

`enrollment_id` is **RESTRICT**: a certificate is proof handed to somebody, and
it must not vanish as a side effect of deleting what it was issued for. Code
that removes enrolments (the seed scripts' `--purge`) removes the certificate
first, on purpose.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: The characters a certificate code is made of: no I/O/0/1 to misread when
#: somebody types a code off a printed page.
CERTIFICATE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CERTIFICATE_CODE_LENGTH = 16


class Certificate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "certificates"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(CERTIFICATE_CODE_LENGTH), nullable=False)

    # Frozen at issue. Lengths match the columns they are copied from.
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    course_title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructor_name: Mapped[str] = mapped_column(String(150), nullable=False)

    #: When the course was completed -- the date printed on the certificate.
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: Where the PDF is in object storage; NULL until the worker has drawn it.
    pdf_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("enrollment_id", name="uq_certificates_enrollment"),
        UniqueConstraint("code", name="uq_certificates_code"),
        CheckConstraint(
            f"code ~ '^[{CERTIFICATE_CODE_ALPHABET}]{{{CERTIFICATE_CODE_LENGTH}}}$'",
            name="ck_certificates_code_format",
        ),
    )

    def __repr__(self) -> str:
        return f"<Certificate {self.code} for {self.recipient_name!r}>"
