"""Durable leased worker. Run separately with python -m backend.app.worker."""
import logging
import json
from hashlib import sha256
import os
from time import perf_counter
from threading import Event, Lock, Thread
from uuid import uuid4

from backend.app.repository import Repository, ROOT, pipeline_version
from contextlib import contextmanager
from review_tag_generator import ReviewAnalyzer

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, repository, analyzer):
        self.repository = repository
        self.analyzer = analyzer
        self.version = pipeline_version(analyzer.backend)
        self.id = str(uuid4())
        self.lock = Lock()
        self.stop = Event()

    @contextmanager
    def renewing_lease(self, job_id=None, preview_id=None):
        done = Event()
        def renew():
            while not done.wait(10):
                try:
                    self.repository.heartbeat(self.id, self.version, job_id, preview_id)
                except Exception:
                    logger.exception('Lease heartbeat failed')
        thread = Thread(target=renew, daemon=True)
        thread.start()
        try:
            yield
        finally:
            done.set()
            thread.join(timeout=2)

    def process_job(self, job_id):
        while not self.stop.is_set():
            # Keep the bulk lease alive while serving previews between rows.
            with self.renewing_lease(job_id=job_id):
                while not self.stop.is_set() and self.process_preview():
                    pass
            item = self.repository.next_item(job_id, self.id)
            if item is None:
                break
            key, review = item
            if key == 'skip':
                continue
            try:
                started = perf_counter()
                with self.renewing_lease(job_id=job_id), self.lock:
                    result = self.analyzer.analyze(review)
                result['pipeline_version'] = self.version
                result['elapsed_ms'] = round((perf_counter() - started) * 1000)
                self.repository.finish_item(job_id, key, self.id, result=result)
            except Exception as exc:
                logger.exception('Inference failed for job %s item %s', job_id, key)
                self.repository.finish_item(job_id, key, self.id, error=exc)

    def process_preview(self):
        preview = self.repository.claim_preview(self.id, self.version)
        if preview:
            preview_id, review = preview
            try:
                with self.renewing_lease(preview_id=preview_id), self.lock:
                    result = self.analyzer.analyze(review)
                result['pipeline_version'] = self.version
                self.repository.finish_preview(preview_id, self.id, result=result)
            except Exception as exc:
                self.repository.finish_preview(preview_id, self.id, error=exc)
            return True
        return False

    def run_once(self):
        self.repository.heartbeat(self.id, self.version)
        if self.process_preview():
            return True
        job_id = self.repository.claim(self.id, self.version)
        if not job_id:
            return False
        self.process_job(job_id)
        return True

    def run(self):
        while not self.stop.is_set():
            try:
                if not self.run_once():
                    self.stop.wait(0.5)
            except Exception:
                logger.exception('Worker failed; uncompleted items remain durable for lease recovery')
                self.stop.wait(2)


def runtime_metadata():
    backend = os.environ.get('DEMO_MODEL_BACKEND', os.environ.get('MODEL_BACKEND', 'transformer'))
    if backend not in ('transformer', 'heuristic'):
        raise ValueError('MODEL_BACKEND must be transformer or heuristic')
    if os.environ.get('APP_PROFILE') == 'release' and backend != 'transformer':
        raise ValueError('Release requires the trained transformer backend')
    policy = json.loads((ROOT / 'audit/evidence/current/policy.json').read_text())
    validation = (ROOT / 'audit/evidence/current/validation.json').read_bytes()
    if sha256(validation).hexdigest() != policy['validation_file_sha256']:
        raise RuntimeError('Frozen validation evidence changed; sentiment policy cannot be verified')
    return backend, policy['selected'] if backend == 'transformer' else 'local_clause'


def make_analyzer():
    backend, context_policy = runtime_metadata()
    return ReviewAnalyzer(use_transformer=backend == 'transformer', context_policy=context_policy,
        device=os.environ.get('MODEL_DEVICE', 'cpu'),
        aspect_model_path=os.environ.get('ASPECT_MODEL_PATH'),
        sentiment_model_path=os.environ.get('SENTIMENT_MODEL_PATH'),
        semantic_model_path=os.environ.get('SEMANTIC_MODEL_PATH'),
        semantic_revision=os.environ.get('SEMANTIC_MODEL_REVISION'),
        normalization_threshold=float(os.environ['NORMALIZATION_THRESHOLD']) if os.environ.get('NORMALIZATION_THRESHOLD') else None)


def main():
    import signal
    logging.basicConfig(level=logging.INFO)
    repository = Repository()
    worker = Worker(repository, make_analyzer())
    signal.signal(signal.SIGTERM, lambda *_: worker.stop.set())
    signal.signal(signal.SIGINT, lambda *_: worker.stop.set())
    try:
        worker.run()
    finally:
        repository.engine.dispose()


if __name__ == '__main__':
    main()
