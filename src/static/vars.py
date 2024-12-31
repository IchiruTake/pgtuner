"""
This module contains how we control and manipulate the log format for the project by including
a base configuration for the log system, application name, ...


"""
import os
import socket
from typing import Literal

# ==================================================================================================
# Application Information
__VERSION__ = "0.1.0"
__AUTHOR__ = "Ichiru Take"

APP_NAME = "PGTUNER_DBA"        # Don't change this value and ONLY text, numbers, and underscores are allowed.
SUPPORTED_POSTGRES_VERSIONS = ('13', '14', '15', '16', '17')
DEBUG_MODE: bool = os.getenv(f'{APP_NAME}_DEBUG') is not None     # If this flag available regardless of the value
GC_FILE_PATH = "conf/gc_debug.toml" if DEBUG_MODE and os.path.exists("conf/gc_debug.toml") else "conf/gc.toml"
LOG_FILE_PATH = "conf/log_debug.toml" if DEBUG_MODE and os.path.exists("conf/log_debug.toml") else "conf/log.toml"
APP_NAME_LOWER: str = APP_NAME.lower()
APP_NAME_UPPER: str = APP_NAME.upper()
PGTUNER_PROFILE_FILE_PATH = f'conf/{APP_NAME_LOWER}.toml'
PGTUNER_PROFILE_DIR_PATH = f'conf/{APP_NAME_LOWER}.d'
SERVER_HOSTNAME: str = socket.gethostname()     # We don't use FQDN here

PG_ARCHIVE_DIR = os.environ.get(f'{APP_NAME}_ARCHIVE_DIR', f'/mnt/{SERVER_HOSTNAME}/wal_archive')
PG_LOG_DIR = os.environ.get(f'{APP_NAME}_LOG_DIR', f'/var/log/{APP_NAME_LOWER}')        # TODO

BASE_ENTRY_READER_DIR: str = os.path.expanduser(f"./.{APP_NAME_LOWER}")
BACKUP_ENTRY_READER_DIR: str = os.path.join(BASE_ENTRY_READER_DIR, "backup")
SUGGESTION_ENTRY_READER_DIR: str = os.path.join(BASE_ENTRY_READER_DIR, "suggestions")
BACKUP_FILE_FORMAT = f"{APP_NAME_LOWER}_readme_*.conf"

# ==================================================================================================
# Environment Variables, if the variable begins with `PGC_` then it is a custom variable that is not available
# in the PostgreSQL environment.
ENV_PGDATA: str = "PGDATA"
ENV_PGHOST: str = "PGHOST"
ENV_PGPORT: str = "PGPORT"
ENV_PGUSER: str = "PGUSER"
ENV_PGPASSWORD: str = "PGPASSWORD"
ENV_PGDATABASE: str = "PGDATABASE"
ENV_PG_SERVER_VERSION: str = "PG_SERVER_VERSION"
ENV_PGC_CONN_EXTARGS: str = "PGC_CONN_EXTARGS"

# ==================================================================================================
# Instruction Tuning
DEFAULT_INSTRUCTION_PROFILE: str = "large"
MULTI_ITEMS_SPLIT: str = ';'

# ==================================================================================================
# Define bytes size
K10: int = 1_000
Ki: int = 1_024
M10: int = K10 ** 2
Mi: int = Ki ** 2
G10: int = K10 ** 3
Gi: int = Ki ** 3
T10: int = K10 ** 4
Ti: int = Ki ** 4
P10: int = K10 ** 5
Pi: int = Ki ** 5
E10: int = K10 ** 6
Ei: int = Ki ** 6

# 256 KiB: This variable is used for correction-tuning related to the memory/buffer size. A smaller value makes the
# tuning more specific and accurate, but prone to unpredictable user behaviour. A larger value makes the tuning more
# general and stable, but less accurate and unable the squeeze your system to the maximum performance.
NET_BUFFER_MIN_JUMP: int = 4 * Ki       # For network minimum
NET_BUFFER_DEF_JUMP: int = 16 * Ki      # For network default
NET_BUFFER_MAX_JUMP: int = 2 * Mi       # For network maximum
MEM_SMALL_JUMP_OFFSET: int = 8 * Mi     # For memory small jump
MEM_MEDIUM_JUMP_OFFSET: int = 32 * Mi   # For memory medium jump
MEM_LARGE_JUMP_OFFSET: int = 128 * Mi    # For memory large jump

