# Automated E-Commerce Review Tag Generator
## Complete Build Plan, Dataset Strategy, ML Pipeline, Backend, Frontend, and Agent Task Brief

> **Project goal:** Build an e-commerce review analysis system that goes beyond overall positive/negative/neutral sentiment.  
> The system should identify individual product aspects, determine sentiment for each aspect, normalize similar aspect names, generate concise customer-friendly tags, aggregate them across many reviews, rank the most useful insights, and present them in a web application.

---

# 1. Core Problem

Traditional e-commerce review systems usually provide:

- Star ratings
- Overall positive / negative / neutral sentiment
- General review summaries

They often do **not** clearly answer:

- What exact product feature is being discussed?
- Is that specific feature being praised or criticized?
- Are “battery backup”, “battery duration”, and “battery life” actually the same aspect?
- Which product strengths or weaknesses are mentioned most often?

The proposed system solves this by creating **aspect-level review tags**.

### Example

**Input review**

> The camera is excellent and photos are sharp, but the battery barely lasts a day. The display is gorgeous.

**Intermediate output**

```json
[
  {
    "aspect": "camera",
    "normalized_aspect": "camera_quality",
    "sentiment": "positive",
    "confidence": 0.95
  },
  {
    "aspect": "battery",
    "normalized_aspect": "battery_life",
    "sentiment": "negative",
    "confidence": 0.93
  },
  {
    "aspect": "display",
    "normalized_aspect": "display_quality",
    "sentiment": "positive",
    "confidence": 0.91
  }
]
```

**Generated tags**

```text
Excellent Camera
Poor Battery Life
Excellent Display
```

For hundreds or thousands of reviews, the system aggregates results:

```text
Excellent Camera        421 mentions
Poor Battery Life       283 mentions
Great Display           251 mentions
Good Build Quality      194 mentions
Expensive Price          92 mentions
```

---

# 2. Recommended Initial Scope

Do not support every e-commerce product category at the beginning.

## Phase 1: Laptops / Consumer Electronics

Recommended aspect set:

```text
battery life
display
performance
processor
keyboard
trackpad
camera
speaker
storage
RAM
build quality
weight
design
price
value for money
heating
charging
ports
delivery
packaging
customer service
```

Once the pipeline is stable, expand into:

```text
Phones
Headphones
Cameras
Home appliances
Clothing
Cosmetics
Furniture
```

---

# 3. Dataset Strategy

Use different datasets for **training**, **benchmarking**, and **real-product demonstration**.

---

## 3.1 Primary Training Dataset: Laptop-ACOS

Recommended as the main supervised dataset.

It provides labels related to:

```text
Aspect
Aspect Category
Opinion
Sentiment
```

Conceptual example:

```text
Review sentence:
"The battery lasts forever."

aspect       = battery
category     = battery_life
opinion      = lasts forever
sentiment    = positive
```

Why it fits this project:

- E-commerce focused
- Laptop domain matches the recommended first scope
- Contains aspect-level sentiment information
- Useful for explicit and implicit product aspect analysis

Reference:
- https://github.com/NUSTM/ACOS

---

## 3.2 Benchmark Dataset: SemEval 2014 Laptop ABSA

Use SemEval laptop reviews for:

- Additional aspect extraction training
- Additional aspect-level sentiment training
- Benchmarking
- Comparing model performance

Useful because it is a classic Aspect-Based Sentiment Analysis benchmark.

Reference:
- https://www.aclweb.org/portal/content/semeval-2014-task-4-aspect-based-sentiment-analysis

---

## 3.3 Real-World Demo Dataset: Amazon Reviews 2023

Use a **small subset** for inference and web-app demonstration.

Recommended sample size:

```text
5,000–50,000 reviews
```

Do **not** attempt to process the entire dataset initially.

Useful fields:

```text
review_id
product_id
review_text
rating
helpful_votes
timestamp
category
product_name
brand
```

Important:

Amazon Reviews 2023 is primarily for:

```text
Inference
Product-level aggregation
UI demonstration
Tag ranking
Real-world testing
```

It does **not automatically provide aspect labels**, so it should not be treated as the main supervised aspect training dataset.

Reference:
- https://amazon-reviews-2023.github.io/main.html

---

## 3.4 Optional Advanced Dataset: E-ABSA20K

Use only after the first complete system is working.

Useful for:

- Long-form e-commerce reviews
- Reviews containing many aspects
- More complex aspect-sentiment extraction
- Future model comparison

This should be an **extension**, not a dependency of the MVP.

---

# 4. Standard Internal Dataset Format

Convert all datasets into a single common structure.

```json
{
  "review_id": "R123",
  "product_id": "P001",
  "product_category": "Laptop",
  "review_text": "Excellent screen but poor battery life.",
  "rating": 3,
  "annotations": [
    {
      "aspect": "screen",
      "normalized_aspect": "display_quality",
      "opinion": "Excellent",
      "sentiment": "positive"
    },
    {
      "aspect": "battery life",
      "normalized_aspect": "battery_life",
      "opinion": "poor",
      "sentiment": "negative"
    }
  ]
}
```

