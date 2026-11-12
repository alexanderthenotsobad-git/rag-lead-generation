"""Small shared helpers: retries, vector normalization, text hygiene."""

from __future__ import annotations

import math
import time
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")


class RetryError(RuntimeError):
    pass


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 20.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn`` with exponential backoff.

    The pipeline talks to three flaky paid APIs (HasData, Hugging Face,
    DeepSeek) plus Pinecone.  A transient 429/5xx should not burn a run.
    """
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as exc:  # noqa: PERF203 - retry loop is intentional
            last = exc
            if attempt == attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            sleep(delay)
    raise RetryError(f"call failed after {attempts} attempts: {last}") from last


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Unit-normalize a vector.  Zero vectors are returned unchanged."""
    norm = math.sqrt(sum(float(v) * float(v) for v in vector))
    if norm == 0.0:
        return [0.0 for _ in vector]
    return [float(v) / norm for v in vector]


def mean_rows(rows: Sequence[Sequence[float]]) -> list[float]:
    """Column-wise mean; used when an API returns token-level embeddings."""
    if not rows:
        raise ValueError("cannot average zero rows")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("ragged rows cannot be averaged")
    count = len(rows)
    return [sum(float(row[i]) for row in rows) / count for i in range(width)]


def truncate_for_embedding(text: str, max_chars: int = 1_000) -> str:
    """Hard-cap text so truncation is explicit instead of silent.

    ``all-MiniLM-L6-v2`` has a ~256-token context window.  Reviews are already
    short, but truncated/concatenated inputs were the original bug.
    """
    text = " ".join((text or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def dedupe_texts(texts: Iterable[str]) -> list[str]:
    """Drop exact duplicate review snippets while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for text in texts:
        key = " ".join((text or "").split()).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def batched(items: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    for start in range(0, len(items), size):
        yield items[start : start + size]
