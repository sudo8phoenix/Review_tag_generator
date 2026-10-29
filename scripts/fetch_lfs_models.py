"""Hydrate checkpoint LFS pointers in build environments without Git LFS."""
import hashlib
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
# Immutable revision containing the model artifacts; directory verification follows.
REVISION = 'a75f30e'


def hydrate(path):
    if path.stat().st_size > 1024:
        return
    pointer = path.read_bytes()
    if not pointer.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
        return
    match = re.search(rb'oid sha256:([a-f0-9]{64})\nsize ([0-9]+)', pointer)
    if not match:
        raise ValueError(f'Invalid LFS pointer: {path}')
    expected, size = match[1].decode(), int(match[2])
    relative = path.relative_to(ROOT).as_posix()
    url = f'https://media.githubusercontent.com/media/sudo8phoenix/Review_tag_generator/{REVISION}/{relative}'
    temporary = path.with_suffix(path.suffix + '.download')
    digest, count = hashlib.sha256(), 0
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > size:
                    raise ValueError('Model download exceeded expected size')
                digest.update(chunk)
                output.write(chunk)
        if count != size or digest.hexdigest() != expected:
            raise ValueError(f'Model download failed integrity check: {relative}')
        temporary.replace(path)
        print('Hydrated', relative)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    for path in ROOT.glob('models/**/best/*'):
        if path.suffix in {'.safetensors', '.bin'}:
            hydrate(path)
