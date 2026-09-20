import pytest

from review_tag_generator.extraction import WindowSpanCandidate, extract_aspects, merge_window_candidates


def test_longest_alias_wins_without_discarding_repetition():
    text = "Battery life is good; battery is poor."
    spans = extract_aspects(text)
    assert [item.aspect for item in spans] == ["Battery life", "battery"]


def test_window_merge_prefers_interior_and_keeps_unicode_offsets():
    text = "😀 Amazing battery life and screen"
    battery = text.index("battery")
    screen = text.index("screen")
    spans = merge_window_candidates(text, [
        WindowSpanCandidate(battery, battery + 7, 0.99, 0, 0),
        WindowSpanCandidate(battery, battery + 12, 0.91, 4, 1),
        WindowSpanCandidate(screen, screen + 6, 0.8, 3, 1),
    ])
    assert [(p.aspect, p.start_char, p.end_char) for p in spans] == [
        ("battery life", battery, battery + 12),
        ("screen", screen, screen + 6),
    ]


def test_invalid_window_offset_rejected():
    with pytest.raises(ValueError, match="outside"):
        merge_window_candidates("screen", [WindowSpanCandidate(0, 50, 0.9, 1, 0)])
