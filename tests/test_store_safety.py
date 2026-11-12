from __future__ import annotations

from types import SimpleNamespace

import pytest

from rag_leads.config import Settings
from rag_leads.store import VectorStore, VectorStoreError


def _live_settings() -> Settings:
    return Settings(
        mode="live",
        pinecone_api_key="test-key",
        pinecone_index_name="idx",
        namespace="restaurants",
        hasdata_api_key=None,
        google_places_api_key=None,
        huggingface_api_token=None,
        deepseek_api_key=None,
    )


class FakePinecone:
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self.deleted = False
        self.created: dict | None = None

    def has_index(self, name: str) -> bool:
        return True

    def describe_index(self, name: str):
        return SimpleNamespace(dimension=self.dimension, metric="cosine")

    def delete_index(self, name: str) -> None:
        self.deleted = True

    def create_index(self, **kwargs):
        self.created = kwargs
        self.dimension = kwargs["dimension"]


def test_existing_wrong_dimension_is_not_deleted():
    store = VectorStore(_live_settings())
    store._pc = FakePinecone(dimension=768)

    with pytest.raises(VectorStoreError, match="768"):
        store.ensure_index()

    assert store._pc.deleted is False


def test_recreate_requires_confirmation():
    store = VectorStore(_live_settings())
    store._pc = FakePinecone(dimension=768)

    with pytest.raises(VectorStoreError, match="confirmation"):
        store.ensure_index(recreate=True, confirm_recreate=False)

    assert store._pc.deleted is False


def test_recreate_with_confirmation_rebuilds_at_384():
    store = VectorStore(_live_settings())
    store._pc = FakePinecone(dimension=768)

    info = store.ensure_index(recreate=True, confirm_recreate=True)

    assert store._pc.deleted is True
    assert info["created"] is True
    assert store._pc.created is not None
    assert store._pc.created["dimension"] == 384
    assert store._pc.created["metric"] == "cosine"


def test_correct_dimension_is_left_alone():
    store = VectorStore(_live_settings())
    store._pc = FakePinecone(dimension=384)

    info = store.ensure_index()

    assert info == {"name": "idx", "dimension": 384, "created": False}
    assert store._pc.deleted is False
