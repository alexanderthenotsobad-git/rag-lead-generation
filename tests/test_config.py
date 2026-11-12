from __future__ import annotations

import pytest
from rag_leads.places import normalize_price_levels

@pytest.fixture
def no_dotenv(monkeypatch):
    """Prevent load_dotenv() from re-reading .env during a test."""
    monkeypatch.setattr("rag_leads.config.load_dotenv", lambda *a, **kw: None)

    

from rag_leads.config import (
    ConfigError,
    Rectangle,
    estimate_hasdata_credits,
    load_settings,
)
from rag_leads.places import normalize_price_levels


def test_rectangle_accepts_valid_corners():
    rect = Rectangle(low=(34.02, -118.28), high=(34.07, -118.22))
    restriction = rect.as_restriction()
    assert restriction["rectangle"]["low"] == {"latitude": 34.02, "longitude": -118.28}
    assert restriction["rectangle"]["high"]["latitude"] == 34.07


@pytest.mark.parametrize(
    "low,high",
    [
        ((34.07, -118.28), (34.02, -118.22)),  # inverted latitude
        ((34.02, -118.22), (34.07, -118.28)),  # inverted longitude
    ],
)
def test_rectangle_rejects_inverted_corners(low, high):
    with pytest.raises(ConfigError):
        Rectangle(low=low, high=high)


def test_rectangle_parse():
    rect = Rectangle.parse("34.02,-118.28,34.07,-118.22")
    assert rect.low == (34.02, -118.28)
    assert rect.high == (34.07, -118.22)


def test_rectangle_parse_rejects_wrong_arity():
    with pytest.raises(ConfigError):
        Rectangle.parse("34.02,-118.28,34.07")


def test_credit_estimate():
    assert estimate_hasdata_credits(0) == 0
    assert estimate_hasdata_credits(5) == 50
    assert estimate_hasdata_credits(5, pages_per_restaurant=2) == 100


def test_price_level_short_names():
    assert normalize_price_levels(["MODERATE", "expensive"]) == [
        "PRICE_LEVEL_MODERATE",
        "PRICE_LEVEL_EXPENSIVE",
    ]


def test_price_level_rejects_unknown():
    with pytest.raises(Exception):
        normalize_price_levels(["CHEAP"])


def test_mock_mode_needs_no_keys(monkeypatch):
    for key in (
        "PINECONE_API_KEY",
        "HASDATA_API_KEY",
        "GOOGLE_PLACES_API_KEY",
        "HUGGINGFACE_API_TOKEN",
        "HF_TOKEN",
        "DEEPSEEK_API_KEY",
        "RAG_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = load_settings(required=["pinecone", "embeddings"], mode="mock")
    assert settings.is_mock
    assert settings.mode == "mock"


def test_auto_mode_falls_back_to_mock_without_keys(monkeypatch, no_dotenv):
    for key in ("PINECONE_API_KEY", "HUGGINGFACE_API_TOKEN", "HF_TOKEN", "RAG_MODE"):
        monkeypatch.delenv(key, raising=False)
    settings = load_settings(required=["pinecone", "embeddings"])
    assert settings.is_mock


def test_live_mode_fails_fast_without_keys(monkeypatch, no_dotenv):
    for key in ("PINECONE_API_KEY", "RAG_MODE"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError):
        load_settings(required=["pinecone"], mode="live")
