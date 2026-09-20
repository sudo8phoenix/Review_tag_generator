"""Validated API v1 data transfer objects.

Offsets use Python/Unicode code point indexes into the exact submitted text.
Confidence values are uncalibrated model scores, not probabilities of correctness.
"""

from __future__ import annotations

from datetime import timezone
from enum import Enum, IntEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


CONTRACT_VERSION = "1.0"
MAX_REVIEW_CHARS = 10_000
MAX_INLINE_REVIEWS = 100
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_TOP_K = 10
MAX_TOP_K = 50
PROBABILITY_TOLERANCE = 1e-5

SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Version = Annotated[str, StringConstraints(min_length=1)]
PipelineVersion = SHA256
AggregateVersion = SHA256
AspectId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")]
UnitFloat = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Count = Annotated[int, Field(strict=True, ge=0)]
UtcDateTime = Annotated[AwareDatetime, AfterValidator(lambda value: value.astimezone(timezone.utc))]


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Sentiment(str, Enum):
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


class SentimentLabelId(IntEnum):
    NEGATIVE = 0
    NEUTRAL = 1
    POSITIVE = 2


class AspectLabelId(IntEnum):
    O = 0
    B_ASP = 1
    I_ASP = 2


class NormalizationMethod(str, Enum):
    ALIAS = "alias"
    SEMANTIC = "semantic"
    UNKNOWN = "unknown"


class Normalization(StrictDTO):
    method: NormalizationMethod
    similarity: UnitFloat | None
    is_unknown: bool

    @model_validator(mode="after")
    def check_method(self) -> "Normalization":
        if self.is_unknown != (self.method is NormalizationMethod.UNKNOWN):
            raise ValueError("unknown flag and method disagree")
        if self.method is NormalizationMethod.SEMANTIC and self.similarity is None:
            raise ValueError("semantic normalization requires similarity")
        return self


class Probabilities(StrictDTO):
    negative: UnitFloat
    neutral: UnitFloat
    positive: UnitFloat

    @model_validator(mode="after")
    def check_total(self) -> "Probabilities":
        if abs(self.negative + self.neutral + self.positive - 1) > PROBABILITY_TOLERANCE:
            raise ValueError("sentiment probabilities must sum to 1 within 1e-5")
        return self


class Mention(StrictDTO):
    mention_id: UUID
    raw_aspect: str = Field(min_length=1)
    start_char: Count
    end_char: Count
    aspect_confidence: UnitFloat
    normalized_aspect_id: AspectId | None
    normalized_aspect: str | None
    normalization: Normalization
    sentiment: Sentiment
    sentiment_confidence: UnitFloat
    probabilities: Probabilities
    tag: str | None
    confidence: UnitFloat
    context_start_char: Count
    context_end_char: Count

    @model_validator(mode="after")
    def check_local_consistency(self) -> "Mention":
        if self.end_char <= self.start_char:
            raise ValueError("mention end_char must exceed start_char")
        if self.context_end_char <= self.context_start_char:
            raise ValueError("context end_char must exceed start_char")
        if not (self.context_start_char <= self.start_char and self.end_char <= self.context_end_char):
            raise ValueError("sentiment context must contain the aspect span")
        if abs(self.confidence - min(self.aspect_confidence, self.sentiment_confidence)) > 1e-5:
            raise ValueError("confidence must be the minimum of aspect and sentiment confidence")
        if self.normalization.is_unknown:
            if self.normalized_aspect_id is not None or self.normalized_aspect is not None or self.tag is not None:
                raise ValueError("unknown aspects cannot have canonical labels or tags")
        elif not self.normalized_aspect_id or not self.normalized_aspect:
            raise ValueError("known aspects require canonical ID and label")
        if not self.normalization.is_unknown and not self.tag:
            raise ValueError("known aspects require a tag")
        if abs(getattr(self.probabilities, self.sentiment.value) - self.sentiment_confidence) > 1e-5:
            raise ValueError("sentiment confidence must match the selected probability")
        return self


class ModelHashes(StrictDTO):
    aspect_extractor: SHA256
    sentiment_classifier: SHA256