For model training, a flattened representation is also useful:

| Review | Aspect | Normalized Aspect | Sentiment |
|---|---|---|---|
| Excellent screen but poor battery life | screen | display_quality | positive |
| Excellent screen but poor battery life | battery life | battery_life | negative |

---

# 5. Final System Architecture

```text
                 E-COMMERCE REVIEWS
                         │
                         ▼
                Text Preprocessing
                         │
                         ▼
          ┌───────────────────────────┐
          │ MODEL 1                   │
          │ Aspect Extraction         │
          │ DistilBERT / BERT         │
          └─────────────┬─────────────┘
                        │
                        ▼
                Extracted Aspects
                        │
                        ▼
          ┌───────────────────────────┐
          │ MODEL 2                   │
          │ Aspect Sentiment          │
          │ DistilBERT / BERT         │
          └─────────────┬─────────────┘
                        │
                        ▼
               Aspect + Sentiment
                        │
                        ▼
          ┌───────────────────────────┐
          │ Aspect Normalization      │
          │ SentenceTransformer       │
          └─────────────┬─────────────┘
                        │
                        ▼
                Canonical Aspects
                        │
                        ▼
                  Tag Generation
                        │
                        ▼
                  Tag Aggregation
                        │
                        ▼
                  Tag Ranking
                        │
                        ▼
                    PostgreSQL
                        │
                        ▼
                     FastAPI
                        │
                        ▼
                React Web Frontend
```

---

# 6. Recommended Tech Stack

| Layer | Technology |
|---|---|
| Main language | Python 3.11 |
| Data processing | Pandas, NumPy |
| NLP preprocessing | spaCy, regex |
| Deep learning | PyTorch |
| Transformers | Hugging Face Transformers |
| Dataset handling | Hugging Face Datasets |
| Aspect extraction | DistilBERT / BERT |
| Aspect sentiment | DistilBERT / BERT |
| Aspect normalization | Sentence Transformers |
| Similarity | Cosine similarity / scikit-learn |
| Evaluation | scikit-learn, seqeval |
| Backend API | FastAPI |
| API schemas | Pydantic |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| DB migrations | Alembic |
| Frontend | React |
| Frontend language | TypeScript |
| Build tool | Vite |
| UI styling | Tailwind CSS |
| Charts | Recharts |
| HTTP client | Axios |
| Testing | pytest |
| API testing | Postman |
| Deployment | Docker / Docker Compose |
| Version control | Git + GitHub |

---

# 7. Python Packages

Suggested environment:

```text
torch
transformers
datasets
evaluate
accelerate
sentence-transformers
spacy
pandas
numpy
scikit-learn
seqeval
fastapi
uvicorn
pydantic
sqlalchemy
psycopg2-binary
alembic
pytest
```

---

# 8. ML Part 1 — Text Preprocessing

Use:

```text
Python
Pandas
spaCy
Regex
```

Tasks:

- Remove HTML tags
- Normalize whitespace
- Remove malformed characters
- Remove unnecessary URLs/emails if present
- Sentence segmentation
- Preserve punctuation
- Preserve negation
- Preserve product terminology
- Handle empty / extremely short reviews
- Remove exact duplicates

Avoid overly aggressive traditional preprocessing.

Do **not** blindly:

```text
remove all stopwords
remove "not"
stem every word
strip all punctuation
```

For transformer models, keep the language reasonably natural.

Example:

```text
"The camera isn't good"
```

must not become:

```text
camera good
```

---

# 9. ML Part 2 — Aspect Extraction

## Task

Input:

```text
"The camera is amazing but battery life is poor."
```

Output:

```text
camera
battery life
```

Treat this as a **token classification / sequence labeling** problem.

---

## BIO Labels

Example:

```text
The       O
camera    B-ASP
is        O
amazing   O
but       O
battery   B-ASP
life      I-ASP
is        O
poor      O
```

Labels:

```text
O
B-ASP
I-ASP
```

---

## Recommended Model

Primary:

```text
distilbert-base-uncased
```

Comparison model:

```text
bert-base-uncased
```

Why DistilBERT first:

- Smaller
- Faster
- Easier to train
- Lower GPU memory usage
- Still transformer-based
- Suitable for a university project

---

## Training Libraries

```text
PyTorch
Transformers
Datasets
seqeval
scikit-learn
```

Suggested starting configuration:

```text
epochs = 3–5
learning_rate = 2e-5
batch_size = 16 or 32
max_length = 128 or 256
optimizer = AdamW
early_stopping = enabled
```

Evaluation:

```text
Precision
Recall
F1-score
```

Main metric:

```text
F1-score
```

---

# 10. ML Part 3 — Aspect Sentiment Classification

Ordinary sentiment analysis gives one label for the whole review.

This system needs:

```text
aspect → sentiment
```

Example:

```text
"The camera is excellent but battery life is awful."
```

