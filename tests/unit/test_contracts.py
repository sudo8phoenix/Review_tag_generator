"""Contract validation against synthetic, checked-in API payloads."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.contracts import models as dto
from review_tag_generator.schemas import Sentiment, TagResult, tag_result_from_mention


EXAMPLES = json.loads((Path(__file__).parents[1] / "fixtures/api/examples.json").read_text())


@pytest.mark.parametrize("name,model", [
    ("preview_request", dto.PreviewRequest),
    ("preview_queued", dto.PreviewQueued),
    ("preview_success", dto.PreviewResult),
    ("preview_no_aspect", dto.PreviewResult),
    ("preview_failed", dto.PreviewResult),
    ("submit_request", dto.SubmitReviewsRequest),
    ("job_accepted", dto.JobAccepted),
    ("job_partial_failure", dto.Job),
    ("empty_product", dto.ProductInsights),
    ("stale_product", dto.ProductInsights),
    ("unknown_mention", dto.Mention),
    ("product_tags", dto.ProductTags),
    ("review_detail", dto.ReviewDetail),
    ("products_page", dto.ProductPage),
    ("reviews_page", dto.ReviewPage),
    ("model_metrics", dto.ModelMetrics),
    ("health", dto.Health),
    ("ready", dto.Ready),
])
def test_fixture_round_trip(name, model):
    instance = model.model_validate(EXAMPLES[name])
    assert model.model_validate_json(instance.model_dump_json()) == instance
    assert model.model_json_schema()["type"] == "object"


def test_all_error_envelopes_round_trip():
    assert set(EXAMPLES["errors"]) == {code.value for code in dto.ErrorCode}
    for code, payload in EXAMPLES["errors"].items():
        envelope = dto.ErrorEnvelope.model_validate(payload)
        assert envelope.error.code.value == code
        assert dto.ErrorEnvelope.model_validate_json(envelope.model_dump_json()) == envelope


def test_supported_aspect_examples_and_insights_partition():
    aspects = [dto.AspectInsight.model_validate(item) for item in EXAMPLES["supported_aspects"]]
    assert {a.classification.value for a in aspects} == {"strength", "weakness", "mixed"}
    payload = deepcopy(EXAMPLES["stale_product"])
    payload["aspects"] = EXAMPLES["supported_aspects"]
    payload["strengths"] = ["display"]
    payload["weaknesses"] = ["keyboard"]
    payload["mixed"] = ["battery"]
    insights = dto.ProductInsights.model_validate(payload)
    assert len(insights.aspects) == 3
    assert dto.ProductInsights.model_validate_json(insights.model_dump_json()) == insights


def test_unicode_code_point_offsets_and_original_text():
    payload = deepcopy(EXAMPLES["preview_success"]["analysis"])
    payload["review_text"] = "😊 display"
    payload["mentions"] = [payload["mentions"][0]]
    payload["mentions"][0].update(raw_aspect="display", start_char=2, end_char=9,
                                   context_start_char=0, context_end_char=9)
    result = dto.Analysis.model_validate(payload)
    assert result.review_text[2:9] == "display"
    with pytest.raises(ValueError, match="differs"):
        dto.validate_original_text(result, "display")


def test_review_detail_rejects_analysis_for_different_source_text():
    payload = deepcopy(EXAMPLES["review_detail"])
    payload["analysis_status"] = "completed"
    payload["analysis"] = EXAMPLES["preview_no_aspect"]["analysis"]
    with pytest.raises(ValidationError):
        dto.ReviewDetail.model_validate(payload)


def test_fixed_label_ids_and_query_bounds():
    assert [item.value for item in dto.SentimentLabelId] == [0, 1, 2]
    assert [item.value for item in dto.AspectLabelId] == [0, 1, 2]
    assert dto.TagsQuery().top_k == 10
    assert dto.ProductsQuery().page_size == 20
    with pytest.raises(ValidationError):
        dto.TagsQuery(top_k=51)
    with pytest.raises(ValidationError):
        dto.ReviewsQuery(sentiment="mixed")
    with pytest.raises(ValidationError):
        dto.PageQuery(page=0)


@pytest.mark.parametrize("text", ["", "  \n ", "a" * 10001])
def test_bad_review_text_rejected(text):
    with pytest.raises(ValidationError):
        dto.ReviewInput(review_text=text)


def test_review_text_not_normalized_and_extra_fields_rejected():
    original = "  Nice screen.\n"
    assert dto.ReviewInput(review_text=original).review_text == original
    with pytest.raises(ValidationError):
        dto.PreviewRequest.model_validate({**EXAMPLES["preview_request"], "surprise": 1})


@pytest.mark.parametrize("rating", [0, 6, 1.5, True, "5"])
def test_rating_must_be_strict_integer_one_to_five(rating):
    with pytest.raises(ValidationError):
        dto.ReviewInput(review_text="Good display", rating=rating)


@pytest.mark.parametrize("mutation", [
    {"start_char": 15, "end_char": 8},
    {"start_char": -1},
    {"end_char": 999},
    {"raw_aspect": "screen"},
    {"context_start_char": 9},
    {"context_end_char": 14},
    {"confidence": 0.4},
    {"sentiment": "mixed"},
    {"sentiment_confidence": 0.6},
])
def test_invalid_mention_or_analysis_rejected(mutation):
    payload = deepcopy(EXAMPLES["preview_success"]["analysis"])
    payload["mentions"][0].update(mutation)
    with pytest.raises(ValidationError):
        dto.Analysis.model_validate(payload)


@pytest.mark.parametrize("probabilities", [
    {"negative": 0.2, "neutral": 0.2, "positive": 0.2},
    {"negative": -0.01, "neutral": 0.04, "positive": 0.97},
    {"negative": 0.02, "neutral": 0.01, "positive": float("nan")},
])
def test_bad_probabilities_rejected(probabilities):
    payload = deepcopy(EXAMPLES["preview_success"]["analysis"])
    payload["mentions"][0]["probabilities"] = probabilities
    with pytest.raises(ValidationError):
        dto.Analysis.model_validate(payload)


def test_unknown_cannot_have_tag_or_canonical_id():
    payload = deepcopy(EXAMPLES["unknown_mention"])
    payload["tag"] = "Good Hinge"
    with pytest.raises(ValidationError):
        dto.Mention.model_validate(payload)


def test_job_count_and_terminal_status_rules():
    payload = deepcopy(EXAMPLES["job_partial_failure"])
    payload["status"] = "completed"
    with pytest.raises(ValidationError):
        dto.Job.model_validate(payload)
    payload["status"] = "completed_with_errors"
    payload["total_rows"] = 6
    with pytest.raises(ValidationError):
        dto.Job.model_validate(payload)


def test_insight_bad_references_and_ratios_rejected():
    payload = deepcopy(EXAMPLES["stale_product"])
    payload["strengths"] = ["display"]
    with pytest.raises(ValidationError):
        dto.ProductInsights.model_validate(payload)
    payload = deepcopy(EXAMPLES["supported_aspects"][0])
    payload["ratios"]["positive"] = 0.8
    with pytest.raises(ValidationError):
        dto.AspectInsight.model_validate(payload)
    payload = deepcopy(EXAMPLES["supported_aspects"][0])
    payload["ratios"] = {"positive": 0.5, "neutral": 0.5, "negative": 0}
    with pytest.raises(ValidationError):
        dto.AspectInsight.model_validate(payload)


def test_legacy_projection_preserves_old_constructor_callers():
    mention = dto.Mention.model_validate(EXAMPLES["preview_success"]["analysis"]["mentions"][0])
    legacy = tag_result_from_mention(mention)
    assert legacy == TagResult("Display", Sentiment.POSITIVE, "Great Display", 0.97, "display", 8, 15)
    unknown = tag_result_from_mention(dto.Mention.model_validate(EXAMPLES["unknown_mention"]))
    assert unknown.normalized_aspect is None and unknown.tag == ""


def test_timestamps_emit_utc_and_idempotency_uuid():
    payload = deepcopy(EXAMPLES["preview_queued"])
    payload["expires_at"] = "2026-09-18T18:00:00+05:30"
    queued = dto.PreviewQueued.model_validate(payload)
    assert queued.model_dump(mode="json")["expires_at"] == "2026-09-18T12:30:00Z"
    assert str(dto.validate_idempotency_key("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")) == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    with pytest.raises(ValueError):
        dto.validate_idempotency_key("not-a-uuid")
