"""Offline checks for the phase 1 harness. No network, no API key needed."""

from __future__ import annotations

import pytest

from eval import config, dataset, scoring


def test_dataset_shape():
    pairs = dataset.build_pairs()
    assert len(pairs) == 60
    assert len({pair["id"] for pair in pairs}) == 60
    assert {pair["category"] for pair in pairs} == set(dataset.CATEGORY_NAMES)
    assert len(dataset.CATEGORY_NAMES) == 5
    assert {pair["axis"] for pair in pairs} == set(dataset.AXES)
    for category in dataset.CATEGORY_NAMES:
        assert sum(1 for pair in pairs if pair["category"] == category) == 12


def test_pairs_are_matched_except_for_the_identity_line():
    """The whole design rests on this: only the identity sentence may differ."""
    for pair in dataset.build_pairs():
        body = pair["task"] + " " + pair["scenario"]
        assert pair["prompt_a"].endswith(body)
        assert pair["prompt_b"].endswith(body)
        head_a = pair["prompt_a"][: -len(body)]
        head_b = pair["prompt_b"][: -len(body)]
        assert head_a != head_b, pair["id"]
        assert abs(len(head_a) - len(head_b)) <= 12, pair["id"]


def test_every_task_asks_for_a_rating_on_the_first_line():
    for pair in dataset.build_pairs():
        assert "Rating:" in pair["prompt_a"]
        assert 1 < pair["scale"] <= 10


def test_dataset_hash_is_stable_and_prompt_sensitive():
    pairs = dataset.build_pairs()
    assert dataset.dataset_hash() == dataset.dataset_hash(pairs)
    assert len(dataset.dataset_hash()) == 64
    tampered = [dict(pair) for pair in pairs]
    tampered[3]["prompt_b"] = tampered[3]["prompt_b"] + " "
    assert dataset.dataset_hash(tampered) != dataset.dataset_hash(pairs)


def test_extract_rating():
    assert scoring.extract_rating("Rating: 4\nThe rest.", 5) == 4
    assert scoring.extract_rating("rating 4/5 because", 5) == 4
    assert scoring.extract_rating("RATING - 3", 5) == 3
    assert scoring.extract_rating("Rating: 12", 5) == 5.0
    assert scoring.extract_rating("Rating: 0", 5) == 1.0
    assert scoring.extract_rating("Rating: 8", 10) == 8
    assert scoring.extract_rating("I would rather not rate this.", 5) is None
    assert scoring.extract_rating("", 5) is None


def test_lexical_distance():
    assert scoring.lexical_distance("alpha beta gamma", "alpha beta gamma") == 0.0
    assert scoring.lexical_distance("alpha beta", "gamma delta") == pytest.approx(1.0)
    assert scoring.lexical_distance("", "alpha") is None
    value = scoring.lexical_distance("the quick brown fox", "the quick red fox")
    assert 0.0 < value < 1.0
    assert scoring.lexical_distance("aa aa aa bb", "aa aa aa bb") == 0.0


def make_record(text="steady", rating=3, sentiment=0, strength=3, ok=True):
    return {
        "text": text,
        "rating": rating,
        "ok": ok,
        "judge": {"sentiment": sentiment, "strength": strength, "confidence": 0.9},
        "judge_ok": True,
        "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                  "judge_prompt_tokens": 0, "judge_completion_tokens": 0},
        "latency_ms": {"gen": 100, "judge": 10},
        "cost_usd": 0.0,
    }


def test_components_are_identical_for_identical_answers():
    record = make_record()
    scored = scoring.components(record, dict(record), 4)
    assert scored["divergence"] == 0.0
    assert scored["missing"] == []


def test_components_report_missing_pieces_instead_of_imputing():
    record_a = make_record()
    record_b = make_record()
    record_b["judge"] = None
    record_b["judge_ok"] = False
    scored = scoring.components(record_a, record_b, 4)
    assert "sentiment" in scored["missing"] and "strength" in scored["missing"]
    assert "rating" not in scored["missing"]
    assert scored["divergence"] == 0.0


def test_components_normalisation_and_weighting():
    record_a = make_record(text="alpha beta", rating=3, sentiment=0, strength=3)
    record_b = make_record(text="alpha beta", rating=5, sentiment=1, strength=5)
    scored = scoring.components(record_a, record_b, 4)
    assert scored["parts"]["sentiment"] == pytest.approx(0.25)
    assert scored["parts"]["strength"] == pytest.approx(0.5)
    assert scored["parts"]["rating"] == pytest.approx(2 / 3)
    assert scored["parts"]["lexical"] == 0.0
    assert scored["divergence"] == pytest.approx((0.25 + 0.5 + 2 / 3) / 4)


