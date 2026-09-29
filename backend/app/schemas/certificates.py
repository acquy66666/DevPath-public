"""A certificate as the public verification page shows it."""

from datetime import datetime

from pydantic import BaseModel


class CertificateOut(BaseModel):
    """Exactly what is printed on the certificate, and nothing about the
    account behind it: no email, no user id, no enrolment."""

    code: str
    #: ABCD-EFGH-JKLM-NPQR, as printed.
    display_code: str
    recipient_name: str
    course_title: str
    instructor_name: str
    issued_at: datetime
    #: The course page, while the course is still on sale; null after that.
    course_slug: str | None
    #: False until the worker has drawn the PDF.
    pdf_ready: bool
    verify_url: str
