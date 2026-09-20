"""Deterministic alias-first aspect normalization with optional local MiniLM.

No model is downloaded here. Semantic mode is opt-in and accepts a local snapshot
whose recorded/reported revision must match the pinned upstream commit.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

ONTOLOGY_VERSION = "electronics-aspects-v1"
MINILM_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MINILM_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
TIE_TOLERANCE = 1e-6
_NORMALIZATION = re.compile(r"[^a-z0-9]+")


class OntologyCollisionError(ValueError):
    """Raised when an alias would have more than one canonical owner."""


@dataclass(frozen=True)
class CanonicalAspect:
    id: str
    display_label: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Ontology:
    version: str
    aspects: tuple[CanonicalAspect, ...]

    @property
    def by_id(self) -> dict[str, CanonicalAspect]:
        return {aspect.id: aspect for aspect in self.aspects}

    @property
    def by_label(self) -> dict[str, CanonicalAspect]:
        return {aspect.display_label: aspect for aspect in self.aspects}

    @property
    def alias_to_aspect(self) -> dict[str, CanonicalAspect]:
        return {
            _normalize_text(alias): aspect
            for aspect in self.aspects
            for alias in (aspect.display_label, *aspect.aliases)
        }


@dataclass(frozen=True)
class NormalizationResult:
    raw_aspect: str
    normalized_aspect_id: str | None
    normalized_aspect: str | None
    method: str
    similarity: float | None
    is_unknown: bool


def _normalize_text(text: str) -> str:
    return " ".join(_NORMALIZATION.sub(" ", text.casefold()).split())


def build_ontology(payload: dict) -> Ontology:
    """Validate and build an ontology, rejecting ambiguous alias ownership."""
    version = payload.get("version")
    raw_aspects = payload.get("aspects")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("ontology version must be a non-empty string")
    if not isinstance(raw_aspects, list) or not raw_aspects:
        raise ValueError("ontology must contain at least one aspect")

    aspects: list[CanonicalAspect] = []
    ids: set[str] = set()
    labels: set[str] = set()
    owners: dict[str, str] = {}
    for raw in raw_aspects:
        identifier = raw.get("id")
        label = raw.get("label")
        aliases = raw.get("aliases")
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", identifier):
            raise ValueError(f"invalid canonical aspect ID: {identifier!r}")
        if identifier in ids:
            raise ValueError(f"duplicate canonical aspect ID: {identifier}")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"invalid display label for {identifier}")
        label_key = _normalize_text(label)
        if label_key in labels:
            raise ValueError(f"duplicate canonical display label: {label}")
        if not isinstance(aliases, list) or any(not isinstance(x, str) or not x.strip() for x in aliases):
            raise ValueError(f"aliases for {identifier} must be non-empty strings")
        aspect = CanonicalAspect(identifier, label, tuple(aliases))
        for alias in (label, *aliases):
            key = _normalize_text(alias)
            previous = owners.get(key)
            if previous is not None and previous != identifier:
                raise OntologyCollisionError(
                    f"alias {alias!r} belongs to both {previous!r} and {identifier!r}"
                )
            owners[key] = identifier
        ids.add(identifier)
        labels.add(label_key)
        aspects.append(aspect)
    return Ontology(version, tuple(aspects))


def get_ontology() -> Ontology:
    path = Path(__file__).parent / "data" / "ontology-v1.json"
    with path.open(encoding="utf-8") as source:
        return build_ontology(json.load(source))


class _MiniLMEncoder:
    """Small local-only mean-pooling encoder for the pinned MiniLM snapshot."""

    def __init__(self, model_path: str | Path, revision: str):
        if revision != MINILM_REVISION:
            raise ValueError(f"semantic model revision must be pinned to {MINILM_REVISION}")
        path = Path(model_path).expanduser()
        if not path.is_dir():
            raise FileNotFoundError(f"local semantic model snapshot not found: {path}")
        try:
            from transformers import AutoModel, AutoTokenizer
            import torch
        except ImportError as exc:
            raise RuntimeError("semantic normalization requires the optional model dependencies") from exc

        # Both loads are strictly offline. Hugging Face snapshots normally record
        # _commit_hash in config.json; a copied snapshot can instead be attested by
        # its caller via the exact required `revision` argument above.
        config_path = path / "config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            recorded = config.get("_commit_hash")
            if recorded and recorded != revision:
                raise ValueError("local semantic snapshot commit does not match the pinned revision")
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(path), local_files_only=True)
        self.model.eval()

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        encoded = self.tokenizer(
            list(texts), padding=True, truncation=True, max_length=256, return_tensors="pt"
        )
        with self.torch.inference_mode():
            hidden = self.model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            pooled = self.torch.nn.functional.normalize(pooled, p=2, dim=1)
        return pooled.cpu().tolist()


class AspectNormalizer:
    """Alias-only by default; semantic matching must be explicitly opted into."""

    def __init__(
        self,
        *,
        ontology: Ontology | None = None,
        semantic_model_path: str | Path | None = None,
        semantic_revision: str | None = None,
        threshold: float | None = None,
        encoder: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
    ):
        self.ontology = ontology or get_ontology()
        if threshold is not None and not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if encoder is not None and semantic_model_path is not None:
            raise ValueError("provide either a local model path or an encoder, not both")
        if (semantic_model_path is not None or encoder is not None) and threshold is None:
            raise ValueError("semantic mode requires an explicitly calibrated threshold")
        if semantic_model_path is not None:
            if semantic_revision is None:
                raise ValueError("semantic mode requires the pinned model revision")
            self.encoder = _MiniLMEncoder(semantic_model_path, semantic_revision)
            self.semantic_revision = semantic_revision
        else:
            if semantic_revision is not None:
                raise ValueError("semantic_revision is only valid when semantic mode is enabled")
            self.encoder = encoder
            self.semantic_revision = None
        self.threshold = threshold
        self._alias_map = self.ontology.alias_to_aspect
        self._embedding_cache: dict[str, tuple[float, ...]] = {}
        self._phrase_vectors: dict[str, tuple[tuple[str, tuple[float, ...]], ...]] = {}
        if self.encoder is not None:
            phrases = sorted({
                _normalize_text(value)
                for aspect in self.ontology.aspects
                for value in (aspect.display_label, *aspect.aliases)
            })
            self._cache_embeddings(phrases)
            self._phrase_vectors = {
                aspect.id: tuple(
                    (phrase, self._embedding_cache[phrase])
                    for phrase in sorted({_normalize_text(v) for v in (aspect.display_label, *aspect.aliases)})
                )
                for aspect in self.ontology.aspects
            }

    @property
    def semantic_enabled(self) -> bool:
        return self.encoder is not None

    @property
    def version(self) -> str:
        mode = "alias-only" if not self.semantic_enabled else f"minilm-{self.semantic_revision}-t{self.threshold:.2f}"
        return f"{self.ontology.version}+{mode}"

    def _cache_embeddings(self, phrases: Iterable[str]) -> None:
        missing = [phrase for phrase in phrases if phrase not in self._embedding_cache]
        if not missing:
            return
        vectors = self.encoder(missing)  # type: ignore[misc]
        if len(vectors) != len(missing):
            raise ValueError("semantic encoder returned the wrong number of embeddings")
        for phrase, vector in zip(missing, vectors):
            values = tuple(float(value) for value in vector)
            if not values or any(not math.isfinite(value) for value in values):
                raise ValueError("semantic embeddings must be non-empty and finite")
            norm = math.sqrt(sum(value * value for value in values))
            if norm == 0:
                raise ValueError("semantic embeddings cannot be zero vectors")
            self._embedding_cache[phrase] = tuple(value / norm for value in values)

    def normalize(self, raw_aspect: str, *, context: str | None = None) -> NormalizationResult:
        raw = raw_aspect.strip()
        key = _normalize_text(raw)
        if not key:
            return NormalizationResult(raw, None, None, "unknown", None, True)
        exact = self._alias_map.get(key)
        if exact is not None:
            return NormalizationResult(raw, exact.id, exact.display_label, "alias", 1.0, False)

        # "charge" is polysemous. Semantic mode only considers it when the caller
        # supplies review context; without that evidence it remains explicitly unknown.
        if key == "charge" and not (context and context.strip()):
            return NormalizationResult(raw, None, None, "unknown", None, True)
        if not self.semantic_enabled:
            return NormalizationResult(raw, None, None, "unknown", None, True)

        query = _normalize_text(f"{raw} {context or ''}")
        self._cache_embeddings([query])
        vector = self._embedding_cache[query]
        scores: list[tuple[float, str]] = []
        for aspect in self.ontology.aspects:
            phrase_vectors = self._phrase_vectors[aspect.id]
            score = max(_cosine(vector, phrase_vector) for _, phrase_vector in phrase_vectors)
            scores.append((score, aspect.id))
        best_score = max(score for score, _ in scores)
        tied = sorted(identifier for score, identifier in scores if best_score - score <= TIE_TOLERANCE)
        if len(tied) != 1 or best_score < self.threshold:  # inclusive boundary: score == threshold is accepted
            return NormalizationResult(raw, None, None, "unknown", round(best_score, 6), True)
        aspect = self.ontology.by_id[tied[0]]
        return NormalizationResult(raw, aspect.id, aspect.display_label, "semantic", round(best_score, 6), False)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("semantic embedding dimensions do not match")
    return sum(a * b for a, b in zip(left, right))


_DEFAULT_NORMALIZER = AspectNormalizer()


def normalize_aspect(aspect: str, threshold: float | None = None):
    """Legacy compatibility adapter; fuzzy rules were removed to avoid guessing.

    Semantic matching is available through an explicitly configured
    :class:`AspectNormalizer`. The legacy threshold argument is accepted but does
    not activate semantics because no validated threshold/model is implicit.
    """
    del threshold
    result = _DEFAULT_NORMALIZER.normalize(aspect)
    # Existing callers expect the original compact schema object.
    from .schemas import NormalizationResult as LegacyNormalizationResult

    return LegacyNormalizationResult(
        raw_aspect=result.raw_aspect,
        normalized_aspect=result.normalized_aspect,
        similarity=result.similarity if result.similarity is not None else 0.0,
        is_unknown=result.is_unknown,
    )
