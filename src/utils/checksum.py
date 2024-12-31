import hashlib
from typing import Literal

__all__ = ['checksum']

from src.static.vars import SUPPORTED_ALGORITHMS

PAGE_SIZE: int = 4 * 1024           # Default page size for reading file

def checksum(file_path: str, alg: SUPPORTED_ALGORITHMS = 'sha3_512') -> str:
    with open(file_path, 'rb', buffering=PAGE_SIZE) as f:
        digest = hashlib.file_digest(f, alg)
        return digest.hexdigest()
