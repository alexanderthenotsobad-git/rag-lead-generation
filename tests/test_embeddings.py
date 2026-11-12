from __future__ import annotations

import math

import pytest

from rag_leads.config import EMBED_DIM
from rag_leads.embeddings import EmbeddingError, coerce_vectors
from rag_leads.mock import mock_embed_text


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))


def test_flat_vector():
    vectors = coerce_vectors([0.5] * EMBED_DIM, expected_count=1)
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBED_DIM
    assert _norm(vectors[0]) == pytest.approx(1.0)


def test_pooled_batch():
    raw = [[0.1] * EMBED_DIM, [0.2] * EMBED_DIM, [0.3] * EMBED_DIM]
    vectors = coerce_vectors(raw, expected_count=3)
    assert len(vectors) == 3
    assert all(len(v) == EMBED_DIM for v in vectors)
    assert all(_norm(v) == pytest.approx(1.0) for v in vectors)


def test_token_matrix_is_mean_pooled():
    raw = [[1.0] * EMBED_DIM, [3.0] * EMBED_DIM]
    vectors = coerce_vectors(raw, expected_count=1)
    assert len(vectors) == 1
    assert vectors[0][0] == pytest.approx(1.0 / math.sqrt(EMBED_DIM))
    assert max(vectors[0]) - min(vectors[0]) == pytest.approx(0.0)


def test_batch_of_token_matrices():
    raw = [
        [[1.0] * EMBED_DIM, [3.0] * EMBED_DIM],
        [[2.0] * EMBED_DIM, [4.0] * EMBED_DIM],
    ]
    vectors = coerce_vectors(raw, expected_count=2)
    assert len(vectors) == 2
    assert all(_norm(v) == pytest.approx(1.0) for v in vectors)


def test_wrong_dimension_raises():
    with pytest.raises(EmbeddingError):
        coerce_vectors([[0.1] * 10], expected_count=1)


def test_single_vector_for_many_inputs_raises():
    with pytest.raises(EmbeddingError):
        coerce_vectors([0.1] * EMBED_DIM, expected_count=3)


def test_mock_embedding_is_deterministic_and_normalized():
    a = mock_embed_text("no vegan options and the menu is confusing")
    b = mock_embed_text("no vegan options and the menu is confusing")
    c = mock_embed_text("great steak and attentive service")
    assert a == b
    assert a != c
    assert len(a) == EMBED_DIM
    assert _norm(a) == pytest.approx(1.0)
