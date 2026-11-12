"""Google Places API (New) Text Search client.

Text Search (New) rejects circle restrictions and bare low/high pairs; it
requires ``locationRestriction.rectangle`` with explicit ``low`` and ``high``
lat/lng objects.  This module always emits that shape.
"""

from __future__ import annotations

from typing import Sequence

import requests

from .config import DEFAULT_BOX, DEFAULT_PRICE_LEVELS, Rectangle, Settings
from .mock import MOCK_PLACES
from .util import with_retries

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.location",
        "places.types",
    ]
)

MAX_RESULTS_PER_CALL = 20


class PlacesError(RuntimeError):
    pass


def normalize_price_levels(values: Sequence[str] | None) -> list[str]:
    """Accept ``MODERATE`` or ``PRICE_LEVEL_MODERATE`` and return the enum form."""
    if not values:
        return list(DEFAULT_PRICE_LEVELS)
    out: list[str] = []
    for value in values:
        token = value.strip().upper()
        if not token.startswith("PRICE_LEVEL_"):
            token = f"PRICE_LEVEL_{token}"
        if token not in {
            "PRICE_LEVEL_INEXPENSIVE",
            "PRICE_LEVEL_MODERATE",
            "PRICE_LEVEL_EXPENSIVE",
            "PRICE_LEVEL_VERY_EXPENSIVE",
            "PRICE_LEVEL_FREE",
        }:
            raise PlacesError(f"unknown price level {value!r}")
        out.append(token)
    return out


def search_restaurants(
    settings: Settings,
    *,
    text_query: str = "restaurants",
    max_results: int = 20,
    price_levels: Sequence[str] | None = None,
    box: Rectangle | tuple[tuple[float, float], tuple[float, float]] = DEFAULT_BOX,
) -> list[dict]:
    """Run a Text Search and return normalized restaurant dicts."""
    if not 1 <= max_results <= MAX_RESULTS_PER_CALL:
        raise PlacesError(
            f"max_results must be 1..{MAX_RESULTS_PER_CALL} (got {max_results})"
        )

    rectangle = box if isinstance(box, Rectangle) else Rectangle(*box)
    levels = normalize_price_levels(price_levels)

    if settings.is_mock:
        return [
            dict(place)
            for place in MOCK_PLACES
            if place["price_level"] in levels
        ][:max_results]

    payload = {
        "textQuery": text_query,
        "maxResultCount": max_results,
        "priceLevels": levels,
        "locationRestriction": rectangle.as_restriction(),
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.key("google_places_api_key"),
        "X-Goog-FieldMask": FIELD_MASK,
    }

    def call() -> requests.Response:
        response = requests.post(PLACES_ENDPOINT, headers=headers, json=payload, timeout=30)
        if response.status_code >= 500 or response.status_code == 429:
            response.raise_for_status()
        return response

    response = with_retries(call)
    if response.status_code != 200:
        raise PlacesError(
            f"Places Text Search failed ({response.status_code}): {response.text[:500]}"
        )

    return [_normalize_place(place) for place in response.json().get("places", [])]


def _normalize_place(place: dict) -> dict:
    display = place.get("displayName") or {}
    location = place.get("location") or {}
    return {
        "place_id": place.get("id", ""),
        "name": display.get("text", "") or place.get("name", ""),
        "address": place.get("formattedAddress", ""),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "price_level": place.get("priceLevel", "PRICE_LEVEL_UNSPECIFIED"),
        "types": place.get("types", []),
        "location": {
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        },
    }