Desired result:

```text
camera       → positive
battery life → negative
```

---

## Model Input

For each detected aspect:

```text
Review:
"The camera is excellent but battery life is awful."

Aspect:
camera
```

Transformer-style input:

```text
[CLS]
The camera is excellent but battery life is awful.
[SEP]
camera
[SEP]
```

Output classes:

```text
positive
neutral
negative
```

---

## Model

Start with:

```text
distilbert-base-uncased
```

Compare later with:

```text
bert-base-uncased
```

Output example:

```json
{
  "positive": 0.94,
  "neutral": 0.02,
  "negative": 0.04
}
```

Evaluation:

```text
Accuracy
Precision
Recall
Macro F1
Confusion Matrix
```

Main metric:

```text
Macro F1
```

---

# 11. ML Part 4 — Aspect Normalization

This is one of the most important parts of the project.

Equivalent expressions:

```text
battery duration
battery backup
battery longevity
battery life
power duration
```

should map to:

```text
battery_life
```

---

## Recommended Model

Use:

```text
sentence-transformers/all-MiniLM-L6-v2
```

No initial fine-tuning required.

Process:

```text
raw aspect
    ↓
sentence embedding
    ↓
compare to canonical aspect embeddings
    ↓
cosine similarity
    ↓
best canonical aspect
```

Example:

```text
battery duration ↔ battery life = 0.86
```

A similarity threshold can be used, but it must be tuned experimentally.

Example starting point:

```text
0.70
```

Do not permanently assume the threshold is correct without validation.

---

# 12. Canonical Aspect Ontology

Example:

```python
ASPECTS = {
    "battery_life": [
        "battery",
        "battery life",
        "battery backup",
        "battery duration"
    ],

    "display_quality": [
        "display",
        "screen",
        "screen quality",
        "display quality"
    ],

    "performance": [
        "performance",
        "speed",
        "processing speed",
        "responsiveness"
    ],

    "build_quality": [
        "build",
        "build quality",
        "construction",
        "durability"
    ],

    "price_value": [
        "price",
        "cost",
        "value",
        "value for money"
    ]
}
```

---

# 13. ML Part 5 — Tag Generation

For the first version, **do not train another neural network**.

Use deterministic tag generation.

Input:

```text
normalized_aspect = battery_life
sentiment = negative
```

Output:

```text
Poor Battery Life
```

Input:

```text
camera_quality
positive
```

Output:

```text
Excellent Camera
```

---

## Template Example

```python
positive_templates = {
    "battery_life": "Great Battery Life",
    "camera_quality": "Excellent Camera",
    "display_quality": "Excellent Display",
    "performance": "Fast Performance"
}

negative_templates = {
    "battery_life": "Poor Battery Life",
    "camera_quality": "Poor Camera",
    "display_quality": "Poor Display",
    "performance": "Slow Performance"
}
```

---

# 14. Aggregation Across Reviews

Example:

For 1,000 product reviews:

```text
battery_life:

positive = 145
neutral  = 70
negative = 421
```

Total aspect mentions:

```text
636
```

Ratios:

```text
positive_ratio = 145 / 636
negative_ratio = 421 / 636
neutral_ratio  = 70 / 636
```

Result:

```text
Poor Battery Life
```

---

# 15. Suggested Aggregate Tag Rules

Starting rules:

```text
positive >= 80% → Excellent
positive >= 60% → Good

negative >= 70% → Poor
negative >= 50% → Weak

otherwise → Mixed
```

Examples:

```text
82% positive camera
→ Excellent Camera
```

```text
65% negative battery
→ Poor Battery Life
```

```text
54% positive display and 42% negative
→ Mixed Display Reviews
```

Tune these thresholds using validation and human judgement.

---

# 16. Tag Ranking

Ranking must consider more than raw frequency.

Suggested score:

```text
ranking_score =
log(1 + mention_count)
× average_model_confidence
× sentiment_strength
```

Where:

```text
sentiment_strength =
abs(positive_ratio - negative_ratio)
```

Optional:

```text
× review_helpfulness
```

---

# 17. Example Product Output

```text
PRODUCT: XYZ Laptop

TOP STRENGTHS

1. Excellent Display
   421 mentions
   86% positive

2. Fast Performance
   389 mentions
   81% positive

3. Good Build Quality
   276 mentions
   73% positive


TOP WEAKNESSES

1. Poor Battery Life
   312 mentions
   68% negative

2. Heating Issues
   204 mentions
   64% negative

3. Expensive
   151 mentions
   57% negative
```

---

# 18. Models That Must Actually Be Trained

## Model 1 — Aspect Extraction

```text
DistilBERT
Task: Token Classification
Labels: O / B-ASP / I-ASP
```

Train this model.

---

## Model 2 — Aspect Sentiment

```text
DistilBERT
Task: Sequence Classification
Labels: Positive / Neutral / Negative
```

Train this model.

---

## Model 3 — Aspect Normalization

