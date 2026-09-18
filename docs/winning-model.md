# Winning model record

The current gates supplied by the training run are recorded here as the release candidate metrics:

| Gate | Task | Metric | Result | Status |
|---|---|---:|---:|---|
| A2 | DistilBERT aspect extraction | Exact Span F1 | 0.706 | passed |
| A3 | DistilBERT aspect sentiment | Macro F1 | 0.750 | passed |

The winning run was produced in Kaggle. The checkpoint and processed split hashes are recorded below, and the checkpoint files have been transferred locally with matching directory hashes. Local model loading still requires the optional inference dependencies.

```json
{
  "model_name": "distilbert-base-uncased",
  "seed": 42,
  "aspect_checkpoint": {"path": "/kaggle/working/review_tag_generator/models/aspect_extractor/distilbert_weighted_lr3e5/best", "sha256": "43912feea208644795785b7b54a001b60be244165cf6298eb42cfa5a1bb49c3d"},
  "sentiment_checkpoint": {"path": "/kaggle/working/review_tag_generator/models/sentiment_classifier/distilbert/best", "sha256": "d4130c282e9da91145b3e496ea9ca47aebab95ae209734cc4bca7ff18234851d"},
  "dataset_hashes": {"A2_train": "d2e009403d85fadcd28afebef69c33d39bb0c0b9f5258435f80629185e0a7cf4", "A2_validation": "6b3ca2e0a2a91a5d4bbd81edebdb814d0fccc9321c482e7c0b141b0a2e01259d", "A2_test": "2e1235eaa2cac125d5d69509a2803d338a38065063b79104594f0f4d3e7ec963", "A3_train": "ebcbb21435c4039155a07a7618269e020bf1e38b7da2c0ed8f0297baf2583eca", "A3_validation": "2d36c1faec0b5fbd2a5f6ffcb78a6d812ff8a3858a15318b42d7f062f4a664d6", "A3_test": "69f3b25ae7fe60b83f155c9b0dc513c985c2dad9e427fc8ffaad0327e90fc0b3"},
  "configuration": {"max_length": 256, "aspect_learning_rate": 0.00003, "aspect_epochs": 8, "sentiment_learning_rate": 0.00002, "sentiment_epochs": 4},
  "metrics": {"A2_exact_span_f1": 0.706, "A3_macro_f1": 0.750},
  "error_samples": "audit/evidence/error-samples.jsonl"
}
```

Do not commit checkpoints, raw datasets, credentials, or generated caches. Keep the model files in private storage and use the recorded hashes to verify any transfer.
