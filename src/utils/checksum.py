import hashlib
from src.static.vars import SUPPORTED_ALGORITHMS

__all__ = ['checksum']
PAGE_SIZE: int = 4 * 1024           # Default page size for reading file
def checksum(file_path: str, alg: SUPPORTED_ALGORITHMS = 'sha3_512') -> str:
    with open(file_path, 'rb', buffering=PAGE_SIZE) as f:
        digest = hashlib.file_digest(f, alg)
        return digest.hexdigest()