```text
SentenceTransformer
all-MiniLM-L6-v2
```

Use pretrained initially.

No training required in MVP.

---

## Tag Generation

Use:

```text
Rule / template-based generation
```

No ML training required initially.

---

# 19. Recommended Experiment Design

Train / compare:

## Aspect Extraction

```text
Rule-based baseline
DistilBERT
BERT
```

Metrics:

```text
Precision
Recall
F1
```

Example reporting format:

| Model | Precision | Recall | F1 |
|---|---:|---:|---:|
| Rule-based | | | |
| DistilBERT | | | |
| BERT | | | |

Use actual experiment results.

---

## Aspect Sentiment

Compare:

```text
Logistic Regression / simple baseline
DistilBERT
BERT
```

Metrics:

| Model | Accuracy | Macro F1 |
|---|---:|---:|
| Logistic Regression | | |
| DistilBERT | | |
| BERT | | |

---

# 20. Normalization Evaluation

Create:

```text
100–300 manually validated aspect mappings
```

Example:

```text
battery backup → battery_life ✓
screen → display_quality ✓
battery duration → battery_life ✓
cost → price_value ✓
camera → camera_quality ✓
```

Report:

```text
Normalization Accuracy
```

---

# 21. End-to-End Evaluation

Example:

Input:

```text
"The screen is fantastic but battery doesn't last long."
```

Expected:

```text
Excellent Display
Poor Battery Life
```

Generated:

```text
Excellent Display
Poor Battery Life
```

Evaluate:

```text
Tag Precision
Tag Recall
Tag F1
```

This becomes the main overall system metric.

---

# 22. Database Design

Use PostgreSQL.

---

## Products Table

```text
products

id
product_id
name
category
brand
```

---

## Reviews Table

```text
reviews

id
review_id
product_id
review_text
rating
helpful_votes
timestamp
```

---

## Aspect Mentions Table

```text
aspect_mentions

id
review_id
raw_aspect
normalized_aspect
sentiment
aspect_confidence
sentiment_confidence
opinion
```

---

## Product Tags Table

```text
product_tags

id
product_id
normalized_aspect
tag
positive_count
negative_count
neutral_count
mention_count
score
rank
```

---

# 23. Backend Architecture

Recommended:

```text
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
Alembic
```

---

# 24. Backend API Endpoints

## Analyze One Review

```http
POST /api/reviews/analyze
```

Input:

```json
{
  "review": "Camera is amazing but battery is poor."
}
```

Output:

```json
{
  "aspects": [
    {
      "aspect": "camera",
      "normalized_aspect": "camera_quality",
      "sentiment": "positive",
      "tag": "Excellent Camera"
    },
    {
      "aspect": "battery",
      "normalized_aspect": "battery_life",
      "sentiment": "negative",
      "tag": "Poor Battery Life"
    }
  ]
}
```

---

## Upload Product Reviews

```http
POST /api/products/{product_id}/reviews
```

Support:

```text
CSV
JSON
```

---

## Generate Product Tags

```http
POST /api/products/{product_id}/generate-tags
```

---

## Retrieve Product Tags

```http
GET /api/products/{product_id}/tags
```

---

## Product Insights

```http
GET /api/products/{product_id}/insights
```

Return:

```text
top positive aspects
top negative aspects
sentiment distributions
mention counts
representative reviews
```

---

# 25. Central ML Inference Pipeline

Create one reusable function:

```python
analyze_review(review)
```

Suggested structure:

```python
def analyze_review(review):

    clean_text = preprocess(review)

    aspects = aspect_model.extract(clean_text)

    results = []

    for aspect in aspects:

        sentiment = sentiment_model.predict(
            clean_text,
            aspect
        )

        normalized = normalize_aspect(aspect)

        tag = generate_tag(
            normalized,
            sentiment
        )

        results.append({
            "aspect": aspect,
            "normalized_aspect": normalized,
            "sentiment": sentiment,
            "tag": tag
        })

    return results
```

The FastAPI backend should call this pipeline.

---

# 26. Recommended Repository Structure

