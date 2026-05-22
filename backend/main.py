"""Backward-compatible entrypoint — prefer ``backend.api.main:app``."""

from backend.api.main import app

__all__ = ["app"]
