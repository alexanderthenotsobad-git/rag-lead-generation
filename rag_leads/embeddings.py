"""Hugging Face embedding client with shape coercion.

The inference API can return one of several shapes depending on whether the
server pools sentence-transformers output:

* ``(384,)``            -- one pooled sentence vector
* ``(n, 384)``          -- a pooled batch
* ``(seq, 384)``        -- token-level output for a single input
* ``(n, seq, 384)``     -- token-level output for a batch

Every shape is coerced to a list of 384-dim unit vectors, and a wrong
dimension fails loudly instead of writing garbage to Pinecone.
"""

from __future__ import annotations

from typing import Sequence

from .config import EMBED_DIM, EMBED_MODEL, MAX_EMBED_CHARS, Settings
from .mock import mock_embed_text
from .util import batched, l2_normalize, mean_rows, truncate_for_embedding, with_retries


class EmbeddingError(RuntimeError):
    pass


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_vector(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) > 0
        and all(_is_number(v) for v in value)
    )


def _checked(vector: Sequence[float], dim: int = EMBED_DIM) -> list[float]:
    values = [float(v) for v in vector]
    if len(values) != dim:
        raise EmbeddingError(
            f"expected a {dim}-dim embedding, got {len(values)}. "
            "The Pinecone index dimension and the embedding model must match."
        )
    return values


def coerce_vectors(raw: object, expected_count: int, dim: int = EMBED_DIM) -> list[list[float]]:
    """Normalize any supported API response shape into pooled unit vectors."""
    if expected_count < 1:
        raise ValueError("expected_count must be >= 1")

    data = raw.tolist() if hasattr(raw, "tolist") else raw

    if _is_vector(data):
        if expected_count != 1:
            raise EmbeddingError(
                f"got a single vector for {expected_count} inputs"
            )
        return [_checked(l2_normalize(data), dim)]

    if not isinstance(data, (list, tuple)) or not data:
        raise EmbeddingError(f"unexpected embedding response: {type(raw)!r}")

    first = data[0]

    if _is_vector(first):
        rows = [[float(v) for v in row] for row in data]
        if any(len(row) != dim for row in rows):
            # Token matrix stored transposed: (dim, seq).
            if len(rows) == dim and len({len(r) for r in rows}) == 1:
                seq = len(rows[0])
                columns = [[rows[r][c] for r in range(dim)] for c in range(seq)]
                return [_checked(l2_normalize(mean_rows(columns)), dim)]
            raise EmbeddingError(
                f"embedding rows are not {dim}-dim (got widths "
                f"{sorted({len(r) for r in rows})[:5]})"
            )
        if len(rows) == expected_count:
            return [_checked(l2_normalize(row), dim) for row in rows]
        if expected_count == 1:
            # Token-level output for one input: mean-pool the sequence.
            return [_checked(l2_normalize(mean_rows(rows)), dim)]
        raise EmbeddingError(
            f"got {len(rows)} vectors for {expected_count} inputs"
        )

    # Three-dimensional: batch of token matrices.
    if isinstance(first, (list, tuple)) and first and _is_vector(first[0]):
        if len(data) != expected_count:
            raise EmbeddingError(
                f"got {len(data)} token matrices for {expected_count} inputs"
            )
        pooled: list[list[float]] = []
        for item in data:
            rows = [[float(v) for v in row] for row in item]
            if any(len(row) != dim for row in rows):
                raise EmbeddingError(f"token matrix rows are not {dim}-dim")
            pooled.append(_checked(l2_normalize(mean_rows(rows)), dim))
        return pooled

    raise EmbeddingError(f"unexpected embedding response shape: {type(raw)!r}")


class EmbeddingClient:
    """Batch embedder.  Uses a deterministic fake in mock mode."""

    def __init__(self, settings: Settings, batch_size: int = 32) -> None:
        self.settings = settings
        self.batch_size = batch_size
        self._client = None

    def _live_client(self):
        if self._client is None:
            from huggingface_hub import InferenceClient

            self._client = InferenceClient(token=self.settings.key("huggingface_api_token"))
        return self._client

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [truncate_for_embedding(text, MAX_EMBED_CHARS) for text in texts]
        if not cleaned:
            return []
        if any(not text for text in cleaned):
            raise EmbeddingError("refusing to embed empty text")

        if self.settings.is_mock:
            return [mock_embed_text(text) for text in cleaned]

        vectors: list[list[float]] = []
        for batch in batched(cleaned, self.batch_size):
            raw = with_retries(
                lambda batch=batch: self._live_client().feature_extraction(
                    list(batch), model=EMBED_MODEL
                )
            )
            vectors.extend(coerce_vectors(raw, expected_count=len(batch)))
        return vectors
