#!/bin/sh
set -eu
# Render supplies a standard PostgreSQL URL; SQLAlchemy needs the psycopg driver.
if [ -n "${DATABASE_URL:-}" ]; then
  case "$DATABASE_URL" in
    postgres://*) DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgres://}" ;;
    postgresql://*) DATABASE_URL="postgresql+psycopg://${DATABASE_URL#postgresql://}" ;;
  esac
  export DATABASE_URL
  python -m alembic -c backend/alembic.ini upgrade head
fi
exec python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
