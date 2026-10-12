"""Local faculty demo API. SQLite storage; trained inference by default."""
from contextlib import asynccontextmanager
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from review_tag_generator import Review, ReviewAnalyzer
from review_tag_generator.aggregation import SavedReviewAnalysis, aggregate_saved_analyses
from review_tag_generator.schemas import Sentiment, TagResult

ROOT = Path(__file__).resolve().parents[2]
DATABASE = Path(os.environ.get("DEMO_DATABASE", ROOT / ".demo/reviews.sqlite3"))
inference_lock = Lock()


def connect():
    return sqlite3.connect(DATABASE)


class ProductInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class ReviewsInput(BaseModel):
    reviews: list[str] = Field(min_length=1, max_length=100)

    @field_validator("reviews")
    @classmethod
    def valid_reviews(cls, values):
        if any(not text.strip() or len(text) > 10000 for text in values):
            raise ValueError("Each review must contain 1–10000 characters")
        return values


def require_product(product_id):
    with connect() as db:
        row = db.execute("SELECT id, name FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Product not found")
    return {"id": row[0], "name": row[1]}


def save_reviews(product_id, texts):
    require_product(product_id)
    # Finish inference before committing so a failed batch leaves no partial import.
    with inference_lock:
        results = [app.state.analyzer.analyze(Review(str(uuid4()), product_id, text)) for text in texts]
    with connect() as db:
        for result in results:
            db.execute("INSERT INTO reviews VALUES (?, ?, ?)", (result["review"]["review_id"], product_id, json.dumps(result)))
    return results


@asynccontextmanager
async def lifespan(application):
    backend = os.environ.get("DEMO_MODEL_BACKEND", "transformer")
    if backend not in ("transformer", "heuristic"):
        raise RuntimeError("DEMO_MODEL_BACKEND must be transformer or heuristic")
    application.state.analyzer = ReviewAnalyzer(use_transformer=backend == "transformer")
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, product_id TEXT NOT NULL, analysis TEXT NOT NULL)")
        fresh = not db.execute("SELECT 1 FROM products LIMIT 1").fetchone()
        if fresh:
            db.execute("INSERT INTO products VALUES ('demo-laptop', 'Demo laptop')")
    if fresh:
        save_reviews("demo-laptop", [
            "Amazing display but terrible battery.",
            "The keyboard is comfortable and the performance is excellent.",
            "The screen is bright but the speakers are poor.",
        ])
    yield


app = FastAPI(title="Review Tag Generator — Local Demo", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "backend": app.state.analyzer.backend, "storage": "local SQLite"}


@app.get("/api/demo/products")
def products():
    with connect() as db:
        return [{"id": row[0], "name": row[1], "review_count": row[2]} for row in db.execute(
            "SELECT p.id, p.name, COUNT(r.id) FROM products p LEFT JOIN reviews r ON r.product_id=p.id GROUP BY p.id ORDER BY p.rowid")]


@app.post("/api/demo/products", status_code=201)
def create_product(body: ProductInput):
    product = {"id": str(uuid4()), "name": body.name}
    with connect() as db:
        db.execute("INSERT INTO products VALUES (?, ?)", (product["id"], product["name"]))
    return product


@app.get("/api/demo/products/{product_id}")
def detail(product_id: str):
    product = require_product(product_id)
    with connect() as db:
        analyses = [json.loads(row[0]) for row in db.execute("SELECT analysis FROM reviews WHERE product_id=? ORDER BY rowid DESC", (product_id,))]
    saved = [SavedReviewAnalysis(Review(**item["review"]), [TagResult(**{**tag, "sentiment": Sentiment(tag["sentiment"])}) for tag in item["tags"]]) for item in analyses]
    return {"product": product, "reviews": analyses, "insights": asdict(aggregate_saved_analyses(product_id, saved)), "backend": app.state.analyzer.backend}


@app.post("/api/demo/products/{product_id}/reviews", status_code=201)
def submit(product_id: str, body: ReviewsInput):
    try:
        return {"analyses": save_reviews(product_id, body.reviews)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
