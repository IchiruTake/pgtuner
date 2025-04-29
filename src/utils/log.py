"""
This module provides a simple logging setup for the project. Supports on logging with
multiple formats and file handlers. Note that we don't support log rotation yet.

Usage:
-----

References:
    1) https://stackoverflow.com/questions/11232230/logging-to-two-files-with-different-settings 

"""
import logging
import logging.handlers
import os
import os.path
import shutil
import sys
from datetime import datetime, date
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Any

from src.utils.static import TIMEZONE, DATE_PATTERN, DATETIME_PATTERN_FOR_FILENAME, APP_NAME_UPPER, Mi
from src.utils.base import TranslateNone

__all__ = ["BuildLogger"]


# ==================================================================================================
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
        import gzip
        with open(dest, 'rb') as f_in:
            with gzip.open(temp_filepath, 'wb', compresslevel=level) as f_out:
                shutil.copyfileobj(f_in, f_out)
    elif alg == 'zlib':
        import zlib
        with open(dest, 'rb') as f_in:
            with open(temp_filepath, 'wb') as f_out:
                f_out.write(zlib.compress(f_in.read(), level))
    elif alg == 'bz2':
        import bz2
        with open(dest, 'rb') as f_in:
            with bz2.open(temp_filepath, 'wb', compresslevel=level) as f_out:
                shutil.copyfileobj(f_in, f_out)
    elif alg == 'lzma':
        import lzma
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
    import glob
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


# ==================================================================================================
# File Handler
def _BuildLogFilepath(profile: dict[str, Any]) -> str:
    log_file_path: str = profile.get('LOG_FILE_PATH', '')
    log_file_extension: str = profile.get('LOG_FILE_EXTENSION', 'log')
    log_rotate_with_date_only = profile.get('LOG_ROTATE_WITH_DATE_ONLY', False)
    log_rotate_with_date_time = profile.get('LOG_ROTATE_WITH_DATE_TIME', False)

    assert log_file_path != '', "LOG_FILE_PATH must be provided."
    assert not all([log_rotate_with_date_only, log_rotate_with_date_time]), \
        "Logging with datetime and date-only are mutually exclusive."

    if log_rotate_with_date_only:
        dt = date.today().strftime(DATE_PATTERN)
        return f'{log_file_path}.{dt}.{log_file_extension}'
    elif log_rotate_with_date_time:
        dt = datetime.now(tz=TIMEZONE).strftime(DATETIME_PATTERN_FOR_FILENAME)
        return f'{log_file_path}.{dt}.{log_file_extension}'
    return f'{log_file_path}.{log_file_extension}'


def _BuildFileHandler(profile: dict[str, Any], readonly_clogger: logging.Logger) -> (
        logging.FileHandler | RotatingFileHandler | TimedRotatingFileHandler | None):
    # [00] Validation and Checkout if the handler is OK to proceed:
    handler_type: str = profile.get('HANDLER_TYPE')
    assert isinstance(handler_type, str), "handler_type must be provided."
    if handler_type not in ('FileHandler', 'RotatingFileHandler', 'TimedRotatingFileHandler'):
        return None

    encoding: str = profile.get('ENCODING', 'utf-8')
    log_filemode: str = profile.get('LOG_FILEMODE', 'a')
    log_format: str = profile.get('LOG_FORMAT')
    log_delay: bool = profile.get('DELAY', False)

    if encoding != 'utf-8':
        readonly_clogger.warning("Encoding is not :scheme:`utf-8`. Please check the encoding for the file handler.")
    if not isinstance(log_delay, bool):
        readonly_clogger.warning("DELAY must be a boolean -> Force :attr:`DELAY` to False.")
        log_delay = False

    if log_format is None:
        message = "LOG_FORMAT must be provided."
        readonly_clogger.error(message)
        raise ValueError(message)
    if log_filemode not in ('a', 'w', 'x'):
        message = "Invalid LOG_FILEMODE value. Please check the value again."
        readonly_clogger.error(message)
        raise ValueError(message)

    # [01]: Build the log filename and Check if file exists
    log_file_path: str = _BuildLogFilepath(profile)
    if not os.path.exists(log_file_path):
        directory = os.path.dirname(log_file_path)
        if directory != '' and not os.path.exists(directory):
            # https://stackoverflow.com/questions/2967194/open-in-python-does-not-create-a-file-if-it-doesnt-exist
            # Credit to Chenglong Ma (Jan 30th, 2021) for the solution.
            os.makedirs(directory, exist_ok=True)
        open(log_file_path, 'x').close()
    log_level: int = profile.get('LEVEL', logging.INFO)
    readonly_clogger.debug(f"New file: {log_file_path} with format: {log_format} at level {log_level}")

    # [02] Create the file handler
    match handler_type:
        case 'FileHandler':
            h = logging.FileHandler(log_file_path, mode=log_filemode, encoding=encoding, delay=log_delay)
        case 'RotatingFileHandler':
            max_bytes: int = profile.get('MAX_BYTES', 16 * Mi)
            backup_count: int = profile.get('BACKUP_COUNT', 5)
            assert isinstance(max_bytes, int) and max_bytes >= 0, "MAX_BYTES must be a positive integer."
            assert isinstance(backup_count, int) and 0 < backup_count <= 128, \
                "BACKUP_COUNT must be a positive integer, ranged from 0 to 128."
            if max_bytes == 0:
                readonly_clogger.warning('MAX_BYTES is set to 0. The log file will not be rotated.')
            compression_algorithm: str = profile.get('COMPRESSION', '')
            print(f'Compression algorithm for {log_file_path}: {compression_algorithm}')
            # h = RotatingFileHandler(log_file_path, mode=log_filemode, encoding=encoding,
            #                         delay=log_delay, maxBytes=max_bytes, backupCount=backup_count)
            h = CompressRotatingFileHandler(log_file_path, mode=log_filemode, encoding=encoding,
                                            delay=log_delay, maxBytes=max_bytes, backupCount=backup_count,
                                            compression_algorithm=compression_algorithm)
        case 'TimedRotatingFileHandler':
            when: str = profile.get('WHEN', 'D').lower()
            interval: int = profile.get('INTERVAL', 1)
            backup_count: int = profile.get('BACKUP_COUNT', 5)
            assert isinstance(backup_count, int) and 0 < backup_count <= 128, \
                'BACKUP_COUNT must be a positive integer, ranged from 0 to 128.'
            compression_algorithm: str = profile.get('COMPRESSION', '')
            print(f'Compression algorithm for {log_file_path}: {compression_algorithm}')
            # h = TimedRotatingFileHandler(log_file_path, when=when, interval=interval, encoding=encoding,
            #                              backupCount=backup_count, delay=log_delay, utc=False, atTime=None)
            h = CompressTimedRotatingFileHandler(log_file_path, when=when, interval=interval, encoding=encoding,
                                                 backupCount=backup_count, delay=log_delay, utc=False, atTime=None,
                                                 compression_algorithm=compression_algorithm)
        case _:
            raise ValueError("Invalid handler_type value. Please check the value again.")
    formatter = logging.Formatter(log_format)
    formatter.converter = lambda *args: datetime.now(tz=TIMEZONE).timetuple()
    h.setFormatter(formatter)
    h.setLevel(log_level)
    return h