class Analysis(StrictDTO):
    review_text: str
    mentions: list[Mention]
    backend: Literal["transformer", "fake"]
    pipeline_version: PipelineVersion
    model_hashes: ModelHashes
    ontology_version: Version
    context_policy: Version
    elapsed_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    warnings: list[str]
    offset_unit: Literal["unicode_code_points"] = "unicode_code_points"

    @model_validator(mode="after")
    def check_offsets(self) -> "Analysis":
        for mention in self.mentions:
            if mention.end_char > len(self.review_text) or mention.context_end_char > len(self.review_text):
                raise ValueError("mention or context exceeds original review text")
            if self.review_text[mention.start_char:mention.end_char] != mention.raw_aspect:
                raise ValueError("raw_aspect must match the original review text slice")
        return self


def validate_original_text(analysis: Analysis, submitted_text: str) -> Analysis:
    """Call at the HTTP boundary before returning an analysis to its requester."""
    if analysis.review_text != submitted_text:
        raise ValueError("analysis text differs from submitted text")
    return analysis


class ReviewInput(StrictDTO):
    review_text: str
    rating: Annotated[int, Field(strict=True, ge=1, le=5)] | None = None

    @field_validator("review_text")
    @classmethod
    def nonblank_bounded_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("review_text must not be blank")
        if len(value) > MAX_REVIEW_CHARS:
            raise ValueError("review_text exceeds 10000 Unicode code points")
        return value


class PreviewRequest(ReviewInput):
    product_id: UUID


class PreviewQueued(StrictDTO):
    preview_id: UUID
    status_url: str = Field(pattern=r"^/api/previews/[0-9a-fA-F-]{36}$")
    expires_at: UtcDateTime

    @model_validator(mode="after")
    def check_url(self) -> "PreviewQueued":
        if not self.status_url.endswith(str(self.preview_id)):
            raise ValueError("status_url must identify preview_id")
        return self


class PreviewStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PreviewResult(StrictDTO):
    preview_id: UUID
    status: PreviewStatus
    expires_at: UtcDateTime
    analysis: Analysis | None = None
    error: "ErrorDetail | None" = None

    @model_validator(mode="after")
    def check_result(self) -> "PreviewResult":
        if self.status is PreviewStatus.COMPLETED and self.analysis is None:
            raise ValueError("completed preview requires analysis")
        if self.status is PreviewStatus.FAILED and self.error is None:
            raise ValueError("failed preview requires error")
        if self.status in (PreviewStatus.QUEUED, PreviewStatus.RUNNING) and (self.analysis or self.error):
            raise ValueError("pending preview cannot contain result or error")
        if self.status is PreviewStatus.COMPLETED and self.error is not None:
            raise ValueError("completed preview cannot contain error")
        if self.status is PreviewStatus.FAILED and self.analysis is not None:
            raise ValueError("failed preview cannot contain analysis")
        return self


class ReviewSubmission(ReviewInput):
    source: Literal["manual"] = "manual"


class SubmitReviewsRequest(StrictDTO):
    reviews: Annotated[list[ReviewSubmission], Field(min_length=1, max_length=MAX_INLINE_REVIEWS)]


class JobAccepted(StrictDTO):
    job_id: UUID
    review_ids: list[UUID] = Field(default_factory=list)
    duplicate_count: Count = 0


class JobType(str, Enum):
    REVIEW_SUBMISSION = "review_submission"
    IMPORT = "import"
    REGENERATION = "regeneration"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class Job(StrictDTO):
    job_id: UUID
    type: JobType
    status: JobStatus
    stage: str = Field(min_length=1)
    attempt: Count
    total_rows: Count
    accepted_rows: Count
    rejected_rows: Count
    duplicate_rows: Count
    completed_rows: Count
    failed_rows: Count
    error_code: str | None
    error_summary: str | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    result_url: str | None

    @model_validator(mode="after")
    def check_counts(self) -> "Job":
        if self.type is JobType.IMPORT and self.total_rows != self.accepted_rows + self.rejected_rows + self.duplicate_rows:
            raise ValueError("import total_rows must equal accepted + rejected + duplicates")
        if self.completed_rows + self.failed_rows > self.accepted_rows:
            raise ValueError("processed rows cannot exceed accepted rows")
        if self.status is JobStatus.COMPLETED and (self.failed_rows or self.rejected_rows):
            raise ValueError("completed with failures/rejections must use completed_with_errors")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        return self


