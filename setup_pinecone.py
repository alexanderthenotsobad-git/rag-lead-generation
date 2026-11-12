#!/usr/bin/env python3
"""Create/verify the Pinecone index at the MiniLM dimension (384).

Safety: the original version of this script deleted the live index on every
run and recreated it at 768 dims (the abandoned Gemini size).  This version
creates only when missing, verifies the dimension when present, and requires
``--recreate --yes`` before any destructive action.

Examples:
    python setup_pinecone.py
    python setup_pinecone.py --recreate --yes   # destructive, explicit
    python setup_pinecone.py --mock
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_leads.config import EMBED_DIM, EMBED_MODEL, load_settings  # noqa: E402
from rag_leads.store import VectorStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true",
                        help="delete and rebuild an existing/wrong-dimension index")
    parser.add_argument("--yes", action="store_true",
                        help="confirm the destructive --recreate action")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args(argv)

    if args.recreate and not args.yes:
        print("--recreate is destructive; re-run with --recreate --yes", file=sys.stderr)
        return 2

    try:
        settings = load_settings(required=["pinecone"], mode="mock" if args.mock else None)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    store = VectorStore(settings)
    print(f"Mode: {settings.mode.upper()}")
    try:
        info = store.ensure_index(
            recreate=args.recreate, confirm_recreate=args.yes
        )
    except Exception as exc:
        print(f"Index setup failed: {exc}", file=sys.stderr)
        return 1

    print(f"Index: {info['name']}")
    print(f"Dimension: {info['dimension']} (model {EMBED_MODEL}, expected {EMBED_DIM})")
    print(f"Status: {'created' if info['created'] else 'already existed'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
