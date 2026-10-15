"""Full-review span annotation with explicit progress and immutable revisions."""
from collections import Counter
from copy import deepcopy
from datetime import timezone
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from backend.app.corrections import Corrections, InvalidCorrection, ReviewReference
from backend.app.db.models import AnalysisRun, ProductSnapshot, ReviewAnnotation, ReviewCorrection, ReviewRecord
from backend.app.repository import Conflict
from review_tag_generator.normalization import get_ontology

ReviewStatus = Literal['needs_review', 'reviewed', 'needs_adjudication']
STATUSES = ('needs_review', 'reviewed', 'needs_adjudication')


class AnnotatedMention(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw_aspect: str = Field(min_length=1, max_length=10000)
    start_char: int = Field(ge=0, strict=True)
    end_char: int = Field(ge=1, strict=True)
    canonical_id: str | None = Field(max_length=100)
    sentiment: Literal['positive', 'neutral', 'negative']


class AnnotationInput(ReviewReference):
    request_id: UUID
    expected_previous_id: UUID | None = None
    expected_correction_id: UUID | None = None
    status: ReviewStatus
    reviewer: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)
    mentions: list[AnnotatedMention] = Field(max_length=200)
    confirmed_no_aspects: bool = Field(default=False, strict=True)

    @field_validator('reviewer', 'reason')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Enter a reviewer name and review notes')
        return value.strip()

    @model_validator(mode='after')
    def explicit_empty_review(self):
        if self.status == 'reviewed' and not self.mentions and not self.confirmed_no_aspects:
            raise ValueError('Confirm that this review has no explicit aspects before marking it reviewed')
        if self.mentions and self.confirmed_no_aspects:
            raise ValueError('A review with aspect mentions cannot be confirmed as having no aspects')
        return self


def timestamp(value):
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()


def record(row):
    return {'id': str(row.id), 'snapshot_id': str(row.snapshot_id), 'status': row.status,
            'reviewer': row.reviewer, 'reason': row.reason, 'created_at': timestamp(row.created_at), **row.payload}


def effective_status(annotation, correction):
    changed = bool(annotation and annotation.payload.get('correction_revision') != (str(correction.id) if correction else None))
    return ('needs_review' if changed else annotation.status if annotation else 'needs_review'), changed


