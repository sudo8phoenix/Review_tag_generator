FROM python:3.11.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the repository's resolved Python dependency set. Model artifacts are
# copied separately so Docker can reuse this layer when checkpoints change.
COPY requirements.lock requirements-inference.txt ./
RUN python -m pip install --no-cache-dir -r requirements.lock -r requirements-inference.txt

COPY pyproject.toml README.md ./
COPY src ./src
COPY backend ./backend
COPY scripts/verify_artifacts.py ./scripts/verify_artifacts.py
COPY models ./models
COPY audit/evidence ./audit/evidence
RUN python -m pip install --no-cache-dir --no-deps . \
    && PYTHONPATH=src python scripts/verify_artifacts.py

EXPOSE 8000
