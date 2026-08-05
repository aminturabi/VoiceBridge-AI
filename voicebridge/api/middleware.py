"""API middleware for request ID tracking, standardized error responses, and boundary protection."""

from __future__ import annotations

import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from voicebridge.config.loader import ConfigError
from voicebridge.logging_conf import get_logger, request_id_ctx

logger = get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns or preserves a unique Request ID (X-Request-ID) for every API request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(req_id)
        
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for standardized error payloads."""

    @app.exception_handler(ConfigError)
    async def config_error_handler(request: Request, exc: ConfigError) -> JSONResponse:
        req_id = request_id_ctx.get("-")
        logger.error(f"Configuration error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Configuration Error",
                "detail": str(exc),
                "request_id": req_id,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = request_id_ctx.get("-")
        logger.exception(f"Unhandled exception on request {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": str(exc) if app.debug else "An unexpected error occurred.",
                "request_id": req_id,
            },
        )
