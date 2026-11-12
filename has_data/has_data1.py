#!/usr/bin/env python3
"""HasData smoke test: fetch reviews for one placeId.

Costs 10 credits per page.  Always run this on 2-5 restaurants before scaling.

Example:
    python has_data/has_data1.py --place-id ChIJj6arSYLHwoAROfRRqiOfX2s
    python has_data/has_data1.py --place-id ChIJ... --yes --max-pages 1
    python has_data/has_data1.py --place-id ChIJ... --mock
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag_leads.config import HASDATA_CREDITS_PER_CALL, load_settings  # noqa: E402
from rag_leads.hasdata import fetch_reviews  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--place-id", required=True)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--yes", action="store_true", help="confirm credit spend")
    parser.add_argument("--json", action="store_true", help="dump raw review JSON")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args(argv)

    if args.max_pages < 1:
        print("--max-pages must be >= 1", file=sys.stderr)
        return 2

    try:
        settings = load_settings(required=["hasdata"], mode="mock" if args.mock else None)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    cost = args.max_pages * HASDATA_CREDITS_PER_CALL
    if not settings.is_mock and not args.yes:
        print(
            f"This will call HasData up to {args.max_pages} time(s) "
            f"(~{cost} credits). Re-run with --yes.",
            file=sys.stderr,
        )
        return 2

    try:
        batch = fetch_reviews(settings, args.place_id, max_pages=args.max_pages)
    except Exception as exc:
        print(f"HasData request failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(batch.reviews, indent=2))
        return 0

    print(f"Mode: {settings.mode.upper()}")
    print(f"placeId: {args.place_id}")
    print(f"Reviews: {len(batch.reviews)}")
    print(f"Calls: {batch.calls} (~{batch.credits_spent} credits)")
    if batch.place_info:
        name = batch.place_info.get("title") or batch.place_info.get("name")
        if name:
            print(f"Place: {name}")
    for i, review in enumerate(batch.reviews[:5], 1):
        print(f"\n[{i}] rating={review.get('rating')} topics={review.get('topics')}")
        print(f"    {review.get('text', '')[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
