import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from review_tag_generator import Review, ReviewAnalyzer

review = Review("demo-1", "demo-product", "Amazing display but terrible battery.")
print(json.dumps(ReviewAnalyzer().analyze(review), indent=2))
