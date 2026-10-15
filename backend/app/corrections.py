"""Source-linked review decisions; model predictions and snapshots stay immutable."""
from copy import deepcopy
from datetime import timezone
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from backend.app.db.models import AnalysisRun, ProductSnapshot, ReviewCorrection, ReviewRecord, ReviewSuggestion
from backend.app.repository import Conflict
from review_tag_generator.normalization import get_ontology


class ReviewReference(BaseModel):
    model_config = ConfigDict(extra='forbid')
    snapshot_id: UUID
    review_id: UUID


class MentionReference(ReviewReference):
    start_char: int = Field(ge=0, strict=True)
    end_char: int = Field(ge=1, strict=True)


class CorrectionInput(MentionReference):
    request_id: UUID
    expected_previous_id: UUID | None = None
    suggestion_id: UUID | None = None
    decision: Literal['accepted', 'edited', 'rejected']
    reviewer: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)
    canonical_id: str | None = Field(default=None, max_length=100)
    sentiment: Literal['positive', 'neutral', 'negative'] | None = None
    supported: bool = Field(default=True, strict=True)

    @field_validator('reviewer', 'reason')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Enter a reviewer name and reason')
        return value.strip()

    @model_validator(mode='after')
    def decision_fields(self):
        if self.decision in ('accepted', 'rejected'):
            if not self.suggestion_id:
                raise ValueError('Accepting or rejecting requires a saved suggestion')
            if self.canonical_id is not None or self.sentiment is not None or not self.supported:
                raise ValueError('Use edit to change the mapping, sentiment or support decision')
        elif self.supported:
            if self.sentiment is None or 'canonical_id' not in self.model_fields_set:
                raise ValueError('A correction needs sentiment and an explicit canonical ID or null')
        elif self.canonical_id is not None or self.sentiment is not None:
            raise ValueError('Unsupported mentions cannot have a canonical ID or sentiment')
        return self


class InvalidCorrection(ValueError):
    pass


