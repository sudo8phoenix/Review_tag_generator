from __future__ import annotations

import pytest

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
        "novel screenish phrase": [0.8, 0.6],
        "tie phrase": [2 ** -0.5, 2 ** -0.5],
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


def test_legacy_normalizer_keeps_old_result_shape_and_no_implicit_fuzzy_guess():
    assert normalize_aspect("screen").normalized_aspect == "Display"
    assert normalize_aspect("hinge").is_unknown
    assert normalize_aspect("fast").is_unknown
