"""Ephemeral shopping summaries using the saved-analysis aggregation policy."""
from dataclasses import asdict
from datetime import timezone

from fastapi import HTTPException
from sqlalchemy import select

from backend.app.db.models import AnalysisPreview, utcnow
from backend.app.repository import text_hash
from review_tag_generator.aggregation import SavedReviewAnalysis, aggregate_saved_analyses
from review_tag_generator.schemas import Review, Sentiment, TagResult


def summarize_previews(repository, product_id, preview_ids, pipeline_version):
    """Read completed previews without publishing or changing product totals."""
    ids = list(dict.fromkeys(preview_ids))
    with repository.transaction() as db:
        product = repository.require_product(db, product_id)
        previews = list(db.scalars(select(AnalysisPreview).where(
            AnalysisPreview.id.in_(ids), AnalysisPreview.product_id == product.id)))
        if len(previews) != len(ids):
            raise HTTPException(404, 'One or more previews do not belong to this product or no longer exist')
        by_id = {item.id: item for item in previews}
        unique, seen = [], set()
        for preview_id in ids:
            item = by_id[preview_id]
            if item.expires_at.replace(tzinfo=timezone.utc) <= utcnow():
                raise HTTPException(410, 'Preview expired; analyze the captured reviews again')
            if item.pipeline_version != pipeline_version:
                raise HTTPException(409, 'Analysis version changed; preview again before summarizing')
            if item.status != 'completed' or not item.analysis:
                raise HTTPException(409, 'Every preview must complete successfully before summarizing')
            key = text_hash(item.review_text)
            if key in seen:
                continue
            seen.add(key)
            analysis = item.analysis
            unique.append(SavedReviewAnalysis(
                Review(**analysis['review']),
                [TagResult(**{**tag, 'sentiment': Sentiment(tag['sentiment'])}) for tag in analysis['tags']]))
        return {
            'saved': False,
            'pipeline_version': pipeline_version,
            'duplicate_reviews': len(previews) - len(unique),
            'insights': asdict(aggregate_saved_analyses(str(product.id), unique)),
        }