class Product(StrictDTO):
    product_id: UUID
    source: str = Field(min_length=1)
    external_product_id: str | None
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    brand: str | None
    created_at: UtcDateTime


class SentimentCounts(StrictDTO):
    positive: Count
    neutral: Count
    negative: Count


class SentimentRatios(StrictDTO):
    positive: UnitFloat
    neutral: UnitFloat
    negative: UnitFloat

    @model_validator(mode="after")
    def check_total(self) -> "SentimentRatios":
        total = self.positive + self.neutral + self.negative
        if total and abs(total - 1) > PROBABILITY_TOLERANCE:
            raise ValueError("nonempty sentiment ratios must sum to 1")
        return self


class ReviewCounts(StrictDTO):
    total: Count
    analyzed: Count
    pending: Count
    failed: Count
    no_aspect: Count

    @model_validator(mode="after")
    def check_counts(self) -> "ReviewCounts":
        if self.analyzed + self.pending + self.failed != self.total:
            raise ValueError("review status counts must sum to total")
        if self.no_aspect > self.analyzed:
            raise ValueError("no_aspect cannot exceed analyzed")
        return self


class AspectClassification(str, Enum):
    STRENGTH = "strength"
    WEAKNESS = "weakness"
    MIXED = "mixed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AspectInsight(StrictDTO):
    aspect_id: AspectId
    label: str = Field(min_length=1)
    counts: SentimentCounts
    ratios: SentimentRatios
    mention_count: Count
    review_count: Count
    average_confidence: UnitFloat
    score: Annotated[float, Field(allow_inf_nan=False)]
    aggregate_tag: str | None
    classification: AspectClassification
    rank: Annotated[int, Field(strict=True, ge=1)]

    @model_validator(mode="after")
    def check_counts(self) -> "AspectInsight":
        if self.review_count > self.mention_count:
            raise ValueError("review_count cannot exceed mention_count")
        if sum((self.counts.positive, self.counts.neutral, self.counts.negative)) != self.review_count:
            raise ValueError("sentiment votes must equal review_count")
        for sentiment in ("positive", "neutral", "negative"):
            expected = getattr(self.counts, sentiment) / self.review_count if self.review_count else 0
            if abs(getattr(self.ratios, sentiment) - expected) > PROBABILITY_TOLERANCE:
                raise ValueError("sentiment ratios must match vote counts")
        return self


class RepresentativeReview(StrictDTO):
    review_id: UUID
    excerpt: str
    mention_ids: Annotated[list[UUID], Field(min_length=1)]
    confidence: UnitFloat


class AspectRepresentatives(StrictDTO):
    aspect_id: AspectId
    positive: list[RepresentativeReview]
    neutral: list[RepresentativeReview]
    negative: list[RepresentativeReview]


class ProductInsights(StrictDTO):
    product: Product
    snapshot_id: UUID | None
    pipeline_version: PipelineVersion
    aggregate_version: AggregateVersion
    data_revision: Count
    stale: bool
    generated_at: UtcDateTime | None
    review_counts: ReviewCounts
    sentiment_distribution: SentimentCounts
    aspects: list[AspectInsight]
    strengths: list[AspectId]
    weaknesses: list[AspectId]
    mixed: list[AspectId]
    insufficient_evidence: list[AspectId]
    representative_reviews: list[AspectRepresentatives]

    @model_validator(mode="after")
    def check_snapshot(self) -> "ProductInsights":
        if (self.snapshot_id is None) != (self.generated_at is None):
            raise ValueError("snapshot_id and generated_at must both be present or absent")
        classification_lists = {
            AspectClassification.STRENGTH: self.strengths,
            AspectClassification.WEAKNESS: self.weaknesses,
            AspectClassification.MIXED: self.mixed,
            AspectClassification.INSUFFICIENT_EVIDENCE: self.insufficient_evidence,
        }
        aspects_by_id = {aspect.aspect_id: aspect for aspect in self.aspects}
        if len(aspects_by_id) != len(self.aspects):
            raise ValueError("aspect IDs must be unique")
        listed = [aspect_id for values in classification_lists.values() for aspect_id in values]
        if len(set(listed)) != len(listed) or set(listed) != set(aspects_by_id):
            raise ValueError("classification lists must partition aspect IDs")
        for classification, values in classification_lists.items():
            if any(aspects_by_id[aspect_id].classification is not classification for aspect_id in values):
                raise ValueError("aspect classification and reference list disagree")
        if any(group.aspect_id not in aspects_by_id for group in self.representative_reviews):
            raise ValueError("representative review refers to absent aspect")
        if len({group.aspect_id for group in self.representative_reviews}) != len(self.representative_reviews):
            raise ValueError("representative aspect groups must be unique")
        return self


