from __future__ import annotations

from rag_leads.classify import ReviewClassifier, parse_classification
from rag_leads.config import load_settings
from rag_leads.mock import mock_classify


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


def test_mock_classify_contract():
    assert mock_classify(
        "The menu is confusing and nothing is labeled."
    ).startswith("LABEL: COMPLAINT")
    assert mock_classify(
        "Amazing options for celiacs; knowledgeable staff."
    ).startswith("LABEL: PRAISE")
    assert mock_classify(
        "Great steak and friendly service."
    ).startswith("LABEL: IRRELEVANT")


def test_classifier_mock_mode():
    settings = load_settings(mode="mock")
    classifier = ReviewClassifier(settings)

    complaint_label, complaint_quote = classifier.classify(
        "The menu is confusing and nothing is labeled."
    )
    assert complaint_label == "COMPLAINT"
    assert complaint_quote

    praise_label, _ = classifier.classify(
        "Amazing options for celiacs; knowledgeable staff."
    )
    assert praise_label == "PRAISE"
