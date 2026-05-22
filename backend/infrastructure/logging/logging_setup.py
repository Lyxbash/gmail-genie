"""
Rotating file logging for Gmail Genie (app, cycle, errors).
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.paths import BACKEND_LOGS_DIR

LOG_DIR = BACKEND_LOGS_DIR

_CYCLE_LOGGER = "gmail_genie.cycle"


def setup_logging(*, production: bool = False) -> None:
    """Configure root + dedicated cycle logger with rotating files."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    env_level = (os.environ.get("LOG_LEVEL") or "").strip().upper()
    if env_level in ("DEBUG", "INFO", "WARNING", "ERROR"):
        level = getattr(logging, env_level)
    else:
        level = logging.WARNING if production else logging.INFO

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    for name, filename in (
        ("gmail_genie.app", "app.log"),
        (_CYCLE_LOGGER, "cycle.log"),
        ("gmail_genie.errors", "error.log"),
    ):
        handler = RotatingFileHandler(
            LOG_DIR / filename,
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(fmt)
        handler.setLevel(level)
        logging.getLogger(name).addHandler(handler)

    err_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    err_handler.setFormatter(fmt)
    err_handler.setLevel(logging.ERROR)
    root.addHandler(err_handler)


def get_cycle_logger() -> logging.Logger:
    return logging.getLogger(_CYCLE_LOGGER)
