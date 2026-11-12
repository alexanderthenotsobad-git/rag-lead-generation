#!/usr/bin/env python3
"""Writer: discover restaurants, fetch reviews, chunk per review, embed, upsert.

This is the only script that writes to Pinecone.  Keeping it separate from
``query_lead.py`` means querying never re-triggers ingestion.

Examples
--------
    python ingest_data.py --mock --max-restaurants 3
    python ingest_data.py --max-restaurants 5 --dry-run
    python ingest_data.py --max-restaurants 5 --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_leads.config import (  # noqa: E402
    DEFAULT_BOX,
    Settings,
    estimate_hasdata_credits,
    load_settings,
)
from rag_leads.embeddings import EmbeddingClient  # noqa: E402
from rag_leads.hasdata import fetch_reviews  # noqa: E402
from rag_leads.pipeline import build_records  # noqa: E402
from rag_leads.places import search_restaurants  # noqa: E402
from rag_leads.store import VectorStore  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-restaurants", type=int, default=5,
                        help="restaurants to ingest (default 5; each costs 10 HasData credits)")
    parser.add_argument("--text-query", default="restaurants")
    parser.add_argument("--price-level", action="append", default=None,
                        help="repeatable; MODERATE / EXPENSIVE / VERY_EXPENSIVE")
    parser.add_argument("--box", default=None,
                        help="low_lat,low_lng,high_lat,high_lng "
                             "(default 34.02,-118.28,34.07,-118.22)")
    parser.add_argument("--max-reviews", type=int, default=50,
                        help="cap reviews embedded per restaurant (default 50)")
    parser.add_argument("--max-pages", type=int, default=1,
                        help="HasData pages per restaurant (each page costs 10 credits)")
    parser.add_argument("--dry-run", action="store_true",
                        help="discover and print the plan without spending credits")
    parser.add_argument("--yes", action="store_true",
                        help="confirm live HasData spending")
    parser.add_argument("--mock", action="store_true", help="force offline fixtures")
    parser.add_argument("--no-create-index", action="store_true",
                        help="fail instead of creating a missing index")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_restaurants < 1:
        print("--max-restaurants must be >= 1", file=sys.stderr)
        return 2
    if args.max_pages < 1:
        print("--max-pages must be >= 1", file=sys.stderr)
        return 2

    mode = "mock" if args.mock else None
    try:
        settings: Settings = load_settings(
            required=["pinecone", "places", "hasdata", "embeddings"], mode=mode
        )
    except Exception as exc:  # ConfigError
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    from rag_leads.config import Rectangle

    box = Rectangle.parse(args.box) if args.box else DEFAULT_BOX

    print(f"Mode: {settings.mode.upper()}")
    print(f"Index: {settings.pinecone_index_name} / namespace {settings.namespace}")
    print("Discovering restaurants via Google Places Text Search...")
    try:
        places = search_restaurants(
            settings,
            text_query=args.text_query,
            max_results=args.max_restaurants,
            price_levels=args.price_level,
            box=box,
        )
    except Exception as exc:
        print(f"Discovery failed: {exc}", file=sys.stderr)
        return 1

    if not places:
        print("No restaurants returned. Widen the box or change --text-query.")
        return 1

    credits = estimate_hasdata_credits(len(places), args.max_pages)
    print(f"\n{len(places)} restaurant(s) -> ~{credits} HasData credits "
          f"({len(places)} calls x {args.max_pages} page(s) x 10):")
    for i, place in enumerate(places, 1):
        print(f"  {i:>2}. {place['name']}  [{place['price_level']}]  {place['place_id']}")

    if args.dry_run:
        print("\nDry run: no credits spent, nothing written.")
        return 0

    if not settings.is_mock and not args.yes:
        print(
            "\nRefusing to spend credits without confirmation. Re-run with --yes.",
            file=sys.stderr,
        )
        return 2

    store = VectorStore(settings)
    if not args.no_create_index:
        try:
            info = store.ensure_index()
            state = "created" if info.get("created") else "verified"
            print(f"\nIndex {info.get('name')} {state} at {info.get('dimension')} dims.")
        except Exception as exc:
            print(f"Index check failed: {exc}", file=sys.stderr)
            return 1
    else:
        print("\nSkipping index creation (--no-create-index).")

    embedder = EmbeddingClient(settings)
    total_records = 0
    total_credits = 0
    failures: list[str] = []

    for i, place in enumerate(places, 1):
        name = place["name"]
        print(f"\n[{i}/{len(places)}] {name}")
        try:
            batch = fetch_reviews(
                settings, place["place_id"], max_pages=args.max_pages
            )
            total_credits += batch.credits_spent
            reviews = batch.reviews[: args.max_reviews]
            records = build_records(place, reviews)
            if not records:
                print("  no usable review text; skipped")
                continue

            vectors = embedder.embed([r["metadata"]["text"] for r in records])
            for record, vector in zip(records, vectors):
                record["values"] = vector

            written = store.upsert(records)
            total_records += written
            print(f"  {len(reviews)} reviews -> {written} vectors upserted")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"  FAILED: {exc}", file=sys.stderr)

    print("\n--- Ingest summary ---")
    print(f"Vectors upserted: {total_records}")
    print(f"HasData credits spent: {total_credits}")
    if failures:
        print(f"Failures ({len(failures)}):", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
