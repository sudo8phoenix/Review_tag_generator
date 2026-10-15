import pytest

from review_tag_generator.quality_queue import review_quality_queue


def analysis(review_id, text, tags):
    return {
        "review": {"review_id": review_id, "review_text": text},
        "tags": tags,
        "backend": "local-test",
        "context_policy": "full_review",
    }


def tag(aspect="Display", aspect_id="display", sentiment="positive", confidence=0.9, **extra):
    return {
        "raw_aspect": "screen",
        "normalized_aspect": aspect,
        "normalized_aspect_id": aspect_id,
        "sentiment": sentiment,
        "confidence": confidence,
        "probabilities": {"negative": 0.02, "neutral": 0.03, "positive": 0.95},
        "start_char": 7,
        "end_char": 13,
        **extra,
    }


def test_queues_unknown_low_confidence_no_aspects_and_mixed_duplicates():
    result = review_quality_queue(
        [
            analysis("unknown", "Unmapped hinge.", [tag(None, None, confidence=0.5)]),
            analysis("empty", "No aspect found.", []),
            analysis(
                "mixed",
                "Screen is bright but screen is dim.",
                [tag(sentiment="positive"), tag(sentiment="negative", confidence=0.8)],
            ),
        ],
        confidence_threshold=0.5,
    )

    by_id = {item["review_id"]: item for item in result["items"]}
    assert set(by_id) == {"unknown", "empty", "mixed"}
    assert [reason["code"] for reason in by_id["unknown"]["reasons"]] == ["unknown_aspect"]
    assert [reason["code"] for reason in by_id["empty"]["reasons"]] == ["no_aspects"]
    assert [reason["code"] for reason in by_id["mixed"]["reasons"]] == ["contradictory_sentiment"]
    assert result["summary"]["queued_reviews"] == 3
    assert result["summary"]["reason_counts"]["unknown_aspect"] == 1


def test_confidence_boundary_includes_only_values_strictly_below_threshold():
    rows = [
        analysis("at", "At boundary", [tag(confidence=0.6)]),
        analysis("below", "Below", [tag(confidence=0.5999)]),
    ]
    result = review_quality_queue(rows, confidence_threshold=0.6)
    assert [item["review_id"] for item in result["items"]] == ["below"]
    assert result["items"][0]["minimum_confidence"] == pytest.approx(0.5999)


def test_contradiction_uses_canonical_id_and_preserves_export_provenance():
    first = tag("Display", "display", "positive", probabilities={"positive": 0.8, "negative": 0.1, "neutral": 0.1})
    second = tag("Screen", "display", "negative", probabilities={"positive": 0.1, "negative": 0.8, "neutral": 0.1})
    source = analysis("r1", "The screen is bright.", [first, second])
    item = review_quality_queue([source])["items"][0]
    assert "contradictory_sentiment" in {reason["code"] for reason in item["reasons"]}
    assert item["review_text"] == "The screen is bright."
    assert item["aspects"][0]["start_char"] == 7
    assert item["aspects"][0]["probabilities"] == first["probabilities"]
    assert item["backend"] == "local-test"
    assert "gold labels" in review_quality_queue([source])["disclaimer"]


def test_ranking_and_output_are_deterministic():
    rows = [
        analysis("z", "No aspects", []),
        analysis("b", "Unknown and low", [tag(None, None, confidence=0.1)]),
        analysis("a", "Unknown", [tag(None, None, confidence=0.8)]),
    ]
    first = review_quality_queue(rows)
    second = review_quality_queue(reversed(rows))
    assert first == second
    assert [item["review_id"] for item in first["items"]] == ["b", "a", "z"]


@pytest.mark.parametrize("threshold", [-0.01, 1.01, float("nan"), float("inf"), True])
def test_rejects_invalid_threshold(threshold):
    with pytest.raises(ValueError):
        review_quality_queue([], confidence_threshold=threshold)
