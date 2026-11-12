"""Chunking and regrouping logic.

The unit of retrieval is **one review**, not one restaurant.  Each review is a
separate vector with a stable id ``{place_id}_{j}`` and a ``restaurant_id`` in
metadata.  That is what lets a single sentence ("nothing is labeled vegan")
surface instead of being averaged into an 8,000-character blob.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .util import dedupe_texts

DEFAULT_QUERY = (
    "Customers complaining the restaurant had no vegan, gluten-free, or healthy "
    "options, couldn't tell what ingredients were in a dish, found the menu "
    "confusing or hard to read, or got sick because dietary information was unclear."
)


@dataclass
class RestaurantGroup:
    restaurant_id: str
    metadata: dict
    matches: list[dict] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.metadata.get("name") or "Unknown restaurant"

    @property
    def address(self) -> str:
        return self.metadata.get("address") or ""

    @property
    def price_level(self) -> str:
        return self.metadata.get("price_level") or ""

    @property
    def best_score(self) -> float:
        return max((float(m.get("score", 0.0)) for m in self.matches), default=0.0)

    @property
    def reviews(self) -> list[str]:
        texts = [
            (m.get("metadata") or {}).get("text", "")
            for m in self.matches
        ]
        return dedupe_texts(t for t in texts if t and t.strip())

    def as_restaurant(self) -> dict:
        return {
            "name": self.name,
            "address": self.address,
            "price_level": self.price_level,
        }


def build_records(place: dict, reviews: Sequence[dict]) -> list[dict]:
    """Turn one restaurant's reviews into one record per review.

    ``id`` is deterministic, so re-ingesting a place overwrites rather than
    duplicating.  ``metadata["text"]`` is mandatory -- without it DeepSeek has
    no context and the app degrades into a restaurant directory.
    """
    place_id = place.get("place_id", "")
    if not place_id:
        raise ValueError("place is missing place_id")

    records: list[dict] = []
    seen: set[str] = set()
    for review in reviews:
        text = " ".join(str(review.get("text") or "").split())
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)

        metadata = {
            "restaurant_id": place_id,
            "name": place.get("name", ""),
            "address": place.get("address", ""),
            "price_level": place.get("price_level", "PRICE_LEVEL_UNSPECIFIED"),
            "review_index": len(records),
            "text": text,
        }
        for key in ("rating", "review_count"):
            value = place.get(key)
            if value is not None:
                metadata[key] = value
        if review.get("rating") is not None:
            metadata["review_rating"] = review["rating"]
        if review.get("author"):
            metadata["author"] = str(review["author"])
        if review.get("topics"):
            metadata["topics"] = [str(t) for t in review["topics"]]

        records.append(
            {
                "id": f"{place_id}_{len(records)}",
                "values": [],  # filled by the embedder
                "metadata": metadata,
            }
        )
    return records


def group_matches(matches: Iterable[dict]) -> list[RestaurantGroup]:
    """Regroup review-level matches by restaurant, best restaurant first."""
    groups: dict[str, RestaurantGroup] = {}
    for match in matches:
        metadata = match.get("metadata") or {}
        restaurant_id = metadata.get("restaurant_id")
        if not restaurant_id:
            continue
        if restaurant_id not in groups:
            groups[restaurant_id] = RestaurantGroup(
                restaurant_id=restaurant_id, metadata=dict(metadata)
            )
        groups[restaurant_id].matches.append(match)

    ordered = sorted(
        groups.values(),
        key=lambda g: (-g.best_score, g.name.lower()),
    )
    for group in ordered:
        group.matches.sort(key=lambda m: float(m.get("score", 0.0)), reverse=True)
    return ordered
