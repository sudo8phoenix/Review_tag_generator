"""Deterministic sensitivity analysis of published review-aspect votes."""
from .aggregation import classify_votes


def tag_family(classification):
    return {
        'excellent': 'positive', 'good': 'positive',
        'poor': 'negative', 'weak': 'negative',
    }.get(classification, classification)


def audit_evidence(insights):
    aspects = []
    for aspect in insights['aspects']:
        counts = aspect['counts']
        classification = classify_votes(counts)
        removals = []
        unchanged_classification = unchanged_tag = 0
        for sentiment, count in counts.items():
            if not count:
                continue
            remaining = {**counts, sentiment: count - 1}
            outcome = classify_votes(remaining)
            same_class = outcome == classification
            same_tag = tag_family(outcome) == tag_family(classification)
            unchanged_classification += count if same_class else 0
            unchanged_tag += count if same_tag else 0
            removals.append({'removed_vote': sentiment, 'review_count': count,
                'classification_after_removal': outcome, 'tag_unchanged': same_tag})
        total = sum(counts.values())
        contradictory = aspect['contradictory_review_count']
        aspects.append({
            'aspect_id': aspect['aspect_id'], 'aspect': aspect['aspect'],
            'review_count': total, 'classification': classification,
            'supported': total >= 3,
            'classification_stability': unchanged_classification / total,
            'tag_stability': unchanged_tag / total,
            'fragile_tag': total >= 3 and unchanged_tag < total,
            'opposing_review_votes': bool(counts['positive'] and counts['negative']),
            'contradictory_review_count': contradictory,
            'ordinary_neutral_review_count': counts['neutral'] - contradictory,
            'removal_scenarios': removals,
        })
    return {'method': 'leave_one_review_out_v1', 'aspects': aspects,
        'note': 'Sensitivity of saved predictions, not model accuracy or a statistical confidence interval.'}
