"""Review classifier: COMPLAINT / PRAISE / IRRELEVANT with a required quote.

This is the third gate. The cheap gates in ``gates.py`` decide which reviews are
worth classifying; this module makes the final decision and returns the exact
sentence the pitch is allowed to cite.
"""

from __future__ import annotations

import re

from .config import DEEPSEEK_BASE_URL, LLM_MODEL, Settings
from .mock import mock_classify
from .prompts import CLASSIFIER_SYSTEM_PROMPT, build_classifier_prompt
from .util import with_retries

LABELS = ("COMPLAINT", "PRAISE", "IRRELEVANT")

_LABEL_RE = re.compile(r"LABEL\s*:\s*(COMPLAINT|PRAISE|IRRELEVANT)", re.IGNORECASE)
_QUOTE_RE = re.compile(r"QUOTE\s*:\s*(.+)", re.IGNORECASE)


def parse_classification(raw: str) -> tuple[str, str]:
    """Parse ``LABEL: ... / QUOTE: ...`` and enforce the quote requirement.

    A COMPLAINT without a quote is downgraded to IRRELEVANT: an unsupported
    complaint is exactly the failure mode the guardrail exists to prevent.
    """
    text = raw or ""
    label_match = _LABEL_RE.search(text)
    quote_match = _QUOTE_RE.search(text)

    label = "IRRELEVANT"
    if label_match:
        label = label_match.group(1).upper()
    else:
        # Tolerate a bare label ("COMPLAINT") from a terse model response.
        upper = text.strip().upper()
        for candidate in LABELS:
            if upper.startswith(candidate):
                label = candidate
                break

    quote = ""
    if quote_match:
        quote = quote_match.group(1).strip().strip('"').strip("'").strip()
    if quote.upper() == "NONE":
        quote = ""

    if label == "COMPLAINT" and not quote:
        return "IRRELEVANT", ""
    return label, quote


class ReviewClassifier:
    """DeepSeek-backed review classifier. Uses the deterministic fake in mock mode."""

    def __init__(
        self,
        settings: Settings,
        temperature: float = 0.0,
        max_tokens: int = 120,
    ) -> None:
        self.settings = settings
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def _live_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.key("deepseek_api_key"),
                base_url=DEEPSEEK_BASE_URL,
                timeout=60.0,
                max_retries=0,
            )
        return self._client

    def classify(self, review_text: str) -> tuple[str, str]:
        if self.settings.is_mock:
            return parse_classification(mock_classify(review_text))

        prompt = build_classifier_prompt(review_text)

        def call() -> str:
            response = self._live_client().chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("DeepSeek returned an empty classification")
            return content.strip()

        return parse_classification(with_retries(call, attempts=3, base_delay=2.0))
