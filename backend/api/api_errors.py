"""
Structured API error responses and global exception handlers.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.services.cycle_manager import cycle_manager

_log = logging.getLogger(__name__)


def error_payload(
    message: str,
    *,
    details: Optional[str] = None,
    stage: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    body: dict = {
        "success": False,
        "error": message,
    }
    if details:
        body["details"] = details
    if stage:
        body["stage"] = stage
    if extra:
        body.update(extra)
    return body


def success_wrapper(data: dict) -> dict:
    if "success" in data:
        return data
    return {"success": True, **data}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            payload = {"success": False, **detail}
        else:
            payload = error_payload(str(detail))
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "Request validation failed",
                details=str(exc.errors())[:500],
            ),
        )

    @app.exception_handler(TimeoutError)
    async def timeout_handler(request: Request, exc: TimeoutError):
        stage = None
        try:
            stage = cycle_manager.status().get("current_stage")
        except Exception:
            pass
        return JSONResponse(
            status_code=503,
            content=error_payload(
                "Operation timed out",
                details=str(exc),
                stage=stage,
            ),
        )

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception):
        _log.exception("Unhandled API error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "Internal server error",
                details=str(exc)[:300],
            ),
        )
