from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class DomainError(Exception):
    """Business rule violation raised by the service layer.

    Routers never build error responses themselves; they let this bubble up
    so every error leaves the API in the same shape:
        {"detail": {"code": "COURSE_NOT_FOUND", "message": "..."}}
    The frontend switches on `code`, never on `message`.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class NotAuthenticatedError(DomainError):
    """No usable credentials. 401 with a WWW-Authenticate header is what a
    Bearer scheme owes the client (RFC 6750); the header is added by the
    handler in register_exception_handlers."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "NOT_AUTHENTICATED"


class PermissionDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"


def _error(status_code: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message, **extra}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        # A rate limit that does not say when to come back is a rate limit the
        # client can only answer by guessing -- which is another request.
        retry_after = getattr(exc, "retry_after", None)
        extra = {"retry_after": retry_after} if retry_after else {}

        response = _error(exc.status_code, exc.code, exc.message, **extra)
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            response.headers["WWW-Authenticate"] = "Bearer"
        if retry_after:
            # The header is what a browser, a proxy or curl already knows how
            # to read; the body field is for the page that draws a countdown.
            response.headers["Retry-After"] = str(retry_after)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Keep already-shaped payloads untouched, wrap plain string details.
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        code = "HTTP_ERROR" if exc.status_code != 404 else "NOT_FOUND"
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": {
                    "code": "VALIDATION_ERROR",
                    "message": "Dữ liệu gửi lên không hợp lệ",
                    "errors": jsonable_encoder(exc.errors()),
                }
            },
        )