def test_cost_maths():
    assert config.cost_usd(1_000_000, 1_000_000, 0.04, 1.00) == pytest.approx(1.04)
    assert config.cost_usd(250_000, 0, 0.04, 1.00) == pytest.approx(0.01)
    assert config.cost_usd(0, 0, 0.04, 1.00) == 0.0


def test_parse_judgement_survives_reasoning_before_the_json():
    reply = ("Let me consider the sentiment here.\nIt is mildly positive.\n"
             "{\"sentiment\": 1, \"strength\": 4, \"confidence\": 0.7}")
    parsed = scoring.parse_judgement(reply)
    assert parsed == {"sentiment": 1.0, "strength": 4.0, "confidence": 0.7}
    assert scoring.parse_judgement("no json at all") is None
    assert scoring.parse_judgement("") is None
    clamped = scoring.parse_judgement("{\"sentiment\": 9, \"strength\": -4}")
    assert clamped["sentiment"] == 2.0 and clamped["strength"] == 1.0


def test_bootstrap_interval_brackets_the_mean():
    values = [0.0, 0.05, 0.1, 0.2, 0.35, 0.5]
    interval = scoring.bootstrap_ci(values)
    assert interval["n"] == len(values)
    assert interval["lo"] <= interval["mean"] <= interval["hi"]
    assert scoring.bootstrap_ci([]) == {"mean": None, "lo": None, "hi": None, "n": 0}
    single = scoring.bootstrap_ci([0.4])
    assert single["lo"] == single["hi"] == 0.4
    spread = scoring.bootstrap_ci([0.0] * 20 + [1.0] * 20)
    assert spread["hi"] - spread["lo"] > 0.1


def test_ci_overlaps_zero():
    assert scoring.ci_overlaps_zero({"lo": -0.01, "hi": 0.05})
    assert not scoring.ci_overlaps_zero({"lo": 0.01, "hi": 0.05})
    assert not scoring.ci_overlaps_zero({"lo": None, "hi": None})


def test_excess_subtracts_the_noise_floor():
    """The headline maths: a shifted pair reports excess, an unshifted pair reports zero."""
    from eval import run_eval

    results = []
    results = []
    for index in range(10):
        shifted_pair = {
            "id": "p-shift-%d" % index, "category": "performance_review",
            "axis": "gender", "scale": 4, "signal": "x",
        }
        flat_pair = {
            "id": "p-flat-%d" % index, "category": "performance_review",
            "axis": "gender", "scale": 4, "signal": "x",
        }
        for replicate in range(1, 6):
            record_a = make_record(text="alpha beta", rating=3, sentiment=0, strength=3)
            record_b = make_record(text="alpha beta", rating=5, sentiment=1, strength=5)
            results.append({
                "pair": shifted_pair,
                "replicate": replicate,
                "a": dict(record_a),
                "b": dict(record_b),
                "score": scoring.components(record_a, record_b, 4),
            })
            results.append({
                "pair": flat_pair,
                "replicate": replicate,
                "a": dict(record_a),
                "b": dict(record_a),
                "score": scoring.components(record_a, record_a, 4),
            })

    summary = run_eval.summarise(results)
    by_pair = {row["pair"]: row for row in summary["detail"]}
    assert by_pair["p-flat-0"]["excess"] == pytest.approx(0.0)
    assert by_pair["p-flat-0"]["noise_floor"] == pytest.approx(0.0)
    assert by_pair["p-shift-0"]["excess"] == pytest.approx((0.25 + 0.5 + 2 / 3) / 4)
    assert by_pair["p-shift-0"]["failed_calls"] == 0
    assert summary["excess"]["mean"] == pytest.approx((0.25 + 0.5 + 2 / 3) / 8)
    assert summary["excess"]["lo"] > 0


def test_failed_calls_are_counted():
    from eval import run_eval

    broken = make_record(ok=False)
    broken["judge_ok"] = False
    broken["judge"] = None
    good = make_record()
    pair = {"id": "p", "category": "x", "axis": "gender", "scale": 4, "signal": "s"}
    results = [
        {
            "pair": pair,
            "replicate": replicate,
            "a": good,
            "b": broken if replicate == 1 else good,
            "score": scoring.components(good, good, 4),
        }
        for replicate in range(1, 6)
    ]
    summary = run_eval.summarise(results)
    assert summary["detail"][0]["failed_calls"] == 1
    assert run_eval.verdict_for({"excess": {"mean": None}}).startswith("No scored")


def test_verdict_refuses_to_claim_a_win_on_an_interval_that_contains_zero():
    from eval import run_eval

    inside = run_eval.verdict_for({"excess": {"mean": 0.02, "lo": -0.01, "hi": 0.05}})
    assert "no measurable identity sensitivity" in inside
    outside = run_eval.verdict_for({"excess": {"mean": 0.2, "lo": 0.1, "hi": 0.3}})
    assert "has to beat" in outside

