from collections import Counter, defaultdict
from .schemas import ProductAggregate, Review, TagResult, Sentiment


def aggregate(product_id: str, rows: list[tuple[Review, list[TagResult]]]) -> ProductAggregate:
    aspect_counts, sentiments = Counter(), Counter()
    grouped = defaultdict(list)
    for review, tags in rows:
        for tag in tags:
            if tag.normalized_aspect is None:
                continue
            aspect_counts[tag.normalized_aspect] += 1
            sentiments[tag.sentiment.value] += 1
            grouped[(tag.normalized_aspect, tag.sentiment)].append((review, tag))

    def ranked(sentiment):
        out = []
        for (aspect, label), values in grouped.items():
            if label is sentiment:
                out.append({"aspect": aspect, "tag": values[0][1].tag, "mentions": len(values), "ratio": round(len(values) / max(aspect_counts[aspect], 1), 4)})
        return sorted(out, key=lambda x: (-x["mentions"], x["aspect"]))

    representatives = []
    for (aspect, label), values in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0][0])):
        review, tag = values[0]
        representatives.append({"aspect": aspect, "sentiment": label.value, "review_id": review.review_id, "review_text": review.review_text, "tag": tag.tag})
    return ProductAggregate(product_id, ranked(Sentiment.POSITIVE), ranked(Sentiment.NEGATIVE), dict(sentiments), dict(aspect_counts), representatives)
