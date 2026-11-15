"""Cheap deterministic gates applied before the LLM classifier.

Three gates, cheapest first:

1. **Rating gate** -- 1-3 stars are complaint candidates; 4-5 stars are treated
   as praise; missing ratings are retained but only become candidates when the
   keyword gate also fires.
2. **Keyword gate** -- the review must mention an allergen, ingredient, or
   dietary term.
3. **LLM classifier** -- ``ReviewClassifier`` makes the final
   COMPLAINT / PRAISE / IRRELEVANT decision and must return a supporting quote.

The gates are deliberately permissive. They reduce classifier volume and cost;
they do not decide truth. Only the classifier may mark a review as COMPLAINT.
"""

from __future__ import annotations

import re
from typing import Iterable

COMPLAINT_MAX_RATING = 3

# Allergen/ingredient terms plus the adjacent dietary vocabulary the VRS
# consultant also handles. Broad on purpose: the classifier is the precision
# layer, this is the recall layer.
KEYWORD_PATTERN = re.compile(
    r"\b(?:"
    r"allerg\w*|anaphyla\w*|celiac|coeliac|gluten|dairy|lactose|"
    r"nuts?|peanut\w*|shellfish|soy|eggs?|sesame|"
    r"ingredient\w*|cross[- ]contamination|intoleran\w*|"
    r"vegan|vegetarian|plant[- ]based"
    r")\b",
    re.IGNORECASE,
)


def rating_bucket(rating: object) -> str:
    """Return ``complaint`` (<= 3), ``praise`` (> 3), or ``unknown``."""
    if rating is None or rating == "":
        return "unknown"
    try:
        value = float(rating)
    except (TypeError, ValueError):
        return "unknown"
    return "complaint" if value <= COMPLAINT_MAX_RATING else "praise"


def has_keyword(text: str) -> bool:
    return bool(KEYWORD_PATTERN.search(text or ""))


def gate_review(text: str, rating: object) -> dict:
    """Compute the two cheap gate outcomes for one review."""
    bucket = rating_bucket(rating)
    keyword = has_keyword(text)
    return {
        "rating_bucket": bucket,
        "keyword_hit": keyword,
        # Unknown ratings are allowed through the rating gate, but the keyword
        # gate must still fire. This keeps sources without ratings usable.
        "complaint_candidate": bucket != "praise" and keyword,
    }


def is_complaint_candidate(metadata: dict) -> bool:
    """Read the stored gate flag, falling back for records ingested earlier."""
    stored = metadata.get("complaint_candidate")
    if stored is not None:
        return bool(stored)

    bucket = metadata.get("rating_bucket") or rating_bucket(metadata.get("review_rating"))
    if bucket == "praise":
        return False

    keyword = metadata.get("keyword_hit")
    if keyword is None:
        keyword = has_keyword(str(metadata.get("text") or ""))
    return bool(keyword)


def candidate_matches(matches: Iterable[dict], limit: int | None = None) -> list[dict]:
    """Filter and rank review matches that pass the cheap gates."""
    candidates = [
        match
        for match in matches
        if is_complaint_candidate(match.get("metadata") or {})
    ]
    candidates.sort(key=lambda match: float(match.get("score", 0.0)), reverse=True)
    if limit is not None:
        return candidates[:limit]
    return candidates
