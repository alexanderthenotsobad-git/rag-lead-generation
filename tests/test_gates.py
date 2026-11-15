from __future__ import annotations

from rag_leads.gates import (
    candidate_matches,
    gate_review,
    has_keyword,
    is_complaint_candidate,
    rating_bucket,
)
from rag_leads.pipeline import build_records


def test_rating_bucket():
    assert rating_bucket(1) == "complaint"
    assert rating_bucket(3) == "complaint"
    assert rating_bucket(4) == "praise"
    assert rating_bucket(None) == "unknown"
    assert rating_bucket("n/a") == "unknown"


def test_has_keyword():
    assert has_keyword("I have a shellfish allergy")
    assert has_keyword("nothing is gluten free")
    assert has_keyword("the ingredients are unclear")
    assert not has_keyword("great steak and friendly service")


def test_gate_review():
    assert gate_review("shellfish allergy, server guessed", 2)["complaint_candidate"] is True
    assert gate_review("amazing gluten free options", 5)["complaint_candidate"] is False
    # Unknown ratings pass only when the keyword gate also fires.
    assert gate_review("shellfish allergy, server guessed", None)["complaint_candidate"] is True
    assert gate_review("great steak", 1)["complaint_candidate"] is False


def test_is_complaint_candidate_falls_back_for_old_records():
    assert is_complaint_candidate({"text": "nut allergy", "review_rating": 2}) is True
    assert is_complaint_candidate({"text": "great steak", "review_rating": 2}) is False
    assert is_complaint_candidate({"text": "nut allergy", "review_rating": 5}) is False


def test_candidate_matches_orders_by_score_and_limits():
    matches = [
        {"score": 0.2, "metadata": {"text": "nut allergy", "review_rating": 2}},
        {"score": 0.9, "metadata": {"text": "gluten free praise", "review_rating": 5}},
        {"score": 0.7, "metadata": {"text": "dairy intolerance", "review_rating": 1}},
    ]
    out = candidate_matches(matches, limit=1)
    assert len(out) == 1
    assert out[0]["score"] == 0.7


def test_build_records_sets_gate_metadata():
    place = {
        "place_id": "ChIJx",
        "name": "X",
        "address": "Y",
        "price_level": "PRICE_LEVEL_MODERATE",
    }
    reviews = [
        {"text": "The menu did not disclose my shellfish allergy.", "rating": 2},
        {"text": "They were amazing with my gluten allergy.", "rating": 5},
        {"text": "I have a nut allergy.", "rating": None},
    ]
    records = build_records(place, reviews)

    assert records[0]["metadata"]["complaint_candidate"] is True
    assert records[0]["metadata"]["rating_bucket"] == "complaint"
    assert records[1]["metadata"]["complaint_candidate"] is False
    assert records[1]["metadata"]["rating_bucket"] == "praise"
    assert records[2]["metadata"]["complaint_candidate"] is True
    assert records[2]["metadata"]["rating_bucket"] == "unknown"
