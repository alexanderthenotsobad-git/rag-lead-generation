#!/usr/bin/env python3
"""Pinecone stats checker -- not a discovery script.

Example:
    python fetch_data.py
    python fetch_data.py --mock
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_leads.config import EMBED_DIM, load_settings  # noqa: E402
from rag_leads.store import VectorStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(required=["pinecone"], mode="mock" if args.mock else None)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    store = VectorStore(settings)
    try:
        stats = store.stats()
    except Exception as exc:
        print(f"Could not read index stats: {exc}", file=sys.stderr)
        return 1

    dimension = stats.get("dimension")
    print(f"Mode: {settings.mode.upper()}")
    print(f"Index: {settings.pinecone_index_name}")
    print(f"Total records in index: {stats['total_vector_count']}")
    print(f"Dimension: {dimension} (expected {EMBED_DIM})")
    print(f"Namespaces: {stats.get('namespaces') or {}}")

    if dimension != EMBED_DIM:
        print(
            f"\nWARNING: index dimension {dimension} != {EMBED_DIM}. "
            "Upserts and queries will fail. Do not recreate blindly; see README.",
            file=sys.stderr,
        )
        return 1
    if not stats["total_vector_count"]:
        print("\nIndex is empty. Run ingest_data.py first.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
