# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Hybrid search scoring utilities.

Provides normalisation, reciprocal-rank fusion (RRF), deduplication, and a
lightweight suffix-stripping stemmer used by the keyword search path.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Stop words
# ---------------------------------------------------------------------------

STOP_WORDS: set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "get", "got", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't",
    "it", "it's", "its", "itself", "just", "let's", "me", "might", "more",
    "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves",
    "out", "over", "own", "same", "shan't", "she", "should", "shouldn't",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "were", "weren't", "what", "when", "where", "which", "while",
    "who", "whom", "why", "will", "with", "won't", "would", "wouldn't",
    "you", "your", "yours", "yourself", "yourselves",
}

# ---------------------------------------------------------------------------
# Simple suffix-stripping stemmer
# ---------------------------------------------------------------------------

# Ordered from longest suffix to shortest so the first match wins.
_SUFFIX_RULES: list[tuple[str, int, str]] = [
    # (suffix, min_stem_length, replacement)
    ("tion", 4, ""),
    ("ment", 4, ""),
    ("ness", 4, ""),
    ("ies", 2, "i"),
    ("ing", 4, ""),
    ("ly", 4, ""),
    ("ed", 4, ""),
    ("s", 4, ""),
]


def simple_stem(word: str) -> str:
    """Apply lightweight suffix stripping to *word*.

    The stemmer only modifies words whose stem (after stripping) is at least
    *min_stem_length* characters long, which avoids over-stemming short words.
    """
    lower = word.lower()
    for suffix, min_stem, replacement in _SUFFIX_RULES:
        if lower.endswith(suffix):
            stem = lower[: -len(suffix)]
            if len(stem) >= min_stem:
                return stem + replacement
    return lower


# ---------------------------------------------------------------------------
# Score normalisation
# ---------------------------------------------------------------------------

def normalize_scores(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalise ``score`` values in *results* to the ``[0, 1]`` range.

    Uses min-max normalisation.  When all scores are equal (or only a single
    result is present), every score is set to ``1.0``.  The original dicts are
    **not** mutated; shallow copies are returned.
    """
    if not results:
        return []

    scores = [r["score"] for r in results]
    min_score = min(scores)
    max_score = max(scores)
    span = max_score - min_score

    out: list[dict[str, Any]] = []
    for r in results:
        copy = dict(r)
        if span == 0:
            copy["score"] = 1.0
        else:
            copy["score"] = (r["score"] - min_score) / span
        out.append(copy)
    return out


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    *result_lists: list[dict[str, Any]],
    weights: list[float] | None = None,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Combine multiple ranked result lists using weighted Reciprocal Rank Fusion.

    Each result list is expected to be sorted by descending score.  For every
    result at rank *r* (0-based) in list *i*, its RRF contribution is::

        weights[i] / (k + r + 1)

    Contributions from the same ``chunk_id`` across lists are summed.

    Parameters
    ----------
    *result_lists:
        Positional ranked result lists (dicts with ``chunk_id`` and ``score``).
    weights:
        Per-list weights.  Defaults to uniform ``1.0`` per list.
    k:
        RRF constant (default 60).

    Returns
    -------
    list[dict[str, Any]]
        Merged results sorted by descending fused score.
    """
    if not result_lists:
        return []

    if weights is None:
        weights = [1.0] * len(result_lists)

    fused: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}

    for list_idx, rlist in enumerate(result_lists):
        w = weights[list_idx] if list_idx < len(weights) else 1.0
        for rank, item in enumerate(rlist):
            cid = item["chunk_id"]
            contribution = w / (k + rank + 1)
            fused[cid] = fused.get(cid, 0.0) + contribution
            # Keep the first-seen metadata for each chunk.
            if cid not in metadata:
                metadata[cid] = {key: val for key, val in item.items() if key != "score"}

    combined: list[dict[str, Any]] = []
    for cid, score in fused.items():
        entry = dict(metadata[cid])
        entry["score"] = score
        combined.append(entry)

    combined.sort(key=lambda r: r["score"], reverse=True)
    return combined


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate_results(
    results: list[dict[str, Any]],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Deduplicate *results* by ``chunk_id``, keeping the highest score.

    Returns at most *top_k* results sorted by descending score.
    """
    seen: dict[str, dict[str, Any]] = {}
    for r in results:
        cid = r["chunk_id"]
        if cid not in seen or r["score"] > seen[cid]["score"]:
            seen[cid] = r

    deduped = sorted(seen.values(), key=lambda r: r["score"], reverse=True)
    return deduped[:top_k]