```text
review-tag-generator/
│
├── data/
│   ├── raw/
│   │   ├── acos/
│   │   ├── semeval/
│   │   └── amazon/
│   │
│   ├── processed/
│   └── annotations/
│
├── ml/
│   ├── preprocessing/
│   │   ├── clean.py
│   │   └── dataset_builder.py
│   │
│   ├── aspect_extraction/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── inference.py
│   │
│   ├── sentiment/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── inference.py
│   │
│   ├── normalization/
│   │   ├── ontology.json
│   │   └── normalize.py
│   │
│   ├── tagging/
│   │   ├── generator.py
│   │   └── ranking.py
│   │
│   └── pipeline.py
│
├── models/
│   ├── aspect_extractor/
│   └── sentiment_classifier/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── database/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── components/
│   ├── pages/
│   └── package.json
│
├── notebooks/
│   ├── dataset_analysis.ipynb
│   └── experiments.ipynb
│
├── tests/
│
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

# 27. Baseline System

Implement an ordinary whole-review sentiment model.

Input:

```text
"The camera is excellent but battery is awful."
```

Baseline output might be:

```text
Neutral
```

Proposed system:

```text
Excellent Camera
Poor Battery Life
```

This makes the benefit of aspect-based analysis visually obvious.

---

# 28. Full TODO List

## Phase 1 — Project Setup

- [ ] Create GitHub repository
- [ ] Create Python virtual environment
- [ ] Create folder structure
- [ ] Install PyTorch
- [ ] Install Transformers
- [ ] Install Datasets
- [ ] Install spaCy
- [ ] Install Sentence Transformers
- [ ] Install FastAPI
- [ ] Create React frontend
- [ ] Configure `.gitignore`
- [ ] Create README

---

## Phase 2 — Dataset

- [ ] Download Laptop-ACOS
- [ ] Download SemEval Laptop dataset
- [ ] Inspect annotation format
- [ ] Convert datasets into common JSON format
- [ ] Remove duplicates
- [ ] Analyse sentiment distribution
- [ ] Analyse aspect frequencies
- [ ] Create train / validation / test splits
- [ ] Download a small Amazon Reviews sample
- [ ] Store product IDs and review text

---

## Phase 3 — Baseline

- [ ] Implement whole-review sentiment baseline
- [ ] Implement basic noun/aspect extraction using spaCy
- [ ] Save baseline metrics
- [ ] Prepare comparison table

---

## Phase 4 — Aspect Extraction

- [ ] Convert aspect annotations to BIO labels
- [ ] Tokenize with DistilBERT tokenizer
- [ ] Align BIO labels with subword tokens
- [ ] Create token-classification model
- [ ] Train model
- [ ] Validate model
- [ ] Save best checkpoint
- [ ] Calculate Precision / Recall / F1
- [ ] Implement inference function

---

## Phase 5 — Aspect Sentiment

- [ ] Create review + aspect input pairs
- [ ] Encode positive / neutral / negative labels
- [ ] Create DistilBERT classifier
- [ ] Train classifier
- [ ] Validate model
- [ ] Save best checkpoint
- [ ] Generate confusion matrix
- [ ] Calculate Macro F1
- [ ] Implement inference

---

## Phase 6 — Aspect Normalization

- [ ] Define canonical aspect ontology
- [ ] Add known synonyms
- [ ] Load MiniLM SentenceTransformer
- [ ] Encode canonical aspects
- [ ] Calculate cosine similarity
- [ ] Tune similarity threshold
- [ ] Map synonyms to canonical aspects
- [ ] Handle unknown aspects
- [ ] Evaluate normalization

---

## Phase 7 — Tag Generation

- [ ] Define positive templates
- [ ] Define negative templates
- [ ] Define neutral/mixed templates
- [ ] Convert aspect + sentiment into readable tags
- [ ] Add tag unit tests

---

## Phase 8 — Aggregation

- [ ] Group aspect mentions by product
- [ ] Count positive mentions
- [ ] Count negative mentions
- [ ] Count neutral mentions
- [ ] Calculate sentiment ratios
- [ ] Set minimum mention threshold
- [ ] Determine aggregate sentiment
- [ ] Generate product-level tags

---

## Phase 9 — Ranking

- [ ] Implement mention-frequency score
- [ ] Add model confidence
- [ ] Add sentiment strength
- [ ] Add optional review helpfulness
- [ ] Sort tags
- [ ] Return Top-K tags
- [ ] Separate strengths and weaknesses

---

## Phase 10 — Backend

- [ ] Set up FastAPI
- [ ] Configure PostgreSQL
- [ ] Configure SQLAlchemy
- [ ] Configure Alembic
- [ ] Create Product model
- [ ] Create Review model
- [ ] Create AspectMention model
- [ ] Create ProductTag model
- [ ] Create review-analysis endpoint
- [ ] Create batch-upload endpoint
- [ ] Create tags endpoint
- [ ] Create product-insights endpoint
- [ ] Add validation
- [ ] Add exception handling
- [ ] Add Swagger documentation

---

## Phase 11 — Frontend

- [ ] Create React/Vite app
- [ ] Product dashboard
- [ ] Review analyzer
- [ ] Tag cards
- [ ] Sentiment badges
- [ ] Strengths section
- [ ] Weaknesses section
- [ ] Aspect sentiment charts
- [ ] Representative review panel
- [ ] CSV upload
- [ ] Connect frontend to FastAPI
- [ ] Add responsive design

---

## Phase 12 — Testing

- [ ] ML unit tests
- [ ] Normalization tests
- [ ] Backend API tests
- [ ] Frontend API tests
- [ ] End-to-end tests
- [ ] Test unseen reviews
- [ ] Test multiple aspects in one review
- [ ] Test negation
- [ ] Test no-aspect reviews
- [ ] Test contradictory sentiment
- [ ] Test duplicate aspects

---

## Phase 13 — Final Evaluation

- [ ] Aspect extraction F1
- [ ] Sentiment Macro F1
- [ ] Normalization accuracy
- [ ] End-to-end Tag F1
- [ ] Baseline comparison
- [ ] Error analysis
- [ ] Product demo screenshots
- [ ] Final result tables
- [ ] Prepare presentation demo

---

# 29. Minimum Successful Version

The minimum complete system should be:

```text
Laptop-ACOS
        ↓
