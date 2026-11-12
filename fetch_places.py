#!/usr/bin/env python3
"""Standalone discovery preview: Google Places Text Search (New).

Spends no HasData credits and writes nothing.  Use this to tune the rectangle,
text query, and price levels before running ingest_data.py.

Example:
    python fetch_places.py --max-results 20
    python fetch_places.py --box 34.02,-118.28,34.07,-118.22 --price-level MODERATE
    python fetch_places.py --mock
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_leads.config import DEFAULT_BOX, Rectangle, load_settings  # noqa: E402
from rag_leads.places import search_restaurants  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-results", type=int, default=20, help="1..20")
    parser.add_argument("--text-query", default="restaurants")
    parser.add_argument("--price-level", action="append", default=None)
    parser.add_argument("--box", default=None,
                        help="low_lat,low_lng,high_lat,high_lng")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--mock", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        settings = load_settings(required=["places"], mode="mock" if args.mock else None)
        box = Rectangle.parse(args.box) if args.box else DEFAULT_BOX
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print(f"Mode: {settings.mode.upper()}")
    try:
        places = search_restaurants(
            settings,
            text_query=args.text_query,
            max_results=args.max_results,
            price_levels=args.price_level,
            box=box,
        )
    except Exception as exc:
        print(f"Discovery failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(places, indent=2))
        return 0

    print(f"\nFound {len(places)} restaurant(s):")
    for place in places:
        print("-" * 60)
        print(f"  {place['name']}")
        print(f"  ID:          {place['place_id']}")
        print(f"  Address:     {place['address']}")
        print(f"  Rating:      {place['rating']}  ({place['review_count']} reviews)")
        print(f"  Price level: {place['price_level']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
