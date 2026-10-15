"""Measure local sequential preview completion; remove the temporary product afterward."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = (
    'The display is bright and clear.',
    'The battery drains too quickly.',
    'The keyboard is comfortable for typing.',
    'The speakers sound weak.',
    'This laptop has excellent performance.',
    'The trackpad feels smooth.',
    'The storage capacity is good for my projects.',
    'The screen is excellent but battery life is poor.',
    'The charger gets hot during use.',
    'The laptop is lightweight and easy to carry.',
)


def request(base, path, body=None, method=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(base + path, data=data, method=method,
        headers={'Content-Type': 'application/json', 'User-Agent': 'ReviewTagGeneratorBenchmark/0.1'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def fingerprint():
    digest = hashlib.sha256()
    for folder in ('src', 'backend'):
        for path in sorted((ROOT / folder).rglob('*.py')):
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8011')
    parser.add_argument('--samples', type=int, default=10)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        parser.error('This smoke benchmark only mutates a local app.')
    if not 3 <= args.samples <= 100:
        parser.error('--samples must be between 3 and 100')
    base = args.base_url.rstrip('/')
    health = request(base, '/api/ready')
    product = request(base, '/api/demo/products', {'name': 'Temporary latency smoke measurement'})
    timings = []
    try:
        for index in range(args.samples + 1):
            text = REVIEWS[index % len(REVIEWS)]
            started = time.perf_counter()
            queued = request(base, f'/api/demo/products/{product["id"]}/preview', {'reviews': [text]})
            preview_id = queued['preview_ids'][0]
            deadline = started + 60
            while True:
                preview = request(base, f'/api/demo/previews/{preview_id}')
                if preview['status'] == 'completed':
                    break
                if preview['status'] == 'failed' or time.perf_counter() >= deadline:
                    raise RuntimeError('Preview failed or exceeded the benchmark deadline')
                time.sleep(.05)
            elapsed = (time.perf_counter() - started) * 1000
            if index:  # One explicit warm-up; exclude it from reported samples.
                timings.append({'fixture_id': index % len(REVIEWS), 'review_characters': len(text),
                    'completion_ms': round(elapsed, 3), 'mentions': len(preview['analysis']['tags'])})
    finally:
        request(base, f'/api/demo/products/{product["id"]}', method='DELETE')
    values = sorted(row['completion_ms'] for row in timings)
    try:
        cpu = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        cpu = platform.machine()
    report = {
        'measured_at': datetime.now(timezone.utc).isoformat(),
        'method': 'Sequential HTTP enqueue-to-completed-preview timing, 50ms polling, one excluded warm-up.',
        'scope': 'Local smoke measurement on short synthetic reviews; includes queue, worker scheduling, inference and polling. Not throughput, model-only latency or production p95.',
        'source_tree_sha256': fingerprint(), 'sample_count': len(values), 'warmup_count': 1,
        'environment': {'system': platform.system(), 'architecture': platform.machine(), 'cpu': cpu, 'python': platform.python_version(),
            'backend': health['backend'], 'storage': health['storage'], 'context_policy': health['context_policy']},
        'pipeline_version': health['pipeline_version'],
        'summary_ms': {'min': min(values), 'median': statistics.median(values), 'mean': statistics.mean(values),
            'p95_nearest_rank': values[math.ceil(.95 * len(values)) - 1], 'max': max(values)},
        'samples': timings, 'temporary_product_removed': True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'sample_count': len(values), 'summary_ms': report['summary_ms'], 'temporary_product_removed': True}))


if __name__ == '__main__':
    main()
