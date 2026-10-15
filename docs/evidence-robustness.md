# Evidence robustness report

A product tag can look convincing while depending on just one review. This
feature measures that dependency using the votes in the published product snapshot.
It performs no additional inference and does not change stored reviews or tags.

## Use it

Start the app, save several reviews for a product, and let its job finish. Request:

```bash
curl --fail http://127.0.0.1:8000/api/demo/products/demo-laptop/evidence-audit
```

With Compose, use port 8080 instead. Replace `demo-laptop` with another product UUID
as needed. The product insights page includes an interactive Evidence robustness panel with
aspect selection, vote-removal scenarios, and a JSON download. The endpoint also
appears in the FastAPI `/docs` interface.

The response includes the published snapshot ID, pipeline version, aggregate
version, revision and stale flag. Pending imports do not leak partial evidence
into the report. Before the first snapshot, the aspect list is empty.

## Method

For each aspect, remove one review-aspect vote and apply the same classification
policy used by normal aggregation. Reviews with the same vote have the same
outcome, so at most three scenarios are needed per aspect. Each scenario records
how many reviews it represents. No model calls or review-by-review reprocessing
are necessary.

- `classification_stability`: fraction of possible single-review removals that
  preserve the exact classification, such as `excellent`.
- `tag_stability`: fraction that preserve the tag family. `excellent` and `good`
  share a positive template; `poor` and `weak` share a negative template. Neutral,
  mixed, and insufficient evidence each remain separate.
- `fragile_tag`: a supported tag changes or disappears under at least one removal.
- `opposing_review_votes`: different reviewers cast both positive and negative votes.
- `contradictory_review_count`: reviews containing both positive and negative
  mentions of this same aspect, which aggregate as neutral votes.
- `ordinary_neutral_review_count`: neutral votes excluding those contradictions.
- `removal_scenarios`: the resulting classification after removing each represented
  sentiment, including whether the tag stays unchanged.

Three positive reviews produce a positive tag, but removing any one drops support
to two: tag stability is 0. Four positive and one neutral review classify as
excellent. Removing a positive changes the classification to good while keeping
the positive tag, so classification stability is 0.2 and tag stability is 1.
Three positive and two negative reviews have tag stability 0.4: removing a positive
flips the classification from good to weak, while removing a negative preserves
the positive tag.

An unsupported aspect is explicitly marked `supported=false`; an unchanged lack
of a tag is not evidence of a strong product claim.

## Interpretation and scope

This is a deterministic sensitivity diagnostic, not a probability of correctness,
confidence interval, fake-review detector, or new trained model. Its one-vote
removals do not model correlated reviewers or coordinated manipulation. It does
not audit changes in ranking or representative selection. A stable result can
still reflect systematic ML errors. Use it alongside the original review evidence
and recorded evaluation scores.

The project contribution is the integration of this check with deduplicated
aspect votes, explicit within-review contradiction counts, and immutable published
snapshot provenance. Do not describe leave-one-out analysis itself as novel research.

## Reviewer decisions

This report uses original saved model predictions. Separate
[corrections](review-corrections.md) and [full-review annotations](review-annotations.md)
do not alter its votes or certify the correctness of a stable tag.
