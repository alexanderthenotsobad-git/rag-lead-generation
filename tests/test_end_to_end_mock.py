from __future__ import annotations

from rag_leads.config import load_settings
from rag_leads.deepseek import PitchGenerator
from rag_leads.embeddings import EmbeddingClient
from rag_leads.mock import MOCK_PLACES, MOCK_REVIEWS
from rag_leads.pipeline import DEFAULT_QUERY, build_records, group_matches
from rag_leads.prompts import NO_SIGNAL, build_pitch_prompt
from rag_leads.store import VectorStore


def _build_pipeline():
    settings = load_settings(mode="mock")
    store = VectorStore(settings, seed_mock=False)
    embedder = EmbeddingClient(settings)

    for place in MOCK_PLACES:
        records = build_records(place, MOCK_REVIEWS[place["place_id"]])
        vectors = embedder.embed([r["metadata"]["text"] for r in records])
        for record, vector in zip(records, vectors):
            record["values"] = vector
        store.upsert(records)

    return settings, store, embedder


def test_mock_ingest_writes_one_vector_per_review():
    _, store, _ = _build_pipeline()
    stats = store.stats()
    total_reviews = sum(len(v) for v in MOCK_REVIEWS.values())
    assert stats["total_vector_count"] == total_reviews


def test_query_regroups_by_restaurant_and_ranks_dietary_reviews():
    settings, store, embedder = _build_pipeline()
    vector = embedder.embed([DEFAULT_QUERY])[0]
    matches = store.query(
        vector,
        top_k=50,
        filter={"price_level": {"$in": ["PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE"]}},
    )
    groups = group_matches(matches)

    assert len(groups) == 3
    names = [g.name for g in groups]
    # The steakhouse has no menu/dietary vocabulary at all.
    assert names[-1] == "Taylor's Steak House"
    # The complaint restaurant and the praise restaurant both score high.
    assert {"Verde Kitchen", "Celiac & Co."} <= set(names[:2])


def test_praise_review_is_retrieved_alongside_complaints():
    """Documents the known flaw: embeddings match topic, not sentiment."""
    settings, store, embedder = _build_pipeline()
    matches = store.query(embedder.embed([DEFAULT_QUERY])[0], top_k=50)
    texts = " ".join((m["metadata"].get("text") or "") for m in matches).lower()
    assert "options for celiacs" in texts


def test_guardrail_refuses_to_pitch_steakhouse():
    settings, store, embedder = _build_pipeline()
    matches = store.query(embedder.embed([DEFAULT_QUERY])[0], top_k=50)
    groups = group_matches(matches)
    steak = next(g for g in groups if g.name == "Taylor's Steak House")

    prompt = build_pitch_prompt(steak.as_restaurant(), steak.reviews)
    response = PitchGenerator(settings).generate(prompt)

    assert response == NO_SIGNAL


def test_guardrail_refuses_praise_review():
    """Retrieval surfaces praise; generation must not turn it into a complaint."""
    settings, store, embedder = _build_pipeline()
    matches = store.query(embedder.embed([DEFAULT_QUERY])[0], top_k=50)
    groups = group_matches(matches)
    celiac = next(g for g in groups if g.name == "Celiac & Co.")

    prompt = build_pitch_prompt(celiac.as_restaurant(), celiac.reviews)
    response = PitchGenerator(settings).generate(prompt)

    assert response == NO_SIGNAL


def test_pitch_is_generated_for_restaurant_with_signal():
    settings, store, embedder = _build_pipeline()
    matches = store.query(embedder.embed([DEFAULT_QUERY])[0], top_k=50)
    groups = group_matches(matches)
    verde = next(g for g in groups if g.name == "Verde Kitchen")

    prompt = build_pitch_prompt(verde.as_restaurant(), verde.reviews)
    response = PitchGenerator(settings).generate(prompt)

    assert response != NO_SIGNAL
    assert "Verde Kitchen" in response
