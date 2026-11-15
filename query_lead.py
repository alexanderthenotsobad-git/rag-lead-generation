#!/usr/bin/env python3
"""Reader: retrieve review chunks, regroup, classify, and generate pitches.

Reads only -- never ingests. Reviews from different restaurants are never mixed
in one prompt. Before a pitch is generated, retrieved reviews pass three gates:

1. rating gate   -- 1-3 stars are complaint candidates; 4-5 stars are praise
2. keyword gate  -- the review must mention an allergen/ingredient term
3. LLM classifier -- COMPLAINT / PRAISE / IRRELEVANT, with a required quote

Only COMPLAINT reviews feed the pitch prompt.

Examples
--------
    python query_lead.py --no-llm --top-k 50
    python query_lead.py --restaurants 3 --max-classify 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_leads.classify import ReviewClassifier  # noqa: E402
from rag_leads.config import Settings, load_settings  # noqa: E402
from rag_leads.deepseek import PitchGenerator  # noqa: E402
from rag_leads.embeddings import EmbeddingClient  # noqa: E402
from rag_leads.gates import candidate_matches  # noqa: E402
from rag_leads.pipeline import DEFAULT_QUERY, group_matches  # noqa: E402
from rag_leads.places import normalize_price_levels  # noqa: E402
from rag_leads.prompts import NO_SIGNAL, build_pitch_prompt  # noqa: E402
from rag_leads.store import VectorStore  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=DEFAULT_QUERY, help="pain-point query text")
    parser.add_argument("--top-k", type=int, default=50,
                        help="review chunks to retrieve before regrouping (default 50)")
    parser.add_argument("--restaurants", type=int, default=3,
                        help="how many restaurants to evaluate (default 3)")
    parser.add_argument("--max-classify", type=int, default=5,
                        help="candidate reviews classified per restaurant (default 5)")
    parser.add_argument("--no-classifier", action="store_true",
                        help="skip the LLM classifier; pitch from cheap-gate candidates")
    parser.add_argument("--price-level", action="append", default=None)
    parser.add_argument("--no-llm", action="store_true",
                        help="show retrieved evidence only; do not call DeepSeek")
    parser.add_argument("--margin", type=float, default=0.0,
                        help="evidence margin fraction below the top score (default 0)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.top_k < 1 or args.restaurants < 1:
        print("--top-k and --restaurants must be >= 1", file=sys.stderr)
        return 2
    if args.max_classify < 1 and not args.no_classifier:
        print("--max-classify must be >= 1 unless --no-classifier is set", file=sys.stderr)
        return 2

    required = ["pinecone", "embeddings"] + ([] if args.no_llm else ["llm"])
    try:
        settings: Settings = load_settings(required=required)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    levels = normalize_price_levels(args.price_level)
    store = VectorStore(settings)
    embedder = EmbeddingClient(settings)
    generator = None if args.no_llm else PitchGenerator(settings)

    classifier = None
    if not args.no_llm and not args.no_classifier:
        classifier = ReviewClassifier(settings)

    print("Mode: LIVE")
    print(f"Index: {settings.pinecone_index_name} / namespace {settings.namespace}")
    print(f"Filter: price_level in {levels}")
    print(f"Classifier: {'off' if classifier is None else 'on'}")
    print(f"Query: {args.query[:140]}...")

    try:
        vector = embedder.embed([args.query])[0]
        matches = store.query(
            vector,
            top_k=args.top_k,
            filter={"price_level": {"$in": levels}},
        )
    except Exception as exc:
        print(f"Query failed: {exc}", file=sys.stderr)
        return 1

    groups = group_matches(matches)
    if not groups:
        print("\nNo matches. Run ingest_data.py first, or widen --price-level.")
        return 1

    # Optional evidence margin: drop restaurants far below the best match.
    top_score = groups[0].best_score
    if args.margin > 0 and top_score > 0:
        cutoff = top_score * (1.0 - args.margin)
        groups = [g for g in groups if g.best_score >= cutoff]

    print(f"\nRetrieved {len(matches)} chunks across {len(groups)} restaurant(s).")

    results = []
    for group in groups[: args.restaurants]:
        # Classification is the only per-candidate LLM cost, so cap only then.
        candidate_limit = None if (args.no_classifier or args.no_llm) else args.max_classify
        candidates = candidate_matches(group.matches, limit=candidate_limit)
        candidate_reviews = [
            (match.get("metadata") or {}).get("text", "")
            for match in candidates
        ]
        candidate_reviews = [text for text in candidate_reviews if text]

        classified: list[dict] = []
        complaint_reviews: list[str] = []

        if classifier is not None:
            for match in candidates:
                text = (match.get("metadata") or {}).get("text", "")
                if not text:
                    continue
                try:
                    label, quote = classifier.classify(text)
                except Exception as exc:
                    print(f"\n{group.name}: classifier error: {exc}", file=sys.stderr)
                    continue
                classified.append({"label": label, "quote": quote, "text": text[:300]})
                if label == "COMPLAINT":
                    complaint_reviews.append(quote or text)
        elif args.no_classifier and not args.no_llm:
            # Debug path: trust the cheap gates without the LLM precision layer.
            complaint_reviews = list(candidate_reviews)

        if args.no_llm:
            pitch, refused = None, None
        elif not complaint_reviews:
            pitch, refused = NO_SIGNAL, True
        else:
            prompt = build_pitch_prompt(group.as_restaurant(), complaint_reviews)
            try:
                pitch = generator.generate(prompt)
            except Exception as exc:
                print(f"\n{group.name}: LLM error: {exc}", file=sys.stderr)
                pitch, refused = None, None
            else:
                refused = pitch.startswith(NO_SIGNAL)

        results.append(
            {
                "restaurant_id": group.restaurant_id,
                "name": group.name,
                "address": group.address,
                "price_level": group.price_level,
                "score": round(group.best_score, 4),
                "candidate_count": len(candidates),
                "candidate_reviews": candidate_reviews,
                "classified": classified,
                "complaint_reviews": complaint_reviews,
                "reviews": group.reviews,
                "pitch": pitch,
                "no_signal": refused,
            }
        )

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    for i, result in enumerate(results, 1):
        print("\n" + "=" * 72)
        print(f"{i}. {result['name']}  (score {result['score']:.4f}, {result['price_level']})")
        print(f"   {result['address']}")
        print(
            f"   Candidates: {result['candidate_count']} | "
            f"complaints: {len(result['complaint_reviews'])}"
        )
        if result["complaint_reviews"]:
            print("   Complaint evidence:")
            for review in result["complaint_reviews"][:5]:
                print(f"     - {review[:240]}")
        else:
            print("   Top retrieved evidence:")
            for review in result["reviews"][:5]:
                print(f"     - {review[:240]}")

        if result["no_signal"]:
            print(f"\n   Pitch: {NO_SIGNAL}")
        elif result["pitch"]:
            print(f"\n   Pitch: {result['pitch']}")
        else:
            print("\n   Pitch: (skipped)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
