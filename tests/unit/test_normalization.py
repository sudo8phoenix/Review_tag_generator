from __future__ import annotations

import pytest
import json

import scripts.evaluate_normalization as evaluator
from review_tag_generator.normalization import (
    AspectNormalizer,
    OntologyCollisionError,
    build_ontology,
    get_ontology,
)
from review_tag_generator.ontology import CANONICAL_ASPECTS, normalize_aspect


def test_ontology_has_all_requested_stable_ids_and_display_labels():
    ontology = get_ontology()
    assert ontology.version == "electronics-aspects-v1"
    assert len(ontology.aspects) == 21
    assert ontology.by_id["battery"].display_label == "Battery"
    assert ontology.by_id["customer_service"].display_label == "Customer Service"
    assert CANONICAL_ASPECTS["Display"]


def test_aliases_normalize_case_whitespace_multiword_and_plural_forms():
    normalizer = AspectNormalizer()
    cases = {
        "  SCREEN  ": ("display", "Display"),
        "Battery    LIFE": ("battery", "Battery"),
        "MONITORS": ("display", "Display"),
        "ssds": ("storage", "Storage"),
        "usb ports": ("ports", "Ports"),
        "customer support": ("customer_service", "Customer Service"),
    }
    for term, expected in cases.items():
        result = normalizer.normalize(term)
        assert (result.normalized_aspect_id, result.normalized_aspect) == expected
        assert result.method == "alias"
        assert result.similarity == 1.0
        assert not result.is_unknown


def test_alias_ownership_collision_is_rejected_across_canonical_items():
    with pytest.raises(OntologyCollisionError, match="both"):
        build_ontology({
            "version": "test-v1",
            "aspects": [
                {"id": "one", "label": "One", "aliases": ["shared term"]},
                {"id": "two", "label": "Two", "aliases": ["Shared Term"]},
            ],
        })


def test_price_value_and_performance_processor_remain_distinct():
    normalizer = AspectNormalizer()
    assert normalizer.normalize("price").normalized_aspect_id == "price"
    assert normalizer.normalize("value for money").normalized_aspect_id == "value"
    assert normalizer.normalize("processor").normalized_aspect_id == "processor"
    assert normalizer.normalize("overall performance").normalized_aspect_id == "performance"


@pytest.mark.parametrize("term", ["fast", "slow", "charge", "hinge", "unrelated topic"])
def test_ambiguous_adjectives_polysemous_charge_and_unknowns_stay_unknown(term):
    result = AspectNormalizer().normalize(term)
    assert result.is_unknown
    assert result.normalized_aspect_id is None
    assert result.normalized_aspect is None
    assert result.method == "unknown"


def test_semantic_mode_requires_explicit_threshold_and_model_revision():
    with pytest.raises(ValueError, match="threshold"):
        AspectNormalizer(encoder=lambda texts: [[1.0] for _ in texts])
    with pytest.raises(ValueError, match="revision"):
        AspectNormalizer(semantic_model_path="/missing/local/model", threshold=0.7)
    with pytest.raises(ValueError, match="pinned"):
        AspectNormalizer(
            semantic_model_path="/missing/local/model", threshold=0.7, semantic_revision="main"
        )


def test_semantic_threshold_boundary_and_deterministic_tie_policy():
    ontology = build_ontology({"version": "test-v1", "aspects": [
        {"id": "display", "label": "Display", "aliases": ["screen"]},
        {"id": "battery", "label": "Battery", "aliases": ["battery life"]},
    ]})
    vectors = {
        "display": [1.0, 0.0], "screen": [1.0, 0.0],
        "battery": [0.0, 1.0], "battery life": [0.0, 1.0],
        "aspect mention novel screenish phrase": [0.8, 0.6],
        "aspect mention tie phrase": [2 ** -0.5, 2 ** -0.5],
    }

    def encoder(texts):
        return [vectors.get(text, [0.0, 1.0]) for text in texts]

    # Threshold inclusive: cosine is exactly 0.8 at the decision boundary.
    accepted = AspectNormalizer(ontology=ontology, encoder=encoder, threshold=0.8).normalize("novel screenish phrase")
    assert accepted.normalized_aspect_id == "display"
    assert accepted.method == "semantic"
    rejected = AspectNormalizer(ontology=ontology, encoder=encoder, threshold=0.81).normalize("novel screenish phrase")
    assert rejected.is_unknown

    tied = AspectNormalizer(ontology=ontology, encoder=encoder, threshold=0.5).normalize("tie phrase")
    assert tied.is_unknown


def test_semantic_embeddings_are_cached_for_aliases_and_repeated_queries():
    calls = []

    def encoder(texts):
        calls.append(tuple(texts))
        return [[1.0, 0.0] for _ in texts]

    normalizer = AspectNormalizer(encoder=encoder, threshold=0.95)
    initial_calls = len(calls)
    normalizer.normalize("new query")
    after_first = len(calls)
    normalizer.normalize("new query")
    assert initial_calls == 1
    assert after_first == 2
    assert len(calls) == after_first


def test_context_is_used_for_ambiguous_semantic_mentions():
    ontology = build_ontology({"version": "test-v1", "aspects": [
        {"id": "battery", "label": "Battery", "aliases": ["battery life"]},
        {"id": "charging", "label": "Charging", "aliases": ["charging"]},
    ]})
    query_texts = []
    vectors = {
        "battery": [1.0, 0.0], "battery life": [1.0, 0.0],
        "charging": [0.0, 1.0],
        "aspect mention charge": [0.0, 1.0],
        "aspect mention charge review context charging cable works": [0.0, 1.0],
    }

    def encoder(texts):
        query_texts.extend(texts)
        return [vectors.get(text, [1.0, 0.0]) for text in texts]

    normalizer = AspectNormalizer(ontology=ontology, encoder=encoder, threshold=0.9)
    assert normalizer.normalize("charge").is_unknown
    result = normalizer.normalize("charge", context="charging cable works")
    assert result.normalized_aspect_id == "charging"
    assert result.method == "semantic"
    assert "aspect mention charge review context charging cable works" in query_texts


def test_legacy_normalizer_keeps_old_result_shape_and_no_implicit_fuzzy_guess():
    assert normalize_aspect("screen").normalized_aspect == "Display"
    assert normalize_aspect("hinge").is_unknown
    assert normalize_aspect("fast").is_unknown


def test_human_rows_report_pending_independent_review_with_input_fingerprint(tmp_path):
    source = tmp_path / "rows.jsonl"
    source.write_text("".join(json.dumps({"text": "hinge", "label": None}) + "\n" for _ in range(200)))
    output = tmp_path / "report.json"
    assert evaluator.main(["--examples-jsonl", str(source), "--output", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["quality_gate"] == "pending independent human review"
    assert report["human_review_input"]["sha256"]
    assert report["human_review_input"]["reviewer_provenance"].startswith("unverified")
