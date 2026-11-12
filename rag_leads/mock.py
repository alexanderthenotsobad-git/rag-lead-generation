"""Offline fixtures and deterministic fakes.

These exist for two reasons:

1. Tests must never touch a paid API.
2. The mock corpus deliberately contains a *praise* review about gluten-free
   accommodation.  It reproduces the project's central strategic finding:
   cosine similarity matches topic vocabulary, not sentiment, so a glowing
   review ("options for celiacs ... knowledgeable") can outrank a complaint.
"""

from __future__ import annotations

import hashlib
import re
from typing import Sequence

from .config import EMBED_DIM
from .util import l2_normalize

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "had", "has", "have", "i", "in", "is", "it", "its", "of", "on", "or",
    "our", "so", "that", "the", "their", "them", "they", "this", "to", "was",
    "we", "were", "with", "you", "your",
}

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS]


def mock_embed_text(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Hashed bag-of-words embedding.

    Deterministic, dependency-free, and *lexically* meaningful: reviews that
    share words with the query get a higher cosine score.  It is not semantic,
    which is exactly what the real MiniLM model gives us for free -- and the
    limitation the strategy memo is about.
    """
    vector = [0.0] * dim
    tokens = _tokens(text)
    # Unigrams plus bigrams give a little word-order signal.
    features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % dim
        sign = 1.0 if (value >> 63) & 1 else -1.0
        vector[index] += sign
    return l2_normalize(vector)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    return sum(float(x) * float(y) for x, y in zip(a, b))


# --- Mock discovery corpus -----------------------------------------------------

MOCK_PLACES: list[dict] = [
    {
        "place_id": "ChIJmockverde000000000000",
        "name": "Verde Kitchen",
        "address": "1234 W Olive St, Los Angeles, CA 90015",
        "rating": 3.8,
        "review_count": 412,
        "price_level": "PRICE_LEVEL_MODERATE",
        "types": ["restaurant", "mediterranean_restaurant"],
        "location": {"latitude": 34.0502, "longitude": -118.2610},
    },
    {
        "place_id": "ChIJmockpraise00000000000",
        "name": "Celiac & Co.",
        "address": "88 S Grand Ave, Los Angeles, CA 90012",
        "rating": 4.7,
        "review_count": 980,
        "price_level": "PRICE_LEVEL_EXPENSIVE",
        "types": ["restaurant", "italian_restaurant"],
        "location": {"latitude": 34.0551, "longitude": -118.2510},
    },
    {
        "place_id": "ChIJmocksteak00000000000",
        "name": "Taylor's Steak House",
        "address": "3361 W 8th St, Los Angeles, CA 90005",
        "rating": 4.4,
        "review_count": 2100,
        "price_level": "PRICE_LEVEL_EXPENSIVE",
        "types": ["restaurant", "steak_house"],
        "location": {"latitude": 34.0570, "longitude": -118.2990},
    },
]

MOCK_REVIEWS: dict[str, list[dict]] = {
    "ChIJmockverde000000000000": [
        {
            "text": "The menu is confusing and nothing is labeled. I could not tell "
                    "which dishes were vegan or gluten free, and the server did not know "
                    "what ingredients were in the sauce.",
            "rating": 2,
            "author": "Dana R.",
            "date": "2026-08-14",
            "topics": ["menu", "dietary"],
        },
        {
            "text": "No vegan options at all and the gluten free choices were unclear. "
                    "I asked about dairy and got a shrug. Hard to eat here with an allergy.",
            "rating": 1,
            "author": "Miguel S.",
            "date": "2026-07-02",
            "topics": ["vegan", "allergy"],
        },
        {
            "text": "Good hummus and friendly service, but I wish the menu listed "
                    "calories and allergens. I left not knowing what I had eaten.",
            "rating": 3,
            "author": "Priya K.",
            "date": "2026-06-19",
            "topics": ["nutrition", "menu"],
        },
    ],
    "ChIJmockpraise00000000000": [
        {
            "text": "Amazing options for celiacs. The staff and kitchen are knowledgeable "
                    "and actually give a shit about cross contamination. The gluten free "
                    "pasta was incredible.",
            "rating": 5,
            "author": "Jordan L.",
            "date": "2026-09-01",
            "topics": ["gluten free", "celiac"],
        },
        {
            "text": "They walked me through every ingredient on the menu and adjusted "
                    "the dish for my dairy allergy. Best dietary transparency in the city.",
            "rating": 5,
            "author": "Sam W.",
            "date": "2026-05-22",
            "topics": ["allergy", "menu"],
        },
    ],
    "ChIJmocksteak00000000000": [
        {
            "text": "Great steak, strong cocktails, and attentive service. Expensive but "
                    "worth it for a special occasion.",
            "rating": 5,
            "author": "Chris B.",
            "date": "2026-04-11",
            "topics": ["steak", "service"],
        },
        {
            "text": "Portions are huge and the creamed spinach is a must. The room is "
                    "loud but the food quality is excellent.",
            "rating": 4,
            "author": "Alex G.",
            "date": "2026-03-30",
            "topics": ["portion", "food"],
        },
    ],
}


class MockVectorStore:
    """In-memory cosine index that mimics the subset of Pinecone we use."""

    def __init__(self) -> None:
        self._vectors: dict[str, dict] = {}

    def upsert(self, vectors: Sequence[dict], namespace: str | None = None) -> int:
        for item in vectors:
            self._vectors[item["id"]] = {
                "values": list(item["values"]),
                "metadata": dict(item.get("metadata", {})),
                "namespace": namespace,
            }
        return len(vectors)

    def query(
        self,
        vector: Sequence[float],
        top_k: int = 10,
        filter: dict | None = None,
        namespace: str | None = None,
        include_metadata: bool = True,
    ) -> dict:
        matches = []
        for vector_id, item in self._vectors.items():
            if namespace is not None and item["namespace"] != namespace:
                continue
            if not _matches_filter(item["metadata"], filter):
                continue
            score = cosine(vector, item["values"])
            matches.append(
                {
                    "id": vector_id,
                    "score": score,
                    "metadata": item["metadata"] if include_metadata else {},
                }
            )
        matches.sort(key=lambda m: m["score"], reverse=True)
        return {"matches": matches[:top_k]}

    def describe_index_stats(self) -> dict:
        namespaces: dict[str, int] = {}
        for item in self._vectors.values():
            key = item["namespace"] or ""
            namespaces[key] = namespaces.get(key, 0) + 1
        return {
            "total_vector_count": len(self._vectors),
            "dimension": EMBED_DIM,
            "namespaces": namespaces,
        }


def _matches_filter(metadata: dict, filter: dict | None) -> bool:
    if not filter:
        return True
    for field, condition in filter.items():
        value = metadata.get(field)
        if isinstance(condition, dict):
            if "$eq" in condition and value != condition["$eq"]:
                return False
            if "$in" in condition and value not in condition["$in"]:
                return False
            if "$ne" in condition and value == condition["$ne"]:
                return False
        elif value != condition:
            return False
    return True


def mock_llm(prompt: str) -> str:
    """Deterministic stand-in for DeepSeek.

    Mirrors the guardrail: if no dietary/menu pain vocabulary is present in the
    *review evidence* (not the instructions), the model must refuse to invent a
    pitch.
    """
    evidence = prompt
    if "Reviews:" in prompt:
        evidence = prompt.split("Reviews:", 1)[1]
    if "Task:" in evidence:
        evidence = evidence.split("Task:", 1)[0]
    lowered = evidence.lower()
    complaint_markers = (
        "confusing", "unclear", "nothing is labeled", "did not know", "didn't know",
        "no vegan", "no gluten", "wish", "shrug", "hard to eat", "could not tell",
        "couldn't tell",
    )
    praise_markers = (
        "amazing", "incredible", "best ", "knowledgeable", "walked me through",
        "give a shit", "excellent", "perfect",
    )
    if any(marker in lowered for marker in complaint_markers):
        pass  # a complaint is present; fall through to the pitch
    elif any(marker in lowered for marker in praise_markers):
        return "No relevant pain points found."
    else:
        signals = ("vegan", "gluten", "allerg", "celiac", "ingredient", "calorie", "menu")
        if not any(signal in lowered for signal in signals):
            return "No relevant pain points found."
    name = "this restaurant"
    for line in prompt.splitlines():
        if line.lower().startswith("restaurant:"):
            name = line.split(":", 1)[1].strip() or name
            break
    return (
        f"{name}'s own reviews show customers asking for ingredient and dietary "
        "clarity that the menu does not provide. Our app turns each dish into "
        "structured ingredient and allergen data, so guests get answers before "
        "they order -- reducing staff time and protecting average check size."
    )
