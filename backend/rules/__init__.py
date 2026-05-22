"""
Gmail Genie modular rule classification package.

Public API
----------
classify_by_rules : Main entry point for deterministic email classification.
build_result      : Standardized result dict factory.
"""

from backend.rules.result_builder import build_result
from backend.rules.rule_engine import classify_by_rules

__all__ = [
    "classify_by_rules",
    "build_result",
]