DistilBERT Aspect Extractor
        ↓
DistilBERT Aspect Sentiment Model
        ↓
MiniLM Normalization
        ↓
Rule-Based Tag Generator
        ↓
Amazon Review Sample
        ↓
Aggregation + Ranking
        ↓
FastAPI
        ↓
React UI
```

---

# 30. Development Priority

Recommended order:

```text
1. Download and understand Laptop-ACOS
        ↓
2. Build preprocessing
        ↓
3. Train aspect extraction model
        ↓
4. Train aspect sentiment model
        ↓
5. Test one review end-to-end
        ↓
6. Implement aspect normalization
        ↓
7. Generate customer-friendly tags
        ↓
8. Process real review dataset
        ↓
9. Add product aggregation
        ↓
10. Add ranking
        ↓
11. Build FastAPI
        ↓
12. Build React UI
        ↓
13. Evaluate and document
```

Do **not** start with the website.

The ML pipeline is the core of the project.

---

# 31. What Not to Build Initially

Avoid unnecessary complexity:

```text
External LLM APIs for every task
Training a giant generative LLM
Kafka
Kubernetes
Microservices
Live Amazon scraping
Multiple databases
Mobile app
50 product categories
Complex cloud architecture
```

Focus on:

```text
Aspect Extraction
+
Aspect Sentiment
+
Aspect Normalization
+
Tag Generation
+
Aggregation
+
Ranking
```

---

# 32. Advanced Future Extensions

After the complete system works:

## Generative ABSA

Compare the pipeline with:

```text
FLAN-T5 / T5 / small instruction model
```

Potential output:

```json
{
  "aspect": "battery",
  "category": "battery_life",
  "opinion": "doesn't last",
  "sentiment": "negative"
}
```

---

## Other Future Improvements

- Implicit aspect detection
- Opinion term extraction
- Multilingual reviews
- Product category-specific ontologies
- LLM-based tag wording
- Review summarization
- Review recommendation / helpfulness prediction
- Live product comparison
- Trend analysis over time
- Explainability
- Keyword highlighting
- Aspect co-occurrence analysis

---

# 33. Website / Frontend Ideas

The frontend should look like an **e-commerce product insight dashboard**, not like a generic ML demo.

The user should immediately understand:

```text
What buyers like
What buyers dislike
How often each issue appears
What actual reviews support the tag
```

---

# 34. Page 1 — Landing / Search Page

### Purpose

Allow the user to select or search for a product.

Suggested layout:

```text
------------------------------------------------------
      ReviewLens / AspectIQ / ReviewTag AI

      Understand thousands of reviews instantly.

      [ Search product / Product ID          ] [Search]

      Popular demo products
      [Laptop A] [Laptop B] [Laptop C]
------------------------------------------------------
```

Include:

- Project title
- One-line explanation
- Product search
- Demo products
- “Analyze a Review” shortcut

---

# 35. Page 2 — Product Insight Dashboard

This should be the main page.

## Header

```text
XYZ Laptop Pro 14

★★★★☆ 4.3
8,421 reviews analyzed
```

Optional:

```text
Laptop / Electronics
```

---

## Top Customer Tags

Display large clickable chips/cards:

```text
[ Excellent Display  86% ]
[ Fast Performance   81% ]
[ Good Build Quality 73% ]

[ Poor Battery Life  68% ]
[ Heating Issues     61% ]
[ Expensive          54% ]
```

Visual idea:

```text
Positive insights
green-style visual state

Negative insights
red-style visual state

Mixed insights
neutral state
```

Do not rely only on color; include icons/text labels too.

---

# 36. Strengths and Weaknesses Panels

Two-column layout:

```text
┌─────────────────────┐  ┌─────────────────────┐
│ What Customers Love │  │ What Customers Dislike
│                     │  │
│ Excellent Display   │  │ Poor Battery Life
│ 421 mentions        │  │ 312 mentions
│ 86% positive        │  │ 68% negative
│                     │  │
│ Fast Performance    │  │ Heating Issues
│ 389 mentions        │  │ 204 mentions
│ 81% positive        │  │ 64% negative
└─────────────────────┘  └─────────────────────┘
```

This should be the strongest visual feature of the product page.

---

# 37. Aspect Explorer

Show all normalized aspects.

Example:

| Aspect | Mentions | Positive | Neutral | Negative |
|---|---:|---:|---:|---:|
| Display | 421 | 86% | 6% | 8% |
| Battery | 312 | 22% | 10% | 68% |
| Performance | 389 | 81% | 9% | 10% |
| Build Quality | 276 | 73% | 12% | 15% |

Allow:

```text
Sort by mentions
Sort by positive
Sort by negative
Search aspects
```

---

# 38. Aspect Detail Drawer / Modal

When the user clicks:

```text
Poor Battery Life
```

open:

```text
BATTERY LIFE