class Annotations:
    def __init__(self, repository):
        self.repository = repository
        self.corrections = Corrections(repository)

    @staticmethod
    def _revisions(db, run_ids):
        annotations = list(db.scalars(select(ReviewAnnotation).where(ReviewAnnotation.analysis_run_id.in_(run_ids))
            .order_by(ReviewAnnotation.created_at.desc(), ReviewAnnotation.id.desc()))) if run_ids else []
        corrections = list(db.scalars(select(ReviewCorrection).where(ReviewCorrection.analysis_run_id.in_(run_ids))
            .order_by(ReviewCorrection.created_at.desc(), ReviewCorrection.id.desc()))) if run_ids else []
        return annotations, corrections

    def worklist(self, product_id, snapshot_id=None, status='all'):
        with self.repository.transaction() as db:
            product = self.repository.require_product(db, product_id)
            if snapshot_id is not None and snapshot_id != product.current_snapshot_id:
                raise Conflict('The product snapshot changed. Reload the annotation workspace.')
            snapshot = db.get(ProductSnapshot, product.current_snapshot_id) if product.current_snapshot_id else None
            rows = []
            if snapshot:
                query = select(AnalysisRun, ReviewRecord).join(ReviewRecord).where(
                    ReviewRecord.product_id == product.id, AnalysisRun.pipeline_version == snapshot.pipeline_version,
                    AnalysisRun.payload.is_not(None))
                membership = snapshot.payload.get('_review_ids')
                if membership is not None:
                    query = query.where(ReviewRecord.id.in_([UUID(value) for value in membership]))
                else:
                    query = query.where(AnalysisRun.created_at <= snapshot.created_at)
                rows = db.execute(query.order_by(ReviewRecord.submitted_at, ReviewRecord.id)).all()
            annotation_rows, correction_rows = self._revisions(db, [run.id for run, _ in rows])
            latest_annotations, latest_corrections = {}, {}
            for annotation in annotation_rows:
                latest_annotations.setdefault(annotation.analysis_run_id, annotation)
            for correction in correction_rows:
                latest_corrections.setdefault(correction.analysis_run_id, correction)
            items = []
            counts = Counter({key: 0 for key in STATUSES})
            for run, review in rows:
                annotation = latest_annotations.get(run.id)
                current_status, changed = effective_status(annotation, latest_corrections.get(run.id))
                counts[current_status] += 1
                if status != 'all' and current_status != status:
                    continue
                items.append({'review_id': str(review.id), 'review_text': review.review_text,
                    'status': current_status, 'corrections_changed': changed,
                    'latest_id': str(annotation.id) if annotation else None,
                    'reviewer': annotation.reviewer if annotation else None,
                    'updated_at': timestamp(annotation.created_at) if annotation else None,
                    'model_mentions': len(run.payload.get('tags', [])),
                    'annotated_mentions': len(annotation.payload['mentions']) if annotation else None})
            return {'product_id': str(product.id), 'snapshot_id': str(snapshot.id) if snapshot else None,
                    'pipeline_version': snapshot.pipeline_version if snapshot else None,
                    'summary': {'total': sum(counts.values()), **dict(counts)}, 'items': items}

    def detail(self, product_id, reference):
        with self.repository.transaction() as db:
            _, snapshot, run, review = self.corrections._review_context(db, product_id, reference)
            annotations, corrections = self._revisions(db, [run.id])
            latest = annotations[0] if annotations else None
            latest_correction = corrections[0] if corrections else None
            status, changed = effective_status(latest, latest_correction)
            if latest:
                mentions = deepcopy(latest.payload['mentions'])
            else:
                # Begin with model mentions and existing explicit correction decisions.
                # Nothing is considered reviewed until a reviewer saves the full review.
                draft = {(tag['start_char'], tag['end_char']): {
                    'raw_aspect': tag['raw_aspect'], 'start_char': tag['start_char'], 'end_char': tag['end_char'],
                    'canonical_id': tag.get('normalized_aspect_id'), 'sentiment': tag['sentiment'],
                } for tag in run.payload.get('tags', [])}
                for correction in reversed(corrections):
                    resolution = correction.payload.get('resolution')
                    if resolution is None:
                        continue
                    key = (correction.start_char, correction.end_char)
                    if not resolution['supported']:
                        draft.pop(key, None)
                    else:
                        draft[key] = {'raw_aspect': review.review_text[key[0]:key[1]], 'start_char': key[0], 'end_char': key[1],
                                      'canonical_id': resolution['canonical_id'], 'sentiment': resolution['sentiment']}
                mentions = sorted(draft.values(), key=lambda mention: (mention['start_char'], mention['end_char']))
            return {'review_id': str(review.id), 'review_text': review.review_text,
                    'snapshot_id': str(snapshot.id), 'pipeline_version': run.pipeline_version,
                    'status': status, 'saved_status': latest.status if latest else None, 'corrections_changed': changed,
                    'latest_id': str(latest.id) if latest else None,
                    'correction_revision': str(latest_correction.id) if latest_correction else None,
                    'mentions': mentions, 'reviewer': latest.reviewer if latest else '',
                    'reason': latest.reason if latest else '',
                    'confirmed_no_aspects': bool(latest and latest.payload['confirmed_no_aspects']),
                    'original_predictions': deepcopy(run.payload.get('tags', [])),
                    'history': [record(row) for row in annotations],
                    'correction_history': [self.corrections._record(row) for row in corrections]}

    def save(self, product_id, body):
        request_hash = sha256(json.dumps(body.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
        with self.repository.transaction() as db:
            _, snapshot, run, review = self.corrections._review_context(db, product_id, body, lock=True)
            replay = db.scalar(select(ReviewAnnotation).where(ReviewAnnotation.analysis_run_id == run.id,
                ReviewAnnotation.request_id == body.request_id))
            if replay:
                if replay.request_sha256 != request_hash:
                    raise Conflict('This request ID was already used for a different annotation')
                return record(replay)
            annotations, corrections = self._revisions(db, [run.id])
            latest = annotations[0] if annotations else None
            correction = corrections[0] if corrections else None
            if (latest.id if latest else None) != body.expected_previous_id:
                raise Conflict('Another annotation was saved. Reload the review before saving your changes.')
            if (correction.id if correction else None) != body.expected_correction_id:
                raise Conflict('Aspect decisions changed. Reload the review before saving your annotation.')
            ontology = get_ontology()
            mentions = sorted([mention.model_dump() for mention in body.mentions], key=lambda item: (item['start_char'], item['end_char']))
            previous_end = 0
            for mention in mentions:
                start, end = mention['start_char'], mention['end_char']
                if not 0 <= start < end <= len(review.review_text) or review.review_text[start:end] != mention['raw_aspect'] or not mention['raw_aspect'].strip():
                    raise InvalidCorrection('Every aspect must match a nonempty exact span in the saved review')
                if start < previous_end:
                    raise InvalidCorrection('Aspect spans overlap or repeat. Resolve the boundaries before saving.')
                if mention['canonical_id'] is not None and mention['canonical_id'] not in ontology.by_id:
                    raise InvalidCorrection('Choose a canonical aspect from the current ontology or Unknown')
                previous_end = end
            payload = {'review_id': str(review.id), 'analysis_run_id': str(run.id),
                'pipeline_version': run.pipeline_version, 'ontology_version': ontology.version,
                'original_text_sha256': run.original_text_sha256,
                'previous_id': str(latest.id) if latest else None,
                'correction_revision': str(correction.id) if correction else None,
                'mentions': mentions, 'confirmed_no_aspects': body.confirmed_no_aspects,
                'original_predictions': deepcopy(run.payload.get('tags', [])),
                'applied_to_predictions': False,
                'reviewer_identity': 'Self-reported; this local demo does not authenticate or independently adjudicate reviewers'}
            row = ReviewAnnotation(id=uuid4(), analysis_run_id=run.id, snapshot_id=snapshot.id,
                request_id=body.request_id, request_sha256=request_hash, status=body.status,
                reviewer=body.reviewer, reason=body.reason, payload=payload)
            db.add(row)
            db.flush()
            return record(row)

    def export(self, product_id, snapshot_id):
        # Hold the product lock while capturing export membership and revisions.
        with self.repository.transaction() as db:
            product = self.repository.require_product(db, product_id, lock=True)
            if product.current_snapshot_id != snapshot_id:
                raise Conflict('The product snapshot changed. Reload before exporting annotations.')
            snapshot = db.get(ProductSnapshot, snapshot_id)
            query = select(ReviewAnnotation, ReviewRecord).join(AnalysisRun,
                ReviewAnnotation.analysis_run_id == AnalysisRun.id).join(ReviewRecord,
                AnalysisRun.review_id == ReviewRecord.id).where(ReviewRecord.product_id == product.id,
                AnalysisRun.pipeline_version == snapshot.pipeline_version)
            membership = snapshot.payload.get('_review_ids')
            if membership is not None:
                query = query.where(ReviewRecord.id.in_([UUID(value) for value in membership]))
            else:
                query = query.where(AnalysisRun.created_at <= snapshot.created_at)
            rows = db.execute(query.order_by(ReviewAnnotation.created_at.desc(), ReviewAnnotation.id.desc())).all()
            _, corrections = self._revisions(db, list({row.analysis_run_id for row, _ in rows}))
            latest_corrections = {}
            for correction in corrections:
                latest_corrections.setdefault(correction.analysis_run_id, correction)
            items, seen = [], set()
            for annotation, review in rows:
                if annotation.analysis_run_id in seen:
                    continue
                seen.add(annotation.analysis_run_id)
                status, changed = effective_status(annotation, latest_corrections.get(annotation.analysis_run_id))
                items.append({**record(annotation), 'review_text': review.review_text,
                              'effective_status': status, 'corrections_changed': changed})
            return {'product_id': str(product.id), 'snapshot_id': str(snapshot.id), 'items': items,
                    'notice': 'Latest saved annotations for this published snapshot. Unannotated reviews are absent. Reviewed is self-reported completion, not independently adjudicated gold. Original predictions and totals are unchanged.'}
