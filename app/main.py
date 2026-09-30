"""Application factory.

Builds the FastAPI app, registers the exception handlers that translate every
failure into the standard error envelope, and mounts the routers.

The handlers are the reason services can raise domain errors without knowing
anything about HTTP: the mapping from error to status code happens here, once.
"""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.settings import settings
from app.errors import ApiError
from app.schemas.common import ErrorResponse
from app.api.routers import health

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    message: str,
    details: list | None = None,
) -> JSONResponse:
    """Render the standard error envelope."""
    body = ErrorResponse(message=message, details=details)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(by_alias=True, exclude_none=True),
    )


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        """Domain errors raised by services. The status code travels on the
        exception, so this one handler covers 400, 404 and 409 alike."""
        return _error_response(exc.status_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic rejected the request before the handler ran. FastAPI would
        return 422 with its own shape; the contract says 400 with ours."""
        return _error_response(400, "Validation failed", details=exc.errors())

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Raised by the router itself — chiefly a 404 for a path that matches
        no route. Without this, Starlette's own {"detail": ...} escapes."""
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _error_response(exc.status_code, message)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        """Anything unanticipated. The traceback is always logged; it reaches
        the client only in development."""
        logger.exception("Unhandled error", exc_info=exc)
        details = traceback.format_exc().splitlines() if settings.is_development else None
        return _error_response(500, "Internal server error", details=details)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Scheduling Platform API",
        version="0.1.0",
        docs_url="/docs",
    )

    _register_exception_handlers(app)
    app.include_router(health.router)

    return app


app = create_app()