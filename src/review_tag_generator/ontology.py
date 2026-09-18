import re

CANONICAL_ASPECTS = {
    "Display": ("screen", "display", "monitor", "panel", "screen quality"),
    "Battery": ("battery", "battery life", "battery backup", "battery duration"),
    "Performance": ("performance", "speed", "fast", "slow", "processor", "cpu"),
    "Keyboard": ("keyboard", "keys", "keypad"),
    "Trackpad": ("trackpad", "touchpad"),
    "Camera": ("camera", "webcam"),
    "Speakers": ("speaker", "speakers", "audio", "sound"),
    "Build Quality": ("build", "build quality", "construction"),
    "Price": ("price", "cost", "value", "value for money"),
    "Charging": ("charging", "charger", "charge"),
    "Weight": ("weight", "heavy", "lightweight"),
    "Heating": ("heating", "heat", "hot", "overheating"),
}

_ALIASES = {alias: canonical for canonical, aliases in CANONICAL_ASPECTS.items() for alias in aliases}


def normalize_aspect(aspect: str, threshold: float = 0.72):
    from .schemas import NormalizationResult
    raw = aspect.strip()
    key = re.sub(r"[^a-z0-9 ]+", " ", raw.casefold())
    key = re.sub(r"\s+", " ", key).strip()
    if key in _ALIASES:
        return NormalizationResult(raw, _ALIASES[key], 1.0, False)
    # Conservative token overlap gives a useful local fallback and avoids guessing unknowns.
    words = set(key.split())
    best, score = None, 0.0
    for canonical, aliases in CANONICAL_ASPECTS.items():
        for alias in aliases:
            alias_words = set(alias.split())
            overlap = len(words & alias_words) / max(len(words | alias_words), 1)
            if overlap > score:
                best, score = canonical, overlap
    if score >= threshold:
        return NormalizationResult(raw, best, round(score, 4), False)
    return NormalizationResult(raw, None, round(score, 4), True)
