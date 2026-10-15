"""Bounded CSV, JSON, Amazon JSONL and line-oriented import validation."""
import csv
import io
import json
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000


def validate_rows(values):
    if len(values) > MAX_ROWS:
        raise ValueError(f'At most {MAX_ROWS} rows may be imported at once')
    rows, errors = [], []
    for number, value in enumerate(values, 1):
        if isinstance(value, dict):
            value = value.get('review_text', value.get('text', value.get('reviewText')))
        if not isinstance(value, str) or not value.strip() or len(value) > 10000:
            errors.append({'row': number, 'error': 'review_text must contain 1–10000 characters'})
        else:
            rows.append((number, value))
    if not values:
        raise ValueError('No review rows found')
    return rows, errors


def parse_import(filename, content):
    if len(content.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Import exceeds 10 MiB')
    content = content.lstrip('\ufeff')
    extension = Path(filename).suffix.lower()
    if extension == '.txt':
        values = content.splitlines()
    elif extension == '.csv':
        reader = csv.DictReader(io.StringIO(content), strict=True)
        if not reader.fieldnames or not {'review_text', 'text', 'reviewText'}.intersection(reader.fieldnames):
            raise ValueError('CSV needs a review_text, text, or reviewText header')
        values = list(reader)
    elif extension == '.json':
        values = json.loads(content)
        if isinstance(values, dict):
            values = values.get('reviews')
        if not isinstance(values, list):
            raise ValueError('JSON must be an array or an object containing a reviews array')
    elif extension in ('.jsonl', '.ndjson'):
        values, errors = [], []
        for number, line in enumerate(content.splitlines(), 1):
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError:
                values.append(None)
        # Bad lines retain their original ordinal for complete error reporting.
    else:
        raise ValueError('Supported formats: .txt, .csv, .json, .jsonl, .ndjson')
    return validate_rows(values)
