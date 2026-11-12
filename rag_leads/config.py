"""Configuration, constants, and environment loading.

One rule matters more than the rest: the embedding model is
``all-MiniLM-L6-v2`` which produces **384** dimensions.  The Pinecone index
must match that exactly.  Gemini is intentionally absent from this codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Sequence

from dotenv import load_dotenv

# --- Model / storage constants -------------------------------------------------

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
EMBED_TOKEN_LIMIT = 256  # ~1,000 chars; anything longer is silently truncated

INDEX_NAME_DEFAULT = "rag-lead-idx"
INDEX_CLOUD = "aws"
INDEX_REGION = "us-east-1"
NAMESPACE = "restaurants"

LLM_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# HasData charges per review call, not per review returned.
HASDATA_CREDITS_PER_CALL = 10

DEFAULT_PRICE_LEVELS = ("PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE")

# Texts longer than this are truncated before embedding.  ``all-MiniLM-L6-v2``
# has a ~256 token window; keeping reviews near a single sentence keeps the
# signal sharp and makes the truncation explicit rather than silent.
MAX_EMBED_CHARS = 1_000

# Central LA rectangle used by the original scripts.  Text Search (New) only
# accepts a rectangle with explicit low/high corners -- circles and bare
# low/high pairs are rejected with HTTP 400.
DEFAULT_BOX = ((34.0200, -118.2800), (34.0700, -118.2200))


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Rectangle:
    low: tuple[float, float]
    high: tuple[float, float]

    def __post_init__(self) -> None:
        (low_lat, low_lng), (high_lat, high_lng) = self.low, self.high
        if not (-90 <= low_lat <= 90 and -90 <= high_lat <= 90):
            raise ConfigError(f"latitude out of range: {self.low!r} / {self.high!r}")
        if not (-180 <= low_lng <= 180 and -180 <= high_lng <= 180):
            raise ConfigError(f"longitude out of range: {self.low!r} / {self.high!r}")
        if not (low_lat < high_lat and low_lng < high_lng):
            raise ConfigError(
                "rectangle must have low.latitude < high.latitude and "
                f"low.longitude < high.longitude (got {self.low!r} / {self.high!r})"
            )

    def as_restriction(self) -> dict:
        return {
            "rectangle": {
                "low": {"latitude": self.low[0], "longitude": self.low[1]},
                "high": {"latitude": self.high[0], "longitude": self.high[1]},
            }
        }

    @classmethod
    def parse(cls, value: str) -> "Rectangle":
        """Parse ``low_lat,low_lng,high_lat,high_lng``."""
        try:
            parts = [float(p.strip()) for p in value.split(",")]
        except ValueError as exc:
            raise ConfigError(f"--box must be four numbers, got {value!r}") from exc
        if len(parts) != 4:
            raise ConfigError(f"--box must be low_lat,low_lng,high_lat,high_lng, got {value!r}")
        return cls(low=(parts[0], parts[1]), high=(parts[2], parts[3]))


@dataclass(frozen=True)
class Settings:
    mode: str  # "live" or "mock"
    pinecone_api_key: str | None
    pinecone_index_name: str
    namespace: str
    hasdata_api_key: str | None
    google_places_api_key: str | None
    huggingface_api_token: str | None
    deepseek_api_key: str | None

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

    def key(self, name: str) -> str:
        value = getattr(self, name)
        if not value:
            raise ConfigError(
                f"{name} is not set. Add it to .env or export it in the shell. "
                "Run with --mock to exercise the pipeline without API calls."
            )
        return value


_ENV_ALIASES = {
    "pinecone_api_key": ("PINECONE_API_KEY",),
    "hasdata_api_key": ("HASDATA_API_KEY",),
    "google_places_api_key": ("GOOGLE_PLACES_API_KEY", "GOOGLE_MAPS_API_KEY"),
    "huggingface_api_token": ("HUGGINGFACE_API_TOKEN", "HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN"),
    "deepseek_api_key": ("DEEPSEEK_API_KEY",),
}

_REQUIRED_FOR = {
    "pinecone": ("pinecone_api_key",),
    "hasdata": ("hasdata_api_key",),
    "places": ("google_places_api_key",),
    "embeddings": ("huggingface_api_token",),
    "llm": ("deepseek_api_key",),
}


def _first_env(names: Iterable[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def load_settings(
    required: Sequence[str] = (),
    mode: str | None = None,
) -> Settings:
    """Load settings and resolve mock vs live mode.

    ``mode`` is ``live``, ``mock``, or ``auto`` (default).  In ``auto`` mode the
    pipeline falls back to mock only when a key required *for this command* is
    missing, so ``fetch_data.py`` can talk to Pinecone without a HasData key.
    """
    load_dotenv(override=False)

    raw_mode = (mode or os.getenv("RAG_MODE", "auto")).strip().lower()
    if raw_mode not in {"auto", "live", "mock"}:
        raise ConfigError(f"RAG_MODE must be auto, live, or mock (got {raw_mode!r})")

    missing: list[str] = []
    for group in required:
        try:
            fields = _REQUIRED_FOR[group]
        except KeyError as exc:
            raise ConfigError(f"unknown required group {group!r}") from exc
        for field in fields:
            if not _first_env(_ENV_ALIASES[field]):
                missing.append(field)

    if raw_mode == "auto":
        raw_mode = "mock" if missing else "live"

    if raw_mode == "live" and missing:
        raise ConfigError(
            "live mode requested but missing keys: "
            + ", ".join(sorted(set(missing)))
            + ". Use --mock for an offline run."
        )

    return Settings(
        mode=raw_mode,
        pinecone_api_key=_first_env(_ENV_ALIASES["pinecone_api_key"]),
        pinecone_index_name=os.getenv("PINECONE_INDEX_NAME", INDEX_NAME_DEFAULT),
        namespace=os.getenv("PINECONE_NAMESPACE", NAMESPACE),
        hasdata_api_key=_first_env(_ENV_ALIASES["hasdata_api_key"]),
        google_places_api_key=_first_env(_ENV_ALIASES["google_places_api_key"]),
        huggingface_api_token=_first_env(_ENV_ALIASES["huggingface_api_token"]),
        deepseek_api_key=_first_env(_ENV_ALIASES["deepseek_api_key"]),
    )


def estimate_hasdata_credits(restaurant_count: int, pages_per_restaurant: int = 1) -> int:
    """Credits HasData will charge for ``restaurant_count`` review calls."""
    return max(0, restaurant_count) * max(1, pages_per_restaurant) * HASDATA_CREDITS_PER_CALL
