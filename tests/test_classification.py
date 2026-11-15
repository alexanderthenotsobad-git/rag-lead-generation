from __future__ import annotations

from rag_leads.classify import parse_classification


def test_parse_label_and_quote():
    label, quote = parse_classification(
        'LABEL: COMPLAINT\nQUOTE: "The server did not know."'
    )
    assert label == "COMPLAINT"
    assert quote == "The server did not know."


def test_complaint_without_quote_is_downgraded():
    assert parse_classification("LABEL: COMPLAINT\nQUOTE: NONE") == ("IRRELEVANT", "")


def test_bare_label_is_tolerated():
    assert parse_classification("PRAISE") == ("PRAISE", "")


def test_unknown_label_is_irrelevant():
    label, _quote = parse_classification("LABEL: MAYBE\nQUOTE: something")
    assert label == "IRRELEVANT"


def test_praise_preserves_quote():
    label, quote = parse_classification(
        'LABEL: PRAISE\nQUOTE: "They were wonderful about my allergy."'
    )
    assert label == "PRAISE"
    assert quote == "They were wonderful about my allergy."
