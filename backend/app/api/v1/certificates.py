"""Verifying a certificate of completion.

**Public on purpose.** Whoever holds a certificate's code -- because the
learner showed them the PDF, scanned its QR code or pasted the link into a CV
-- may check that it is real. The code is 80 random bits, so holding it is the
permission; there is no list to browse and nothing keyed by anything else.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.deps import DbSession
from app.schemas.certificates import CertificateOut
from app.services import certificates as certificates_service
from app.services.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("/{code}", response_model=CertificateOut)
async def get_certificate(code: str, session: DbSession) -> CertificateOut:
    """What the certificate says. 404 `CERTIFICATE_NOT_FOUND` for any code
    that is not one -- malformed and unknown alike."""
    found = await certificates_service.get_public(session, code)
    certificate = found.certificate
    return CertificateOut(
        code=certificate.code,
        display_code=certificates_service.display_code(certificate.code),
        recipient_name=certificate.recipient_name,
        course_title=certificate.course_title,
        instructor_name=certificate.instructor_name,
        issued_at=certificate.issued_at,
        course_slug=found.course_slug,
        pdf_ready=certificate.pdf_key is not None,
        verify_url=certificates_service.verify_url(certificate.code),
    )


@router.get(
    "/{code}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_certificate(
    code: str,
    session: DbSession,
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> Response:
    """The certificate as a PDF.

    409 `CERTIFICATE_NOT_READY` while the worker has not drawn it -- and the
    job is queued again, so a PDF whose first job was lost is one retry away.
    """
    certificate, data = await certificates_service.pdf_bytes(session, storage, code)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="devpath-chung-chi-{certificate.code}.pdf"'
        },
    )
