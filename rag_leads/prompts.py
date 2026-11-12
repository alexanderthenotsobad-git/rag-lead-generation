"""Prompt construction for per-restaurant pitch generation.

The guardrail is load-bearing: without it DeepSeek will confidently invent a
pain point from "great steak, nice service".  The exact refusal string is
defined once here and compared literally after generation.
"""

from __future__ import annotations

NO_SIGNAL = "No relevant pain points found."

SYSTEM_PROMPT = (
    "You are a B2B sales analyst for an AI-powered restaurant menu app. "
    "The app reads a menu at the ingredient level and generates personalized "
    "recommendations for diners based on dietary needs, macros, and restrictions."
)

PITCH_INSTRUCTIONS = """\
You are evaluating ONE restaurant using ONLY the customer reviews provided.

Restaurant: {name}
Address: {address}
Price level: {price_level}

Reviews:
{reviews}

Task:
1. Decide whether these reviews contain a genuine customer pain point about:
   - menu confusion or difficulty understanding dishes,
   - missing or unclear ingredient / allergen / nutrition information,
   - unavailable vegan, vegetarian, gluten-free, or healthier options,
   - a bad experience caused by unclear dietary information.
2. If such a signal exists, write ONE short paragraph (max 110 words) pitching
   our AI-powered menu app to the owner. Ground every claim in the reviews
   above. Do not invent details, statistics, or complaints.
3. If the reviews do NOT contain such a signal, respond with exactly:
{no_signal}
Do not add anything else in that case.
"""


def build_pitch_prompt(
    restaurant: dict,
    reviews: list[str],
    *,
    max_reviews: int = 12,
    max_chars: int = 4_000,
) -> str:
    """One prompt per restaurant; never mix reviews across restaurants."""
    cleaned = ["- " + " ".join(r.split()) for r in reviews if r and r.strip()]
    cleaned = cleaned[:max_reviews]
    joined = "\n".join(cleaned)[:max_chars]

    return PITCH_INSTRUCTIONS.format(
        name=restaurant.get("name", "Unknown restaurant"),
        address=restaurant.get("address", "Unknown address"),
        price_level=restaurant.get("price_level", "unknown"),
        reviews=joined or "- (no reviews retrieved)",
        no_signal=NO_SIGNAL,
    )
