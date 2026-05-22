"""
Travel and transport classification rules.

Travel is not a config category; high-confidence travel signals map to
``Receipts`` for bookings and ``General`` for informational updates.
"""

from __future__ import annotations

from typing import Optional

from backend.rules.domain_lists import TRAVEL_DOMAINS
from backend.rules.keyword_lists import TRAVEL_KEYWORDS
from backend.rules.result_builder import (
    EmailContext,
    build_result,
    contains_any,
    domain_matches,
)

CATEGORY_BOOKING = "Receipts"
CATEGORY_UPDATE = "General"


def classify_travel(ctx: EmailContext) -> Optional[dict]:
    """Classify flights, hotels, trains, and ride receipts."""
    booking_keywords = [
        "booking confirmed",
        "reservation confirmed",
        "trip confirmed",
        "e-ticket",
        "eticket",
        "boarding pass",
        "pnr",
        "hotel booking",
        "itinerary",
    ]

    if domain_matches(ctx.domain, TRAVEL_DOMAINS):
        if contains_any(ctx.combined, booking_keywords):
            return build_result(
                category=CATEGORY_BOOKING,
                confidence=0.95,
                reason="matched_travel_domain_booking",
            )
        return build_result(
            category=CATEGORY_UPDATE,
            confidence=0.90,
            reason="matched_travel_domain",
        )

    if contains_any(ctx.combined, TRAVEL_KEYWORDS):
        if contains_any(ctx.combined, booking_keywords):
            return build_result(
                category=CATEGORY_BOOKING,
                confidence=0.93,
                reason="matched_travel_booking_keywords",
            )
        return build_result(
            category=CATEGORY_UPDATE,
            confidence=0.88,
            reason="matched_travel_keywords",
        )

    return None
