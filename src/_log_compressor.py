import gzip
import lzma
import shutil
import os
import zlib
import bz2
import logging.handlers
import glob

__all__ = ['CompressRotatingFileHandler', 'CompressTimedRotatingFileHandler']


def _interpret(algorithm: str) -> tuple[str, int, str] | None:
    if ':' not in algorithm:
        return None
    ext_mapper = {'gzip': 'gz', 'zlib': 'zlib', 'bz2': 'bz2', 'lzma': 'xz'}
    alg, level = algorithm.split(':')
    if alg not in ext_mapper:
        return None
    level = int(level)
    return alg, level, ext_mapper[alg]


class CompressRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        algorithm = kwargs.get('compression_algorithm', 'gzip:9')
        if 'compression_algorithm' in kwargs:
            del kwargs['compression_algorithm']
        super().__init__(*args, **kwargs)
        self._algorithm = _interpret(algorithm)

    def rotate(self, source: str, dest: str):
        super().rotate(source, dest)
        if self._algorithm is not None:
            cmp_filepath: str = _compress(source, dest, algorithm=self._algorithm)
            _cleanup(cmp_filepath, backup_count=self.backupCount, algorithm=self._algorithm)
        return None


class CompressTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, *args, **kwargs):
        algorithm = kwargs.get('compression_algorithm', 'gzip:9')
        if 'compression_algorithm' in kwargs:
            del kwargs['compression_algorithm']
        super().__init__(*args, **kwargs)
        self._algorithm = _interpret(algorithm)

    def rotate(self, source: str, dest: str):
        super().rotate(source, dest)
        if self._algorithm is not None:
            cmp_filepath: str = _compress(source, dest, algorithm=self._algorithm)
            _cleanup(cmp_filepath, backup_count=self.backupCount, algorithm=self._algorithm)
        return None


def _compress(source: str, dest: str, algorithm: tuple[str, int, str] = None):
    print(f'Compression is triggered with source={source}, dest={dest}, algorithm={algorithm}')
    alg, level, extension_name = algorithm
    temp_filepath = f'{dest}.tmp'  # Add tmp here to avoid the conflict with namer()
    if os.path.exists(temp_filepath):
        os.remove(temp_filepath)

    if alg == 'gzip':
        with open(dest, 'rb') as f_in:
            with gzip.open(temp_filepath, 'wb', compresslevel=level) as f_out:
                shutil.copyfileobj(f_in, f_out)
    elif alg == 'zlib':
        with open(dest, 'rb') as f_in:
            with open(temp_filepath, 'wb') as f_out:
                f_out.write(zlib.compress(f_in.read(), level))
    elif alg == 'bz2':
        with open(dest, 'rb') as f_in:
            with bz2.open(temp_filepath, 'wb', compresslevel=level) as f_out:
                shutil.copyfileobj(f_in, f_out)
    elif alg == 'lzma':
        with open(dest, 'rb') as f_in:
            with lzma.open(temp_filepath, 'wb', preset=level) as f_out:
                shutil.copyfileobj(f_in, f_out)

    # Only remove the original file if the compression is successful or one compression is in-place
    if os.path.exists(temp_filepath):
        os.remove(dest)
        shutil.move(temp_filepath, f'{dest}.{extension_name}')

    return temp_filepath

def _cleanup(compress_filepath: str, backup_count: int, algorithm: tuple[str, int, str] = None, ):
    # Scan all files and remove all compressed files made by logging
    if algorithm is None:
        return None
    dot_in_compress_filepath = compress_filepath.removesuffix(f'.{algorithm[2]}').rfind('.')
    leftover_files = glob.glob(f'{compress_filepath[:dot_in_compress_filepath]}.*.{algorithm[2]}')
    if len(leftover_files) <= backup_count:
        return None
    # We have more files than the backup count, remove the oldest files based on its creation rather than
    # modified time
    leftover_files.sort(key=os.path.getctime)
    for file in leftover_files[:len(leftover_files) - backup_count]:
        os.remove(file)

    pass
