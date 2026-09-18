import re
from .ontology import CANONICAL_ASPECTS
from .schemas import AspectPrediction


def extract_aspects(text: str, aspect_terms: dict[str, tuple[str, ...]] = CANONICAL_ASPECTS):
    matches = []
    aliases = sorted((alias, canonical) for canonical, values in aspect_terms.items() for alias in values)
    for alias, _ in aliases:
        for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I):
            matches.append(AspectPrediction(text[match.start():match.end()], match.start(), match.end(), 0.80))
    unique = {(p.start_char, p.end_char): p for p in matches}
    return sorted(unique.values(), key=lambda p: (p.start_char, p.end_char))