312 total mentions

Positive   22%
Neutral    10%
Negative   68%

Most common expressions:

battery
battery life
battery backup
battery duration

Representative reviews:

"Battery barely lasts four hours."

"Battery backup is terrible."

"I expected much better battery performance."
```

Also display:

```text
Normalized to:
battery_life
```

This visually demonstrates the aspect-normalization part of the ML pipeline.

---

# 39. Review Analyzer Page

This should be your best live ML demonstration.

Layout:

```text
Analyze a Review

[ The camera is amazing but the battery is terrible. ]

                    [ Analyze ]
```

Results:

```text
Detected Aspect          Sentiment      Confidence

Camera                   Positive       95%
Normalized: camera_quality
Tag: Excellent Camera

Battery                  Negative       93%
Normalized: battery_life
Tag: Poor Battery Life
```

---

# 40. Highlighted Review View

A particularly strong UI idea:

Show the sentence with ML-highlighted spans.

Example:

```text
The [camera] is amazing but the [battery life] is terrible.
     ↑ positive                    ↑ negative
```

This makes aspect extraction instantly understandable during a presentation.

---

# 41. Batch Upload / Admin Page

Allow:

```text
Upload CSV / JSON
```

After processing:

```text
PROCESSING COMPLETE

10,000 reviews uploaded
9,871 processed successfully
129 skipped

42 raw aspects found
16 normalized aspects
11 final ranked tags
```

Include progress states:

```text
Uploading
Preprocessing
Extracting aspects
Classifying sentiment
Normalizing aspects
Generating tags
Complete
```

This provides a professional pipeline feel.

---

# 42. Model Performance Page

Useful for academic evaluation.

Display:

## Aspect Extraction

```text
Precision
Recall
F1
```

## Aspect Sentiment

```text
Accuracy
Macro F1
```

## Normalization

```text
Accuracy
```

## End-to-End Tags

```text
Precision
Recall
F1
```

Add charts comparing:

```text
Rule-based baseline
DistilBERT
BERT
```

This page is extremely useful during project reviews.

---

# 43. Baseline vs Proposed System Demo

Create an interactive comparison.

Input:

```text
"The camera is excellent but the battery life is awful."
```

### Existing / Baseline System

```text
Overall sentiment:
Neutral
```

### Proposed System

```text
Camera → Positive → Excellent Camera
Battery → Negative → Poor Battery Life
```

This directly demonstrates why the project exists.

---

# 44. Product Comparison Page — Optional

Future feature:

```text
Compare Laptop A vs Laptop B
```

Example:

| Aspect | Laptop A | Laptop B |
|---|---|---|
| Display | Excellent | Good |
| Battery | Poor | Excellent |
| Performance | Excellent | Good |
| Heating | Weak | Good |
| Value | Good | Excellent |

This can make the final project feel much closer to a real e-commerce product.

---

# 45. Trends Page — Optional

If timestamps exist:

```text
Battery sentiment over time
```

Example:

```text
Jan → 61% negative
Feb → 58% negative
Mar → 44% negative
```

This could reveal product improvements or emerging issues.

---

# 46. Recommended Website Navigation

```text
Dashboard
Products
Analyze Review
Upload Dataset
Model Metrics
About Project
```

Optional later:

```text
Compare Products
Trends
```

---

# 47. Recommended Visual Style

The website should feel like a mix of:

```text
Amazon product information
+
modern analytics dashboard
+
AI insight tool
```

Recommended visual direction:

- Clean white / near-white background
- Dark text
- Purple or blue primary accent
- Soft cards
- Rounded tag chips
- Strong spacing
- Clear positive / negative / neutral states
- Minimal gradients
- Modern sans-serif font
- Responsive layout

Since the project presentation already uses a purple visual identity, the website can reuse that accent to make the project feel consistent.

---

# 48. Suggested Website Components

Reusable React components:

```text
ProductHeader
SearchBar
InsightTag
AspectCard
AspectTable
SentimentBar
SentimentDonut
ReviewHighlight
ReviewCard
AspectDetailDrawer
UploadBox
ProcessingProgress
MetricCard
ModelComparisonChart
Navbar
Sidebar
```

---

# 49. Suggested Dashboard Layout

```text
┌─────────────────────────────────────────────────────────────┐
│ Navbar                                                      │
├─────────────────────────────────────────────────────────────┤
│ Product Name                 Rating      Reviews Analyzed    │
├─────────────────────────────────────────────────────────────┤
│ Top Customer Insights                                      │
│ [Excellent Display] [Fast Performance] [Poor Battery Life] │
├─────────────────────────────┬───────────────────────────────┤
│ What Customers Love         │ What Customers Dislike        │
│                             │                               │
│ Display                     │ Battery                       │
│ Performance                 │ Heating                       │
│ Build Quality               │ Price                         │
├─────────────────────────────┴───────────────────────────────┤
│ Aspect Sentiment Distribution                               │
│ [chart]                                                     │
├─────────────────────────────────────────────────────────────┤
│ Representative Reviews                                     │
│ Review 1                                                   │
│ Review 2                                                   │
│ Review 3                                                   │
└─────────────────────────────────────────────────────────────┘
```

---

# 50. Best Features for the Final Demo

If time is limited, prioritize these:

1. Product insight dashboard
2. Top strengths and weaknesses
3. Clickable aspect detail panel
4. Review analyzer with highlighted aspect spans
5. Baseline vs proposed-system comparison
6. Model metrics page
7. Dataset upload

These features make the ML work visible instead of hiding everything behind an API.

---

# 51. Agent Task Brief

Give the following instruction to a coding agent:

> Build an Automated E-Commerce Review Tag Generator using Aspect-Based Sentiment Analysis.
>
> The system must process product reviews and return normalized human-readable product tags.
>
> Implement the project as a modular pipeline:
>
> 1. Build a preprocessing pipeline for e-commerce review text.
> 2. Train a DistilBERT token-classification model for aspect term extraction using Laptop-ACOS and/or SemEval laptop ABSA data.
> 3. Train a DistilBERT sequence-classification model for aspect-level sentiment classification with positive, negative and neutral labels.
> 4. Implement aspect normalization using `sentence-transformers/all-MiniLM-L6-v2` and cosine similarity against a canonical aspect ontology.
> 5. Implement deterministic human-readable tag generation from normalized aspect + sentiment.
> 6. Aggregate aspect sentiments across all reviews belonging to a product.
> 7. Rank tags using mention frequency, model confidence and sentiment strength.
> 8. Store products, reviews, aspect mentions and generated product tags in PostgreSQL.
> 9. Create a FastAPI REST backend exposing review analysis, product review ingestion, product tag generation and product insights.
> 10. Create a React + TypeScript frontend displaying top strengths, weaknesses, tags, sentiment distribution and representative customer reviews.
> 11. Provide evaluation scripts for aspect extraction Precision/Recall/F1, sentiment Macro-F1, normalization accuracy and end-to-end Tag F1.
> 12. Keep ML training, inference, backend and frontend separated into clean modules.
> 13. Add tests and Docker configuration.
> 14. Do not use external LLM APIs for the main pipeline.
> 15. Save trained models locally and expose one reusable `analyze_review()` inference pipeline.
> 16. Do not begin the frontend until the end-to-end ML inference pipeline works.
> 17. After each milestone, add tests and documentation for how to run that component.

---

# 52. Suggested Development Milestones

## Milestone 1

```text
Dataset downloaded
Dataset converted
Dataset statistics generated
```

## Milestone 2

```text
Aspect extraction model trained
F1 calculated
Inference working
```

## Milestone 3

```text
Aspect sentiment classifier trained
Macro F1 calculated
Inference working
```

## Milestone 4

```text
Normalization working
Tag generation working
```

## Milestone 5

```text
End-to-end analyze_review() working
```

Example:

```text
Input:
"Amazing display but terrible battery."

