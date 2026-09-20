from __future__ import annotations

from pathlib import Path

from .schemas import AspectPrediction, Sentiment, SentimentPrediction
from .sentiment import aspect_context_span
from .extraction import WindowSpanCandidate, merge_window_candidates


class ReviewTooLongError(ValueError):
    """The review cannot be analyzed completely within the configured model budget."""


class TransformerModels:
    """Thin inference wrapper around the two trained DistilBERT checkpoints."""

    def __init__(self, aspect_path: str | Path, sentiment_path: str | Path, max_length: int = 256, device: str = "cpu", extraction_stride: int = 64, max_review_tokens: int = 4096, context_policy: str = "local_clause"):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoModelForTokenClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install the optional transformer dependencies to load the trained models") from exc

        self.torch = torch
        self.max_length = max_length
        if not 0 < extraction_stride < max_length - 2:
            raise ValueError("Extraction stride must fit inside the model content window")
        self.extraction_stride = extraction_stride
        self.max_review_tokens = max_review_tokens
        if context_policy not in {"local_clause", "full_review"}:
            raise ValueError(f"Unknown sentiment context policy: {context_policy}")
        self.context_policy = context_policy
        if device not in {"cpu", "cuda", "mps"}:
            raise ValueError(f"Unsupported model device: {device}")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        if device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS requested but unavailable")
        self.device = torch.device(device)
        self.aspect_tokenizer = AutoTokenizer.from_pretrained(str(aspect_path), use_fast=True, local_files_only=True)
        self.aspect_model, aspect_info = AutoModelForTokenClassification.from_pretrained(
            str(aspect_path), local_files_only=True, output_loading_info=True
        )
        self.sentiment_tokenizer = AutoTokenizer.from_pretrained(str(sentiment_path), use_fast=True, local_files_only=True)
        self.sentiment_model, sentiment_info = AutoModelForSequenceClassification.from_pretrained(
            str(sentiment_path), local_files_only=True, output_loading_info=True
        )
        for name, info in (("aspect", aspect_info), ("sentiment", sentiment_info)):
            if any(info.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
                raise RuntimeError(f"{name} checkpoint did not load exactly: {info}")
        self.aspect_model = self.aspect_model.to(self.device).eval()
        self.sentiment_model = self.sentiment_model.to(self.device).eval()

    def extract_aspects(self, text: str) -> list[AspectPrediction]:
        if not text.strip():
            return []
        full_encoding = self.aspect_tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        token_ids = full_encoding["input_ids"]
        token_offsets = full_encoding["offset_mapping"]
        token_count = len(token_ids)
        if token_count > self.max_review_tokens:
            raise ReviewTooLongError(f"Review has {token_count} tokens; limit is {self.max_review_tokens}")
        content_capacity = self.max_length - self.aspect_tokenizer.num_special_tokens_to_add(pair=False)
        step = content_capacity - self.extraction_stride
        if step <= 0:
            raise ValueError("Extraction stride leaves no room for new tokens")
        candidates: list[WindowSpanCandidate] = []
        for window_index, first_token in enumerate(range(0, token_count, step)):
            chunk_ids = token_ids[first_token:first_token + content_capacity]
            chunk_offsets = token_offsets[first_token:first_token + content_capacity]
            # These checkpoints use DistilBERT's BERT tokenizer, whose single-sequence
            # input is [CLS] content [SEP]. Building it explicitly avoids the tokenizer
            # overflow path dropping the final tokens in the saved tokenizer revision.
            prepared_ids = [self.aspect_tokenizer.cls_token_id, *chunk_ids, self.aspect_tokenizer.sep_token_id]
            offsets = [(0, 0), *chunk_offsets, (0, 0)]
            row = {
                "input_ids": self.torch.tensor([prepared_ids], device=self.device),
                "attention_mask": self.torch.ones((1, len(prepared_ids)), dtype=self.torch.long, device=self.device),
            }
            with self.torch.inference_mode():
                probs_by_token = self.torch.softmax(self.aspect_model(**row).logits[0], dim=-1).cpu()
            active_indexes = [index for index, (start, end) in enumerate(offsets) if start < end and row["attention_mask"][0, index].item()]
            current = None

            def finish():
                if current is None:
                    return
                start, end, scores, first, last = current
                margin = min(first - active_indexes[0], active_indexes[-1] - last)
                candidates.append(WindowSpanCandidate(start, end, sum(scores) / len(scores), margin, window_index))

            for index in active_indexes:
                start, end = offsets[index]
                probabilities = probs_by_token[index]
                label_id = int(probabilities.argmax())
                label = self.aspect_model.config.id2label.get(label_id, str(label_id))
                confidence = float(probabilities[label_id])
                if label == "B-ASP":
                    finish()
                    current = [start, end, [confidence], index, index]
                elif label == "I-ASP" and current is not None:
                    current[1] = end
                    current[2].append(confidence)
                    current[4] = index
                else:
                    # An orphan I is dropped. It cannot establish a reliable exact boundary.
                    finish()
                    current = None
            finish()
            if first_token + content_capacity >= token_count:
                break
        return merge_window_candidates(text, candidates)

    def select_sentiment_context(self, review: str, aspect: str, start_char: int, end_char: int) -> tuple[str, int, int]:
        context, base_start, base_end = aspect_context_span(review, start_char, end_char, self.context_policy)
        tokenized = self.sentiment_tokenizer(context, add_special_tokens=False, return_offsets_mapping=True)
        offsets = tokenized["offset_mapping"]
        aspect_length = len(self.sentiment_tokenizer(aspect, add_special_tokens=False)["input_ids"])
        budget = self.max_length - self.sentiment_tokenizer.num_special_tokens_to_add(pair=True) - aspect_length
        if budget < 1:
            raise ReviewTooLongError("Aspect leaves no room for its review context")
        if len(offsets) <= budget:
            return context, base_start, base_end
        relative_start, relative_end = start_char - base_start, end_char - base_start
        covered = [index for index, (start, end) in enumerate(offsets) if start < relative_end and end > relative_start]
        if not covered:
            raise ValueError("Aspect has no visible tokens in selected sentiment context")
        if len(covered) > budget:
            raise ReviewTooLongError("Aspect is longer than the available sentiment context")
        first = min(max(0, covered[0] - (budget - len(covered)) // 2), len(offsets) - budget)
        if first + budget <= covered[-1]:
            first = covered[-1] - budget + 1
        window_start = base_start + offsets[first][0]
        window_end = base_start + offsets[first + budget - 1][1]
        return review[window_start:window_end], window_start, window_end

    def predict_sentiment(self, review: str, aspect: str, start_char: int | None = None, end_char: int | None = None) -> SentimentPrediction:
        context = self.select_sentiment_context(review, aspect, start_char, end_char)[0] if start_char is not None and end_char is not None else review
        encoded = self.sentiment_tokenizer(context, aspect, truncation="only_first", max_length=self.max_length, return_tensors="pt")
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with self.torch.inference_mode():
            probabilities = self.torch.softmax(self.sentiment_model(**encoded).logits[0], dim=-1).cpu()
        label_id = int(probabilities.argmax())
        label_name = self.sentiment_model.config.id2label[label_id].lower()
        label = Sentiment(label_name)
        return SentimentPrediction(label, float(probabilities[label_id]), {
            self.sentiment_model.config.id2label[i].lower(): float(probabilities[i])
            for i in range(len(probabilities))
        })