# Stream Handler
def _BuildStreamHandler(profile: dict[str, Any], readonly_clogger: logging.Logger) -> logging.StreamHandler | None:
    # [01] Build the stream handler
    log_stream: str | None = profile.get('STREAM', None)
    log_format: str | None = profile.get('LOG_FORMAT', None)
    log_level: int = profile.get('LEVEL', logging.INFO)
    readonly_clogger.debug(f"New log stream: {log_stream} with format: {log_format} at level {log_level}")
    if log_stream is None:
        raise ValueError("STREAM must be provided.")

    match log_stream:
        case 'ext://sys.stdout':
            h = logging.StreamHandler(stream=sys.stdout)
        case 'ext://sys.stderr':
            h = logging.StreamHandler(stream=sys.stderr)
        case _:
            raise ValueError("Invalid STREAM value. Please check the value again.")
    formatter = logging.Formatter(log_format)
    formatter.converter = lambda *args: datetime.now(tz=TIMEZONE).timetuple()
    h.setFormatter(formatter)
    h.setLevel(log_level)
    return h


def _BuildHandlers(profile: dict[str, dict], readonly_clogger: logging.Logger) -> list[logging.Handler]:  # type: ignore
    # [00] Validation and Checkout if the handler is OK to proceed:
    _term: str = '_HANDLER'
    output: list[logging.Handler] = []
    for key, sub_profile in profile.items():
        if key.endswith(_term) and isinstance(sub_profile, dict) and sub_profile.get('ENABLED', False) is True:
            h: logging.Handler | None = None
            if key.endswith(f'FILE{_term}'):
                h = _BuildFileHandler(sub_profile, readonly_clogger=readonly_clogger)
                readonly_clogger.debug(f'A file handler is built as {key}')

            if key.endswith(f'STREAM{_term}'):
                h = _BuildStreamHandler(sub_profile, readonly_clogger=readonly_clogger)
                readonly_clogger.debug(f'A stream handler is built as {key}')

            if h is not None:
                output.append(h)
            else:
                readonly_clogger.warning(f"A handler is found that matched with the suffix {_term} and enabled, but it "
                                         f"is not in the support type so we ignored its build.")

    return output


def BuildLogger(cfg: dict[str, Any] | str) -> logging.Logger:
    if isinstance(cfg, str):  # A filepath
        import toml
        with open(cfg, 'r') as f:
            cfg = toml.load(f)['LOGGER']
            if __debug__:
                from pprint import pprint
                pprint(cfg)

    # [00] Validation and Checkout if the handler is OK to proceed:
    assert isinstance(cfg, dict), "Config must be a dictionary."
    TranslateNone(cfg)
    logger_name: str = cfg.get('NAME', APP_NAME_UPPER).upper()
    logger_level: int = cfg.get('LEVEL', logging.DEBUG)
    print(f"Building logger {logger_name} with level {logger_level}...")

    # [01] Setup logger
    manager = logging.Logger.manager.loggerDict.keys()
    c_logger: logging.Logger = logging.getLogger(logger_name)
    c_logger.debug(f"Current loggers: {manager}")
    if logger_name in manager:
        c_logger.debug(f"Logger {logger_name} is already in the manager.")

    c_logger.setLevel(logger_level)
    c_handlers = list(c_logger.handlers)
    _file_handlers = (logging.FileHandler, RotatingFileHandler, TimedRotatingFileHandler,
                      CompressTimedRotatingFileHandler, CompressRotatingFileHandler)
    for c_handler in c_handlers:
        if isinstance(c_handler, _file_handlers):
            c_logger.removeHandler(c_handler)
        if isinstance(c_handler, logging.StreamHandler):
            c_logger.removeHandler(c_handler)

    for h in _BuildHandlers(cfg[logger_name], readonly_clogger=c_logger):
        c_logger.addHandler(h)

    c_logger.info(f"Logger {logger_name} is created and initialized.")
    return c_logger