Output:
Excellent Display
Poor Battery Life
```

## Milestone 6

```text
Thousands of reviews processed
Product-level aggregation working
Ranking working
```

## Milestone 7

```text
FastAPI completed
PostgreSQL connected
```

## Milestone 8

```text
React dashboard completed
```

## Milestone 9

```text
Evaluation
Error analysis
Final report
Final presentation demo
```

---

# 53. Final Recommended Project Definition

## Machine Learning

```text
Model 1:
DistilBERT
Aspect Term Extraction
BIO Token Classification

Model 2:
DistilBERT
Aspect Sentiment Classification
Positive / Neutral / Negative

Model 3:
SentenceTransformer
all-MiniLM-L6-v2
Pretrained aspect normalization model
```

---

## Algorithms

```text
Text preprocessing
Canonical aspect mapping
Tag templates
Review aggregation
Tag scoring
Tag ranking
```

---

## Backend

```text
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
Alembic
```

---

## Frontend

```text
React
TypeScript
Vite
Tailwind CSS
Recharts
Axios
```

---

## Engineering

```text
GitHub
Docker
Docker Compose
pytest
Postman
```

---

# 54. Final Goal

The completed project should allow a user to:

```text
Select a product
      ↓
See thousands of reviews analyzed
      ↓
View top strengths and weaknesses
      ↓
Inspect individual aspects
      ↓
See supporting reviews
      ↓
Analyze a new review live
```

The core academic contribution is not simply sentiment analysis.

It is:

```text
Aspect Extraction
        +
Aspect-Level Sentiment
        +
Aspect Normalization
        +
Human-Readable Tag Generation
        +
Product-Level Aggregation
        +
Tag Ranking
```

That combination is what should remain central throughout the implementation.
