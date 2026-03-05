# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for hybrid search scoring utilities."""

from __future__ import annotations


def test_normalize_scores_empty():
    from flydesk.knowledge.scoring import normalize_scores
    assert normalize_scores([]) == []


def test_normalize_scores_single():
    from flydesk.knowledge.scoring import normalize_scores
    results = [{"chunk_id": "c1", "score": 5.0}]
    normalized = normalize_scores(results)
    assert normalized[0]["score"] == 1.0


def test_normalize_scores_range():
    from flydesk.knowledge.scoring import normalize_scores
    results = [
        {"chunk_id": "c1", "score": 10.0},
        {"chunk_id": "c2", "score": 5.0},
        {"chunk_id": "c3", "score": 0.0},
    ]
    normalized = normalize_scores(results)
    assert normalized[0]["score"] == 1.0
    assert normalized[2]["score"] == 0.0
    assert 0.0 < normalized[1]["score"] < 1.0


def test_reciprocal_rank_fusion_combines():
    from flydesk.knowledge.scoring import reciprocal_rank_fusion
    semantic = [
        {"chunk_id": "c1", "score": 0.9},
        {"chunk_id": "c2", "score": 0.7},
    ]
    keyword = [
        {"chunk_id": "c2", "score": 0.8},
        {"chunk_id": "c3", "score": 0.6},
    ]
    combined = reciprocal_rank_fusion(semantic, keyword, weights=[0.7, 0.3])
    ids = [r["chunk_id"] for r in combined]
    assert "c1" in ids
    assert "c2" in ids
    assert "c3" in ids


def test_reciprocal_rank_fusion_empty():
    from flydesk.knowledge.scoring import reciprocal_rank_fusion
    assert reciprocal_rank_fusion() == []


def test_deduplicate_by_chunk_id():
    from flydesk.knowledge.scoring import deduplicate_results
    results = [
        {"chunk_id": "c1", "score": 0.9},
        {"chunk_id": "c1", "score": 0.7},
        {"chunk_id": "c2", "score": 0.8},
    ]
    deduped = deduplicate_results(results, top_k=5)
    assert len(deduped) == 2
    assert deduped[0]["chunk_id"] == "c1"
    assert deduped[0]["score"] == 0.9


def test_deduplicate_respects_top_k():
    from flydesk.knowledge.scoring import deduplicate_results
    results = [{"chunk_id": f"c{i}", "score": 1.0 - i * 0.1} for i in range(10)]
    deduped = deduplicate_results(results, top_k=3)
    assert len(deduped) == 3


def test_simple_stem_ing():
    from flydesk.knowledge.scoring import simple_stem
    assert simple_stem("running") == "runn"


def test_simple_stem_ed():
    from flydesk.knowledge.scoring import simple_stem
    assert simple_stem("played") == "play"


def test_simple_stem_ly():
    from flydesk.knowledge.scoring import simple_stem
    assert simple_stem("quickly") == "quick"


def test_simple_stem_tion():
    from flydesk.knowledge.scoring import simple_stem
    result = simple_stem("education")
    assert result == "educa"


def test_simple_stem_ies():
    from flydesk.knowledge.scoring import simple_stem
    result = simple_stem("flies")
    assert result == "fli"


def test_simple_stem_short_word():
    from flydesk.knowledge.scoring import simple_stem
    assert simple_stem("run") == "run"


def test_stop_words_set():
    from flydesk.knowledge.scoring import STOP_WORDS
    assert "the" in STOP_WORDS
    assert "and" in STOP_WORDS
    assert "is" in STOP_WORDS
    assert len(STOP_WORDS) >= 100
