"""
This module contains how we control and manipulate the log format for the project by including
a base configuration for the log system, application name, ...

"""
import os
import socket
from typing import Literal

# ==================================================================================================
# Application Information
__version__ = '0.1.4'
__VERSION__ = __version__
__AUTHOR__ = 'Ichiru Take'

APP_NAME = 'PGTUNER_DBA'  # This name is used on log.toml,
SUPPORTED_POSTGRES_VERSIONS = ('13', '14', '15', '16', '17')
APP_NAME_LOWER: str = APP_NAME.lower()
APP_NAME_UPPER: str = APP_NAME.upper()

DEBUG_MODE: bool = os.getenv(f'{APP_NAME_UPPER}_DEBUG') is not None  # If this flag available regardless of the value
WEB_MODE: bool = os.getenv(f'{APP_NAME_UPPER}_WEB') is not None  # If this flag available regardless of the value

GC_FILE_PATH = 'conf/gc.toml'
LOG_FILE_PATH = 'conf/log.toml'
if DEBUG_MODE and os.path.exists('conf/log_debug.toml'):
    LOG_FILE_PATH = "conf/log_debug.toml"
elif WEB_MODE and os.path.exists('conf/log_web.toml'):
    LOG_FILE_PATH = 'conf/log_web.toml'

# SERVER_HOSTNAME: str = socket.gethostname()  # We don't use FQDN here
PG_ARCHIVE_DIR = '/var/lib/postgresql/mnt/archive/wal'
PG_LOG_DIR = '/var/log/postgresql'

BASE_ENTRY_READER_DIR: str = os.path.expanduser(f'./.{APP_NAME_LOWER}')
SUGGESTION_ENTRY_READER_DIR: str = os.path.join(BASE_ENTRY_READER_DIR, 'suggestions')

# ==================================================================================================
# Instruction Tuning
MULTI_ITEMS_SPLIT: str = ';'

# ==================================================================================================
# Define bytes size
K10: int = 1000
Ki: int = 1024
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

DB_PAGE_SIZE: int = 8 * Ki  # This is already hard-coded in the PostgreSQL source code
BASE_WAL_SEGMENT_SIZE: int = 16 * Mi  # This is already hard-coded in the PostgreSQL source code
# ==================================================================================================
# SHA3-512
RANDOM_IOPS: str = 'random_iops'
THROUGHPUT: str = 'throughput'
SUPPORTED_ALGORITHMS = Literal['shake_256', 'sha384', 'sha224', 'sha3_512', 'shake_128', 'blake2s', 'md5', 'blake2b',
'sha256', 'sha512', 'sha3_256', 'sha3_384', 'sha3_224', 'sha1']

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
DATETIME_PATTERN_FOR_FILENAME: str = r'%Y%m%d-%H%M%S'  # r'%Y-%m-%d_%H-%M-%S_%Z'
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
