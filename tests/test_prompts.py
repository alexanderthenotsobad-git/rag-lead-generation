from __future__ import annotations

from rag_leads.prompts import NO_SIGNAL, build_pitch_prompt


def test_prompt_contains_exact_guardrail_once():
    prompt = build_pitch_prompt(
        {"name": "Verde", "address": "123 St", "price_level": "PRICE_LEVEL_MODERATE"},
        ["no vegan options", "menu is confusing"],
    )
    assert prompt.count(NO_SIGNAL) == 1
    assert NO_SIGNAL == "No relevant pain points found."


def test_prompt_has_no_stray_artifacts():
    prompt = build_pitch_prompt({"name": "X"}, ["review text"])
    for artifact in ("Pitch:", '"""', "Pitch :"):
        assert artifact not in prompt


def test_prompt_scopes_reviews_to_one_restaurant():
    prompt = build_pitch_prompt(
        {"name": "Verde Kitchen"}, ["the menu is confusing", "no gluten free options"]
    )
    assert "Verde Kitchen" in prompt
    assert "the menu is confusing" in prompt
    assert "no gluten free options" in prompt


def test_prompt_caps_reviews_and_chars():
    prompt = build_pitch_prompt(
        {"name": "X"}, [f"review {i}" for i in range(30)], max_reviews=3
    )
    assert "review 0" in prompt
    assert "review 2" in prompt
    assert "review 3" not in prompt


def test_empty_reviews_still_produces_valid_prompt():
    prompt = build_pitch_prompt({"name": "X"}, [])
    assert "no reviews retrieved" in prompt
    assert NO_SIGNAL in prompt
