FROM python:3.11.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the repository's resolved Python dependency set. Model artifacts are
# copied separately so Docker can reuse this layer when checkpoints change.
COPY requirements.lock requirements-inference.txt ./
# Install CPU-only PyTorch first so the pinned Linux build does not pull CUDA.
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.14.0
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

# Keep runtime model discovery rooted in the bundled source and checkpoints.
ENV PYTHONPATH=/app/src
