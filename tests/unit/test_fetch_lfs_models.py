import hashlib
import io
from pathlib import Path
import pytest
from scripts import fetch_lfs_models as fetch


def test_pointer_hydration_checks_integrity(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, 'ROOT', tmp_path)
    payload = b'verified model bytes'
    digest = hashlib.sha256(payload).hexdigest()
    path = tmp_path / 'model.safetensors'
    pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{digest}\nsize {len(payload)}\n'
    path.write_text(pointer)
    monkeypatch.setattr(fetch.urllib.request, 'urlopen', lambda *args, **kwargs: io.BytesIO(payload))
    fetch.hydrate(path)
    assert path.read_bytes() == payload
    path.write_text(pointer)
    monkeypatch.setattr(fetch.urllib.request, 'urlopen', lambda *args, **kwargs: io.BytesIO(b'invalid'))
    with pytest.raises(ValueError):
        fetch.hydrate(path)
    assert path.read_text() == pointer
    assert not list(tmp_path.glob('*.download'))
