"""Canonical filesystem paths for the backend package."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
BACKEND_DATA_DIR = BACKEND_DIR / "data"
BACKEND_LOGS_DIR = BACKEND_DIR / "logs"
BACKEND_EVAL_DIR = BACKEND_DIR / "evaluation"
BACKEND_DEBUG_TRACES_DIR = BACKEND_DIR / "debug_traces"
PROJECT_DATA_DIR = ROOT_DIR / "data"
