from review_tag_generator.comparison import compare_products


def detail(name, aspects, *, stale=False, snapshot="snap", revision=4):
    return {
        "product": {"id": name.lower(), "name": name},
        "insights": {"review_count": 12, "aspects": aspects},
        "snapshot_id": snapshot,
        "pipeline_version": "pipe-v1",
        "aggregate_version": "agg-v1",
        "data_revision": revision,
        "stale": stale,
    }


def aspect(aspect_id, count, positive, neutral, negative, label=None):
    return {
        "aspect_id": aspect_id,
        "aspect": label or aspect_id.title(),
        "review_count": count,
        "counts": {"positive": positive, "neutral": neutral, "negative": negative},
        "ratios": {
            "positive": positive / count,
            "neutral": neutral / count,
            "negative": negative / count,
        },
        "classification": "mixed",
    }


def test_compares_canonical_union_and_supported_favorable_share():
    left = detail("Left", [aspect("battery", 5, 3, 1, 1, "Battery"), aspect("display", 2, 1, 0, 1)])
    right = detail("Right", [aspect("battery", 4, 1, 1, 2, "Battery"), aspect("keyboard", 3, 2, 0, 1)])

    result = compare_products(left, right)

    assert [row["aspect_id"] for row in result["rows"]] == ["battery", "display", "keyboard"]
    battery, display, keyboard = result["rows"]
    assert round(battery["favorable_share_difference"], 2) == 0.65
    assert battery["signal"] == "left"
    assert battery["evidence_gap"] == {"left": False, "right": False, "pipeline_version_mismatch": False}
    assert display["left"]["review_count"] == 2 and display["right"] is None
    assert display["favorable_share_difference"] is None
    assert display["signal"] == "insufficient_evidence"
    assert display["evidence_gap"] == {"left": True, "right": True, "pipeline_version_mismatch": False}
    assert keyboard["left"] is None and keyboard["evidence_gap"]["left"]


def test_three_reviews_is_supported_and_equal_balance_is_a_tie():
    left = detail("Left", [aspect("sound", 3, 2, 0, 1)])
    right = detail("Right", [aspect("sound", 3, 2, 0, 1)])

    row = compare_products(left, right)["rows"][0]

    assert row["favorable_share_difference"] == 0
    assert row["signal"] == "tie"
    assert row["evidence_gap"] == {"left": False, "right": False, "pipeline_version_mismatch": False}


def test_includes_snapshot_provenance_and_sampling_interpretation():
    result = compare_products(detail("Left", [], stale=True), detail("Right", [], snapshot=None, revision=9))

    assert result["left"]["stale"] is True
    assert result["left"]["snapshot_id"] == "snap"
    assert result["right"]["snapshot_id"] is None
    assert result["right"]["data_revision"] == 9
    assert "sampling" in result["interpretation"]
    assert result["rows"] == []


def test_pipeline_version_mismatch_suppresses_directional_comparison():
    left = detail("Left", [aspect("battery", 5, 4, 0, 1)])
    right = detail("Right", [aspect("battery", 5, 1, 0, 4)])
    right["pipeline_version"] = "pipe-v2"

    result = compare_products(left, right)
    row = result["rows"][0]

    assert result["pipeline_version_mismatch"] is True
    assert row["favorable_share_difference"] is None
    assert row["signal"] == "insufficient_evidence"
    assert row["evidence_gap"]["pipeline_version_mismatch"] is True
