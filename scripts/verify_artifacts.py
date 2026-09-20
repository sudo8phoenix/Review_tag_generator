"""Check the exact saved weights before allowing real model inference."""

from pathlib import Path

from review_tag_generator.artifacts import verify_checkpoint


root = Path(__file__).resolve().parents[1]
for task, checkpoint, manifest in (
    ("aspect", "models/aspect_extractor/distilbert_weighted_lr3e5/best", "audit/evidence/A2/aspect_training_manifest.json"),
    ("sentiment", "models/sentiment_classifier/distilbert/best", "audit/evidence/A3/sentiment_training_manifest.json"),
):
    print(f"{task}: {verify_checkpoint(root / checkpoint, root / manifest, task)}")