class Corrections:
    def __init__(self, repository):
        self.repository = repository

    def _review_context(self, db, product_id, reference, lock=False):
        product = self.repository.require_product(db, product_id, lock=lock)
        if product.current_snapshot_id != reference.snapshot_id:
            raise Conflict('The product snapshot changed. Reload the product before reviewing this evidence.')
        snapshot = db.get(ProductSnapshot, reference.snapshot_id)
        run = db.scalar(select(AnalysisRun).join(ReviewRecord).where(
            ReviewRecord.product_id == product.id, ReviewRecord.id == reference.review_id,
            AnalysisRun.pipeline_version == snapshot.pipeline_version))
        membership = snapshot.payload.get('_review_ids')
        if (not run or not run.payload or (membership is not None and str(reference.review_id) not in membership)
                or (membership is None and run.created_at > snapshot.created_at)):
            raise LookupError('Saved analysis is not part of this published product snapshot')
        review = db.get(ReviewRecord, reference.review_id)
        return product, snapshot, run, review

    def _context(self, db, product_id, reference, lock=False):
        product, snapshot, run, review = self._review_context(db, product_id, reference, lock)
        original = next((tag for tag in run.payload.get('tags', [])
                         if tag.get('start_char') == reference.start_char and tag.get('end_char') == reference.end_char), None)
        if not original or review.review_text[reference.start_char:reference.end_char] != original['raw_aspect']:
            raise InvalidCorrection('Select an exact saved aspect span from this analysis')
        return product, snapshot, run, review, original

    def context(self, product_id, reference):
        with self.repository.transaction() as db:
            _, _, _, review, original = self._context(db, product_id, reference)
            return {'review_text': review.review_text, 'original': deepcopy(original)}

    def save_suggestion(self, product_id, reference, suggestion):
        with self.repository.transaction() as db:
            _, _, run, _, original = self._context(db, product_id, reference, lock=True)
            if original.get('normalized_aspect_id') is not None:
                raise InvalidCorrection('Mapping assistance is for unknown aspects')
            row = ReviewSuggestion(id=uuid4(), analysis_run_id=run.id, snapshot_id=reference.snapshot_id,
                start_char=reference.start_char, end_char=reference.end_char, payload=deepcopy(suggestion))
            db.add(row)
            db.flush()
            return {**row.payload, 'id': str(row.id)}

    @staticmethod
    def _record(row):
        created_at = row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at.astimezone(timezone.utc)
        return {'id': str(row.id), 'snapshot_id': str(row.snapshot_id),
                'decision': row.decision, 'reviewer': row.reviewer, 'reason': row.reason,
                'created_at': created_at.isoformat(), **row.payload}

    def history(self, product_id, reference):
        with self.repository.transaction() as db:
            _, snapshot, run, _, original = self._context(db, product_id, reference)
            rows = list(db.scalars(select(ReviewCorrection).where(ReviewCorrection.analysis_run_id == run.id,
                ReviewCorrection.start_char == reference.start_char, ReviewCorrection.end_char == reference.end_char)
                .order_by(ReviewCorrection.created_at.desc(), ReviewCorrection.id.desc())))
            return {'items': [self._record(row) for row in rows], 'snapshot_id': str(snapshot.id),
                    'latest_id': str(rows[0].id) if rows else None, 'original': original}

    def save(self, product_id, body):
        request_hash = sha256(json.dumps(body.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
        with self.repository.transaction() as db:
            _, snapshot, run, review, original = self._context(db, product_id, body, lock=True)
            replay = db.scalar(select(ReviewCorrection).where(
                ReviewCorrection.analysis_run_id == run.id, ReviewCorrection.request_id == body.request_id))
            if replay:
                if replay.request_sha256 != request_hash:
                    raise Conflict('This request ID was already used for a different decision')
                return self._record(replay)
            latest = db.scalar(select(ReviewCorrection).where(ReviewCorrection.analysis_run_id == run.id,
                ReviewCorrection.start_char == body.start_char, ReviewCorrection.end_char == body.end_char)
                .order_by(ReviewCorrection.created_at.desc(), ReviewCorrection.id.desc()).limit(1))
            if (latest.id if latest else None) != body.expected_previous_id:
                raise Conflict('Another decision was saved for this aspect. Reload decision history before saving.')
            suggestion = None
            if body.suggestion_id:
                suggestion = db.get(ReviewSuggestion, body.suggestion_id)
                if (not suggestion or suggestion.analysis_run_id != run.id or suggestion.snapshot_id != snapshot.id
                        or (suggestion.start_char, suggestion.end_char) != (body.start_char, body.end_char)):
                    raise InvalidCorrection('The suggestion does not belong to this saved aspect and snapshot')
            ontology = get_ontology()
            resolution = None
            if body.decision == 'accepted':
                canonical_id = suggestion.payload.get('canonical_aspect_id')
                proposed = suggestion.payload.get('proposed_aspect_label')
                if canonical_id is None and not proposed:
                    raise InvalidCorrection('An abstention has no mapping to accept; edit or reject it instead')
                if canonical_id is not None and canonical_id not in ontology.by_id:
                    raise InvalidCorrection('The suggested canonical aspect is no longer in the ontology')
                resolution = {'supported': True, 'canonical_id': canonical_id,
                              'proposed_aspect_label': proposed, 'sentiment': original['sentiment']}
            elif body.decision == 'edited':
                if body.canonical_id is not None and body.canonical_id not in ontology.by_id:
                    raise InvalidCorrection('Choose a canonical aspect from the current ontology or Unknown')
                resolution = {'supported': body.supported, 'canonical_id': body.canonical_id,
                              'proposed_aspect_label': None, 'sentiment': body.sentiment}
            payload = {
                'review_id': str(review.id), 'analysis_run_id': str(run.id), 'pipeline_version': run.pipeline_version,
                'ontology_version': ontology.version, 'original_text_sha256': run.original_text_sha256,
                'start_char': body.start_char, 'end_char': body.end_char,
                'original': deepcopy(original), 'resolution': resolution,
                'suggestion_id': str(suggestion.id) if suggestion else None,
                'suggestion': deepcopy(suggestion.payload) if suggestion else None,
                'previous_id': str(latest.id) if latest else None,
                'applied_to_predictions': False,
                'reviewer_identity': 'Self-reported; this local demo does not authenticate reviewers',
            }
            row = ReviewCorrection(id=uuid4(), analysis_run_id=run.id, snapshot_id=snapshot.id,
                request_id=body.request_id, request_sha256=request_hash,
                start_char=body.start_char, end_char=body.end_char,
                decision=body.decision, reviewer=body.reviewer, reason=body.reason, payload=payload)
            db.add(row)
            db.flush()
            return self._record(row)

    def export(self, product_id):
        with self.repository.transaction() as db:
            product = self.repository.require_product(db, product_id)
            rows = db.execute(select(ReviewCorrection, ReviewRecord.review_text)
                .join(AnalysisRun, ReviewCorrection.analysis_run_id == AnalysisRun.id)
                .join(ReviewRecord, AnalysisRun.review_id == ReviewRecord.id)
                .where(ReviewRecord.product_id == product.id)
                .order_by(ReviewCorrection.created_at, ReviewCorrection.id)).all()
            return {'product_id': str(product.id), 'items': [
                {**self._record(row), 'review_text': text} for row, text in rows],
                'notice': 'Reviewer decisions with source provenance. Not independently adjudicated gold labels. Original model predictions and product totals are unchanged.'}
