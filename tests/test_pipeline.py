from __future__ import annotations

from rag_leads.pipeline import build_records, group_matches

PLACE = {
    "place_id": "ChIJtest",
    "name": "Test Kitchen",
    "address": "1 Test St",
    "rating": 4.1,
    "review_count": 10,
    "price_level": "PRICE_LEVEL_MODERATE",
}


def test_build_records_one_vector_per_review():
    reviews = [
        {"text": "First review", "rating": 5},
        {"text": "Second review", "rating": 2},
        {"text": "   ", "rating": 1},  # blank, must be dropped
    ]
    records = build_records(PLACE, reviews)
    assert [r["id"] for r in records] == ["ChIJtest_0", "ChIJtest_1"]
    assert [r["metadata"]["review_index"] for r in records] == [0, 1]
    assert records[0]["metadata"]["text"] == "First review"
    assert records[1]["metadata"]["review_rating"] == 2
    assert all(r["metadata"]["restaurant_id"] == "ChIJtest" for r in records)


def test_build_records_dedupes_identical_reviews():
    reviews = [{"text": "same text"}, {"text": "  same   text "}, {"text": "other"}]
    records = build_records(PLACE, reviews)
    assert len(records) == 2
    assert [r["metadata"]["text"] for r in records] == ["same text", "other"]


def test_build_records_requires_place_id():
    try:
        build_records({"name": "x"}, [{"text": "hi"}])
    except ValueError as exc:
        assert "place_id" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def _match(restaurant_id: str, text: str, score: float) -> dict:
    return {
        "id": f"{restaurant_id}_x",
        "score": score,
        "metadata": {
            "restaurant_id": restaurant_id,
            "name": restaurant_id.upper(),
            "text": text,
            "price_level": "PRICE_LEVEL_MODERATE",
        },
    }


def test_group_matches_regroups_and_sorts():
    matches = [
        _match("b", "b1", 0.5),
        _match("a", "a1", 0.9),
        _match("b", "b2", 0.7),
        _match("a", "a2", 0.2),
    ]
    groups = group_matches(matches)
    assert [g.restaurant_id for g in groups] == ["a", "b"]
    assert groups[0].best_score == 0.9
    # Reviews inside a group are ordered by their own score.
    assert groups[1].reviews == ["b2", "b1"]


def test_group_matches_dedupes_identical_review_text():
    matches = [
        _match("a", "same text", 0.9),
        _match("a", "same text", 0.8),
        _match("a", "different", 0.7),
    ]
    groups = group_matches(matches)
    assert groups[0].reviews == ["same text", "different"]


def test_group_matches_skips_missing_restaurant_id():
    matches = [{"id": "x", "score": 1.0, "metadata": {"text": "orphan"}}]
    assert group_matches(matches) == []
