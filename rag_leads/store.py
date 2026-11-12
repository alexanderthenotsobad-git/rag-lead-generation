"""Pinecone vector store wrapper.

Guardrails baked in:

* The index is created at 384 dims (MiniLM), never 768 (the abandoned Gemini
  size), and never deleted implicitly.
* If an existing index has the wrong dimension, we raise instead of wiping it.
* Upserts are batched and idempotent because review ids are deterministic
  (``{place_id}_{j}``).
"""

from __future__ import annotations

from typing import Sequence

from .config import EMBED_DIM, INDEX_CLOUD, INDEX_REGION, Settings
from .mock import MockVectorStore

UPSERT_BATCH_SIZE = 100


class VectorStoreError(RuntimeError):
    pass


class VectorStore:
    def __init__(self, settings: Settings, *, seed_mock: bool = True) -> None:
        self.settings = settings
        self._index = None
        self._pc = None
        self._mock = MockVectorStore() if settings.is_mock else None
        if self._mock is not None and seed_mock:
            self._seed_mock()

    def _seed_mock(self) -> None:
        """Preload the offline corpus so `query_lead.py --mock` works alone."""
        from .mock import MOCK_PLACES, MOCK_REVIEWS, mock_embed_text
        from .pipeline import build_records

        vectors: list[dict] = []
        for place in MOCK_PLACES:
            for record in build_records(place, MOCK_REVIEWS.get(place["place_id"], [])):
                record["values"] = mock_embed_text(record["metadata"]["text"])
                vectors.append(record)
        self._mock.upsert(vectors, namespace=self.settings.namespace)

    # --- connection -----------------------------------------------------

    def _pinecone(self):
        if self._pc is None:
            from pinecone import Pinecone

            self._pc = Pinecone(api_key=self.settings.key("pinecone_api_key"))
        return self._pc

    def index(self):
        if self.settings.is_mock:
            return self._mock
        if self._index is None:
            self._index = self._pinecone().Index(self.settings.pinecone_index_name)
        return self._index

    def ensure_index(self, *, recreate: bool = False, confirm_recreate: bool = False) -> dict:
        """Create the index if missing; verify dimension if present.

        ``recreate`` is the only destructive path and requires an explicit
        second confirmation.  The original ``setup_pinecone.py`` deleted the
        live index on every run -- that is how you lose a working corpus.
        """
        if self.settings.is_mock:
            return {"name": "mock", "dimension": EMBED_DIM, "created": True}

        pc = self._pinecone()
        name = self.settings.pinecone_index_name

        if pc.has_index(name):
            info = pc.describe_index(name)
            dimension = int(info.dimension)
            if dimension != EMBED_DIM:
                if not recreate:
                    raise VectorStoreError(
                        f"index {name!r} has dimension {dimension}, but this pipeline "
                        f"requires {EMBED_DIM}. Refusing to delete it automatically. "
                        "Re-run with --recreate --yes if you really mean to rebuild."
                    )
                if not confirm_recreate:
                    raise VectorStoreError(
                        "recreate requested without confirmation (pass --yes)"
                    )
                pc.delete_index(name)
            else:
                return {"name": name, "dimension": dimension, "created": False}

        from pinecone import ServerlessSpec

        pc.create_index(
            name=name,
            dimension=EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=INDEX_CLOUD, region=INDEX_REGION),
            deletion_protection="disabled",
        )
        return {"name": name, "dimension": EMBED_DIM, "created": True}

    # --- data -----------------------------------------------------------

    def upsert(
        self,
        vectors: Sequence[dict],
        namespace: str | None = None,
    ) -> int:
        if not vectors:
            return 0
        namespace = namespace or self.settings.namespace
        if self.settings.is_mock:
            return self._mock.upsert(vectors, namespace=namespace)

        index = self.index()
        total = 0
        for start in range(0, len(vectors), UPSERT_BATCH_SIZE):
            batch = list(vectors[start : start + UPSERT_BATCH_SIZE])
            index.upsert(vectors=batch, namespace=namespace)
            total += len(batch)
        return total

    def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 50,
        filter: dict | None = None,
        namespace: str | None = None,
    ) -> list[dict]:
        namespace = namespace or self.settings.namespace
        if self.settings.is_mock:
            result = self._mock.query(
                vector, top_k=top_k, filter=filter, namespace=namespace
            )
            return result["matches"]

        result = self.index().query(
            vector=list(vector),
            top_k=top_k,
            filter=filter,
            namespace=namespace,
            include_metadata=True,
        )
        return list(result.get("matches", []))

    def stats(self) -> dict:
        if self.settings.is_mock:
            return self._mock.describe_index_stats()

        info = self._pinecone().describe_index(self.settings.pinecone_index_name)
        raw = self.index().describe_index_stats()
        return {
            "total_vector_count": raw.get("total_vector_count", 0),
            "dimension": int(info.dimension),
            "metric": getattr(info, "metric", "cosine"),
            "namespaces": raw.get("namespaces", {}),
        }
