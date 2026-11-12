"""HasData Google Maps Reviews client.

HasData accepts a Google ``placeId`` directly (the ``ChIJ...`` id from Places)
and returns full review text in ``snippet`` plus pre-computed ``topics`` and
``placeInfo``.  Each call costs 10 credits regardless of review count, so this
module counts calls and callers must budget before looping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from .config import HASDATA_CREDITS_PER_CALL, Settings
from .mock import MOCK_REVIEWS
from .util import with_retries

HASDATA_ENDPOINT = "https://api.hasdata.com/scrape/google-maps/reviews"


class HasDataError(RuntimeError):
    pass


@dataclass
class ReviewBatch:
    reviews: list[dict] = field(default_factory=list)
    calls: int = 0
    place_info: dict[str, Any] = field(default_factory=dict)

    @property
    def credits_spent(self) -> int:
        return self.calls * HASDATA_CREDITS_PER_CALL


def fetch_reviews(
    settings: Settings,
    place_id: str,
    *,
    max_pages: int = 1,
) -> ReviewBatch:
    """Fetch reviews for one place, following ``nextPageToken`` if present.

    ``max_pages`` bounds spend: every page is another 10-credit call.
    """
    if not place_id:
        raise HasDataError("place_id is required")

    if settings.is_mock:
        return ReviewBatch(
            reviews=[dict(r) for r in MOCK_REVIEWS.get(place_id, [])],
            calls=1,
        )

    headers = {"x-api-key": settings.key("hasdata_api_key")}
    batch = ReviewBatch()
    token: str | None = None

    for _ in range(max(1, max_pages)):
        params: dict[str, str] = {"placeId": place_id}
        if token:
            params["nextPageToken"] = token

        def call(params=params) -> requests.Response:
            response = requests.get(
                HASDATA_ENDPOINT, headers=headers, params=params, timeout=45
            )
            if response.status_code >= 500 or response.status_code == 429:
                response.raise_for_status()
            return response

        response = with_retries(call)
        batch.calls += 1

        if response.status_code != 200:
            raise HasDataError(
                f"HasData reviews failed for {place_id} "
                f"({response.status_code}): {response.text[:300]}"
            )

        payload = response.json()
        if not batch.place_info:
            batch.place_info = payload.get("placeInfo") or {}

        reviews = payload.get("reviews") or payload.get("data") or []
        batch.reviews.extend(_normalize_review(r) for r in reviews)

        token = payload.get("nextPageToken") or (payload.get("pagination") or {}).get(
            "nextPageToken"
        )
        if not token or not reviews:
            break

    return batch


def _normalize_review(review: dict) -> dict:
    text = (
        review.get("snippet")
        or review.get("text")
        or review.get("reviewText")
        or ""
    )
    text = " ".join(str(text).split())
    return {
        "text": text,
        "rating": review.get("rating"),
        "author": review.get("author") or review.get("authorName"),
        "date": review.get("date") or review.get("relativeDate"),
        "topics": review.get("topics") or [],
    }