DB_PAGE_SIZE: int = 8 * Ki              # This is already hard-coded in the PostgreSQL source code
WAL_SEGMENT_SIZE: int = 16 * Mi         # This is already hard-coded in the PostgreSQL source code
# ==================================================================================================
# SHA3-512
RANDOM_IOPS: str = 'random_iops'
THROUGHPUT: str = 'throughput'
SUPPORTED_ALGORITHMS = Literal['shake_256', 'sha384', 'sha224', 'sha3_512', 'shake_128', 'blake2s', 'md5', 'blake2b',
'sha256', 'sha512', 'sha3_256', 'sha3_384', 'sha3_224', 'sha1']
PRESET_PROFILE_CHECKSUM: tuple[tuple[str, SUPPORTED_ALGORITHMS, str], ...] = (
    (PGTUNER_PROFILE_FILE_PATH, 'sha3_512', '78076083d2429a01026015305e6299aed2ac75e804a01618f32218e533ec4e87414eb5988f7c62cdea83348b4a377131a1b61139dd6fa59a2a2f1ae042c1aced'),
    (f'{PGTUNER_PROFILE_DIR_PATH}/00-pgtuner_disk.toml', 'sha3_512', 'd6dffb0c18e9336ae54e64252bee43623012ccc50823c9bd71f58a1227ff02eb277581ebce1e269be4441e0a8ad0deb20dbdf7a1cabe45a833d04d5be674428d'),
    (f'{PGTUNER_PROFILE_DIR_PATH}/01-pgtuner_mini.toml', 'sha3_512', '4f399037ad561ca93b87fb8093a97474bcca9037327ec8ff81df37e45f76f7af29df5bd614465a4eac26112165971f3963270ba149a30e3862f22b2b309a75f1'),
    (f'{PGTUNER_PROFILE_DIR_PATH}/02-pgtuner_medium.toml', 'sha3_512', 'a1e7090af84268d05da5f1d1b81bc266274f1760bc6e86fa51132f01e5c413c856dcfe3920ffa4caa3bc6ce6a8815a7e7e8029ce874a95808850fac49b5fcf3b'),
    (f'{PGTUNER_PROFILE_DIR_PATH}/03-pgtuner_large.toml', 'sha3_512', 'd9e9adbccc97ced94880eee3701ee25f73b06fcd8621312f60b905c0f816221ccf90d6cb7c513d901d1c50ee280adfb61937fe3fa68166ed0228e569d344c650'),
    (f'{PGTUNER_PROFILE_DIR_PATH}/04-pgtuner_mall.toml', 'sha3_512', '2ff481377e28dc28e7c555db9b7ef7170c1cdf5587c16d5182fd2de2246f5919cee751090b7a385799ef07fb9ca5fdc11a6955cb83b9c7260739d5b13ccc2c81'),
    (f'{PGTUNER_PROFILE_DIR_PATH}/05-pgtuner_bigt.toml', 'sha3_512', '07d4afda07d7ef0aaed6965a9a72605fd75d69f824c7e151af713ba5b23bcd7346a82bdc6a9a4b766d93d0951d7b4355ce5b1b2d78046634b9fafd54a007eaa1'),
)


# ==================================================================================================
# RegEx Patterns for Logging
YEAR_PATTERN: str = r'%Y'
MONTH_PATTERN: str = r'%m'
DAY_PATTERN: str = r'%d'
HOUR_PATTERN: str = r'%H'
MINUTE_PATTERN: str = r'%M'
SECOND_PATTERN: str = r'%S'
ZONE_PATTERN: str = r'%z'  # Use %Z for timezone name if preferred
ZONENAME_PATTERN: str = r'%Z'  # Use %Z for timezone name if preferred

# Timer part
DATE_PATTERN: str = rf'{YEAR_PATTERN}-{MONTH_PATTERN}-{DAY_PATTERN}'
TIME_PATTERN: str = rf'{HOUR_PATTERN}:{MINUTE_PATTERN}:{SECOND_PATTERN}'
DATETIME_PATTERN_FOR_FILENAME: str = r'%Y%m%d-%H%M%S'        # r'%Y-%m-%d_%H-%M-%S_%Z'
DATETIME_PATTERN: str = ' '.join([DATE_PATTERN, TIME_PATTERN, ZONE_PATTERN])  # r'%Y-%m-%d %H:%M:%S %z'

# ==================================================================================================
# Timing Constants
NANOSECOND: float = 1e-9
MICROSECOND: float = 1e-6
MILLISECOND: float = 1e-3
SECOND: int = 1
MINUTE: int = 60 * SECOND
HOUR: int = 60 * MINUTE
DAY: int = 24 * HOUR
WEEK: int = 7 * DAY
MONTH: int = int(30.5 * DAY)
YEAR: int = int(365.25 * DAY)

# ==================================================================================================
# Typer Log Constants
TYPER_PRE_INFO: str = f"[{APP_NAME}-INFO]"
TYPER_PRE_ERROR: str = f"[{APP_NAME}-ERROR]"
TYPER_PRE_WARNING: str = f"[{APP_NAME}-WARNING]"
TYPER_PRE_SUCCESS: str = f"[{APP_NAME}-SUCCESS]"
TYPER_PRE_DEBUG: str = f"[{APP_NAME}-DEBUG]"
TYPER_PRE_CRITICAL: str = f"[{APP_NAME}-CRITICAL]"
TYPER_PRE_FATAL: str = f"[{APP_NAME}-FATAL]"
TYPER_PRE_EXCEPTION: str = f"[{APP_NAME}-EXCEPTION]"
TYPER_PRE_TRACEBACK: str = f"[{APP_NAME}-TRACEBACK]"
TYPER_PRE_QANDA: str = f"[{APP_NAME}-Q&A]"

# Typer Signal Constants
TYPER_PRE_PROGRESS: str = f"[{APP_NAME}-PROGRESS]"
TYPER_PRE_START: str = f"[{APP_NAME}-START]"
TYPER_PRE_END: str = f"[{APP_NAME}-END]"
TYPER_PRE_STOP: str = f"[{APP_NAME}-STOP]"
TYPER_PRE_EXIT: str = f"[{APP_NAME}-EXIT]"
TYPER_PRE_ABORT: str = f"[{APP_NAME}-ABORT]"
TYPER_PRE_CANCEL: str = f"[{APP_NAME}-CANCEL]"
TYPER_PRE_CONTINUE: str = f"[{APP_NAME}-CONTINUE]"
TYPER_PRE_PAUSE: str = f"[{APP_NAME}-PAUSE]"
TYPER_PRE_RESUME: str = f"[{APP_NAME}-RESUME]"
TYPER_PRE_RESTART: str = f"[{APP_NAME}-RESTART]"
TYPER_PRE_RELOAD: str = f"[{APP_NAME}-RELOAD]"
TYPER_PRE_RECONFIGURE: str = f"[{APP_NAME}-RECONFIGURE]"
