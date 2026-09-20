import re
from dataclasses import dataclass
from .ontology import CANONICAL_ASPECTS
from .schemas import AspectPrediction


@dataclass(frozen=True)
class WindowSpanCandidate:
    start_char: int
    end_char: int
    confidence: float
    boundary_margin: int
    window_index: int


def merge_window_candidates(text: str, candidates: list[WindowSpanCandidate]) -> list[AspectPrediction]:
    """Prefer spans seen away from a window edge, then higher-confidence spans."""
    selected: list[WindowSpanCandidate] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (-item.boundary_margin, -item.confidence, item.window_index, item.start_char, item.end_char),
    ):
        if not (0 <= candidate.start_char < candidate.end_char <= len(text)):
            raise ValueError("Model returned an aspect outside the source review")
        if not text[candidate.start_char:candidate.end_char].strip():
            continue
        if any(candidate.start_char < kept.end_char and candidate.end_char > kept.start_char for kept in selected):
            continue
        selected.append(candidate)
    return [
        AspectPrediction(text[item.start_char:item.end_char], item.start_char, item.end_char, round(item.confidence, 4))
        for item in sorted(selected, key=lambda item: (item.start_char, item.end_char))
    ]


def extract_aspects(text: str, aspect_terms: dict[str, tuple[str, ...]] = CANONICAL_ASPECTS):
    matches = []
    aliases = sorted((alias, canonical) for canonical, values in aspect_terms.items() for alias in values)
    for alias, _ in aliases:
        for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I):
            matches.append(AspectPrediction(text[match.start():match.end()], match.start(), match.end(), 0.80))
    # Keep the longest alias where dictionary entries overlap, e.g. "battery life".
    chosen = []
    for candidate in sorted(matches, key=lambda p: (-(p.end_char - p.start_char), p.start_char, p.end_char)):
        if not any(candidate.start_char < kept.end_char and candidate.end_char > kept.start_char for kept in chosen):
            chosen.append(candidate)
    return sorted(chosen, key=lambda p: (p.start_char, p.end_char))
