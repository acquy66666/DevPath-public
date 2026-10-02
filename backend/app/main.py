from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()

    # The schema is a map of every route and every field. Useful while
    # building; on the public server it only helps somebody looking for the
    # route that was forgotten. No schema also means no /docs and no /redoc.
    public_schema = settings.env != "production"

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_url="/openapi.json" if public_schema else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        # What the frontend sends (lib/api/client.ts), not "*": with
        # credentials on, a wildcard is answered by reflecting whatever the
        # browser asked for. Accept needs no entry -- CORS always allows it.
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
