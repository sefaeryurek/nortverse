"""Pattern D (Cosine Similarity) birim testleri."""

import math
from unittest.mock import AsyncMock, patch

import pytest

from app.analysis.pattern_d import (
    _to_vector,
    cosine_similarity,
    find_matched_ids,
)
from app.analysis.scores import ALL_SCORES, score_key


# ─── _to_vector ──────────────────────────────────────────────────────────────


class TestToVector:
    def test_empty_dict_returns_zeros(self):
        vec = _to_vector({})
        assert len(vec) == len(ALL_SCORES)
        assert all(v == 0.0 for v in vec)

    def test_single_key(self):
        h, a = ALL_SCORES[0]
        key = score_key(h, a)
        vec = _to_vector({key: 3.5})
        assert vec[0] == 3.5
        assert all(v == 0.0 for v in vec[1:])

    def test_full_ratios(self):
        ratios = {score_key(h, a): float(i) for i, (h, a) in enumerate(ALL_SCORES)}
        vec = _to_vector(ratios)
        assert len(vec) == 35
        for i, v in enumerate(vec):
            assert v == float(i)

    def test_extra_keys_ignored(self):
        ratios = {score_key(h, a): 1.0 for h, a in ALL_SCORES}
        ratios["unknown_key"] = 99.0
        vec = _to_vector(ratios)
        assert len(vec) == 35


# ─── cosine_similarity ───────────────────────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_a(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_zero_vector_b(self):
        assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0

    def test_both_zero(self):
        assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_known_value(self):
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        dot = 1*4 + 2*5 + 3*6  # 32
        norm_a = math.sqrt(1 + 4 + 9)  # sqrt(14)
        norm_b = math.sqrt(16 + 25 + 36)  # sqrt(77)
        expected = dot / (norm_a * norm_b)
        assert cosine_similarity(a, b) == pytest.approx(expected)

    def test_similar_vectors_high_sim(self):
        a = [3.5, 2.0, 1.5, 4.0, 0.5]
        b = [3.6, 2.1, 1.4, 4.1, 0.6]
        sim = cosine_similarity(a, b)
        assert sim > 0.99

    def test_different_vectors_low_sim(self):
        a = [10.0, 0.0, 0.0, 0.0, 0.0]
        b = [0.0, 0.0, 0.0, 0.0, 10.0]
        sim = cosine_similarity(a, b)
        assert sim == pytest.approx(0.0)

    def test_35_dimensional_vectors(self):
        a = [float(i) for i in range(35)]
        b = [float(i + 0.1) for i in range(35)]
        sim = cosine_similarity(a, b)
        assert sim > 0.99

    def test_symmetry(self):
        a = [1.0, 3.0, 5.0, 7.0]
        b = [2.0, 4.0, 6.0, 8.0]
        assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a))

    def test_scale_invariance(self):
        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0, 3.0]
        b_scaled = [10.0, 20.0, 30.0]
        assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(a, b_scaled))


# ─── score_key helper ────────────────────────────────────────────────────────

class TestScoreKey:
    def test_format(self):
        assert score_key(1, 0) == "1-0"
        assert score_key(0, 0) == "0-0"
        assert score_key(6, 1) == "6-1"

    def test_all_scores_length(self):
        assert len(ALL_SCORES) == 35


# ─── find_matched_ids ───────────────────────────────────────────────────────


def _make_ratios(base: float = 3.0) -> dict[str, float]:
    return {score_key(h, a): base + i * 0.1 for i, (h, a) in enumerate(ALL_SCORES)}


def _make_candidate(match_id: str, ratios: dict[str, float]):
    return (match_id, ratios, 2, 1, 1, 0, 1, 1)


class TestFindMatchedIds:
    @pytest.mark.asyncio
    async def test_empty_ratios_returns_empty(self):
        result = await find_matched_ids({})
        assert result == []

    @pytest.mark.asyncio
    async def test_zero_vector_returns_empty(self):
        ratios = {score_key(h, a): 0.0 for h, a in ALL_SCORES}
        result = await find_matched_ids(ratios)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_similar_matches(self):
        target = _make_ratios(3.0)
        similar = _make_ratios(3.01)
        different = {score_key(h, a): 0.0 for h, a in ALL_SCORES}
        different[score_key(0, 0)] = 10.0

        candidates = [
            _make_candidate("100", similar),
            _make_candidate("200", different),
        ]

        with patch("app.analysis.pattern_d._load_candidates", new_callable=AsyncMock, return_value=candidates):
            result = await find_matched_ids(target, top_n=5, min_similarity=0.9)

        ids = [mid for mid, _ in result]
        assert "100" in ids
        assert "200" not in ids

    @pytest.mark.asyncio
    async def test_exclude_match_id(self):
        target = _make_ratios(3.0)
        same = _make_ratios(3.0)

        all_candidates = [_make_candidate("100", same), _make_candidate("200", same)]

        async def mock_load(exclude_match_id=None, as_of=None):
            if exclude_match_id:
                return [c for c in all_candidates if c[0] != exclude_match_id]
            return all_candidates

        with patch("app.analysis.pattern_d._load_candidates", side_effect=mock_load):
            result = await find_matched_ids(target, exclude_match_id="100")

        ids = [mid for mid, _ in result]
        assert "100" not in ids
        assert "200" in ids

    @pytest.mark.asyncio
    async def test_top_n_limit(self):
        target = _make_ratios(3.0)
        candidates = [_make_candidate(str(i), _make_ratios(3.0 + i * 0.001)) for i in range(10)]

        with patch("app.analysis.pattern_d._load_candidates", new_callable=AsyncMock, return_value=candidates):
            result = await find_matched_ids(target, top_n=3, min_similarity=0.5)

        assert len(result) <= 3

    @pytest.mark.asyncio
    async def test_similarity_score_included(self):
        target = _make_ratios(3.0)
        candidates = [_make_candidate("100", _make_ratios(3.01))]

        with patch("app.analysis.pattern_d._load_candidates", new_callable=AsyncMock, return_value=candidates):
            result = await find_matched_ids(target, min_similarity=0.5)

        assert len(result) == 1
        mid, sim = result[0]
        assert mid == "100"
        assert 0.99 < sim <= 1.0
