import pytest

import scripts.evaluate_pipeline as evaluator
from scripts.evaluate_pipeline import classification_metrics, metrics_from_labels, select_policy, span_metrics


def test_confusion_matrix_arithmetic_and_label_order():
    scores = classification_metrics([[2, 1, 0], [0, 1, 1], [1, 0, 3]])
    assert scores["n"] == 9
    assert scores["accuracy"] == 6 / 9
    assert scores["per_class"]["negative"]["precision"] == 2 / 3
    assert scores["per_class"]["negative"]["recall"] == 2 / 3
    assert scores["per_class"]["neutral"]["recall"] == 1 / 2
    assert scores["per_class"]["positive"]["recall"] == 3 / 4
    assert abs(scores["macro_f1"] - ((2 / 3 + 1 / 2 + 3 / 4) / 3)) < 1e-12


def test_labels_and_exact_spans():
    scores = metrics_from_labels(["negative", "neutral", "positive"], ["neutral", "neutral", "positive"])
    assert scores["confusion_matrix"] == [[0, 1, 0], [0, 1, 0], [0, 0, 1]]
    spans = span_metrics(2, 1, 2)
    assert spans["precision"] == 2 / 3
    assert spans["recall"] == 1 / 2
    assert abs(spans["f1"] - 4 / 7) < 1e-12


def test_selection_requires_recall_and_prefers_full_review_on_tie():
    full = classification_metrics([[5, 0, 0], [0, 5, 0], [0, 0, 5]])
    local = classification_metrics([[5, 0, 0], [0, 5, 0], [0, 0, 5]])
    assert select_policy({"full_review": full, "local_clause": local})["policy"] == "full_review"
    bad = classification_metrics([[5, 0, 0], [3, 2, 0], [0, 0, 5]])
    assert select_policy({"full_review": bad, "local_clause": local})["policy"] == "local_clause"
    assert select_policy({"full_review": bad, "local_clause": bad})["policy"] is None


@pytest.mark.parametrize("phase", ["validation", "test"])
def test_frozen_held_out_report_refuses_before_mutating_evidence(tmp_path, monkeypatch, phase):
    current = tmp_path / "current"
    current.mkdir()
    (current / "test.json").write_text('{"frozen": true}\n')
    before = {path.name: path.read_bytes() for path in current.iterdir()}
    monkeypatch.setattr(evaluator, "CURRENT", current)

    def evidence_must_not_be_read_or_written():
        raise AssertionError("frozen invocation reached evaluation evidence")

    monkeypatch.setattr(evaluator, "hash_inventory", evidence_must_not_be_read_or_written)
    with pytest.raises(RuntimeError, match="Test report exists|[Hh]eld-out test was already evaluated"):
        evaluator.main([phase])
    assert {path.name: path.read_bytes() for path in current.iterdir()} == before