class SupportedTag(StrictDTO):
    aspect_id: AspectId
    label: str
    tag: str
    classification: Literal["strength", "weakness", "mixed"]
    rank: Annotated[int, Field(strict=True, ge=1)]
    review_count: Count


class ProductTags(StrictDTO):
    product_id: UUID
    snapshot_id: UUID | None
    pipeline_version: PipelineVersion
    aggregate_version: AggregateVersion
    data_revision: Count
    stale: bool
    generated_at: UtcDateTime | None
    tags: list[SupportedTag]

    @model_validator(mode="after")
    def check_snapshot(self) -> "ProductTags":
        if (self.snapshot_id is None) != (self.generated_at is None):
            raise ValueError("snapshot_id and generated_at must both be present or absent")
        if self.snapshot_id is None and self.tags:
            raise ValueError("tags require a published snapshot")
        if len({tag.aspect_id for tag in self.tags}) != len(self.tags):
            raise ValueError("tag aspect IDs must be unique")
        if len({tag.rank for tag in self.tags}) != len(self.tags):
            raise ValueError("tag ranks must be unique")
        return self


class PageQuery(StrictDTO):
    page: Annotated[int, Field(strict=True, ge=1)] = 1
    page_size: Annotated[int, Field(strict=True, ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE


class ProductsQuery(PageQuery):
    search: str | None = None


class ReviewsQuery(PageQuery):
    aspect_id: AspectId | None = None
    sentiment: Sentiment | None = None


class TagsQuery(StrictDTO):
    top_k: Annotated[int, Field(strict=True, ge=1, le=MAX_TOP_K)] = DEFAULT_TOP_K


class ProductPage(PageQuery):
    items: list[Product]
    total: Count


class ReviewDetail(ReviewInput):
    review_id: UUID
    product_id: UUID
    source: str = Field(min_length=1)
    analysis_status: Literal["pending", "running", "completed", "failed"]
    analysis: Analysis | None
    submitted_at: UtcDateTime

    @model_validator(mode="after")
    def check_analysis(self) -> "ReviewDetail":
        if self.analysis_status == "completed" and self.analysis is None:
            raise ValueError("completed review requires compatible analysis")
        if self.analysis_status != "completed" and self.analysis is not None:
            raise ValueError("non-completed review cannot contain analysis")
        if self.analysis is not None:
            validate_original_text(self.analysis, self.review_text)
        return self


class ReviewPage(PageQuery):
    items: list[ReviewDetail]
    total: Count


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    PREVIEW_EXPIRED = "PREVIEW_EXPIRED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    QUEUE_FULL = "QUEUE_FULL"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorIssue(StrictDTO):
    field: str | None = None
    message: str


class ErrorDetail(StrictDTO):
    code: ErrorCode
    message: str = Field(min_length=1)
    details: list[ErrorIssue]
    retryable: bool


class ErrorEnvelope(StrictDTO):
    error: ErrorDetail
    request_id: UUID


class Health(StrictDTO):
    status: Literal["ok"] = "ok"


class Ready(StrictDTO):
    status: Literal["ready"] = "ready"
    pipeline_version: PipelineVersion


class MetricRecord(StrictDTO):
    task_id: str
    protocol: str
    pipeline_version: PipelineVersion | None
    metrics: dict[str, Annotated[float, Field(allow_inf_nan=False)]]


class ModelMetrics(StrictDTO):
    historical: list[MetricRecord]
    current: list[MetricRecord]


def validate_idempotency_key(value: str) -> UUID:
    """Use for the Idempotency-Key header on every mutating job endpoint."""
    parsed = UUID(value)
    if str(parsed) != value.lower():
        raise ValueError("Idempotency-Key must be a canonical UUID")
    return parsed
