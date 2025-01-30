"""
This module contains how we control and manipulate the log format for the project by including
a base configuration for the log system, application name, ...

"""
import os
import socket
from typing import Literal

# ==================================================================================================
# Application Information
__version__ = '0.1.0'
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
PGTUNER_PROFILE_FILE_PATH = f'conf/{APP_NAME_LOWER}.toml'
PGTUNER_PROFILE_DIR_PATH = f'conf/{APP_NAME_LOWER}.d'

SERVER_HOSTNAME: str = socket.gethostname()  # We don't use FQDN here
if WEB_MODE:
    SERVER_HOSTNAME = '<postgres-host>'

PG_ARCHIVE_DIR = '/mnt/<any-storage-host>/<postgresql-hostname>/postgresql/archive/wal'
PG_LOG_DIR = '/mnt/<any-storage-host>/<postgresql-hostname>/postgresql/archive/db_log'

BASE_ENTRY_READER_DIR: str = os.path.expanduser(f'./.{APP_NAME_LOWER}')
BACKUP_ENTRY_READER_DIR: str = os.path.join(BASE_ENTRY_READER_DIR, 'backup')
SUGGESTION_ENTRY_READER_DIR: str = os.path.join(BASE_ENTRY_READER_DIR, 'suggestions')

# ==================================================================================================
# Instruction Tuning
DEFAULT_INSTRUCTION_PROFILE: str = 'large'
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
PRESET_PROFILE_CHECKSUM: tuple[tuple[str, SUPPORTED_ALGORITHMS, str], ...] = (
    (PGTUNER_PROFILE_FILE_PATH, 'sha3_512',
     '78076083d2429a01026015305e6299aed2ac75e804a01618f32218e533ec4e87414eb5988f7c62cdea83348b4a377131a1b61139dd6fa59a2a2f1ae042c1aced'),
    (f'{PGTUNER_PROFILE_DIR_PATH}/00-pgtuner_disk.toml', 'sha3_512',
     '151aec6e4de49fb27e1c16ca0eb821fa5d6eb5c41d7281d9c06bcf283a6be50bd3e00a1967a544723b2c070396d41bfe1ccc4cdeb67841a102f3e5550a55cb5d'),
    # (f'{PGTUNER_PROFILE_DIR_PATH}/01-pgtuner_mini.toml', 'sha3_512', 'd51b38243ce5ac6ef4624883831ea3a3f4e3cac85d1fcddc218e3c4062e95d0e5f9f4dbdc74d86fdc6488c9f50284eb6f16a41df8552199d5cb9a1c045f79b8a'),
    # (f'{PGTUNER_PROFILE_DIR_PATH}/02-pgtuner_medium.toml', 'sha3_512', '7c76060245dc0575ba9fc6f3bbe6d1bd94dff71c17428f3ab0f84e3556fdab5b97571173a68a0a6d4dd1892af326c300ded162ed970ab43a392431f93fb05e0a'),
    # (f'{PGTUNER_PROFILE_DIR_PATH}/03-pgtuner_large.toml', 'sha3_512', '87b7e76cee850fd2b961398f53875bff1c759b2d60018fb9042da49f028a500ce1d46f0e4eaf74a5f45957842b4214854ba90b3c881da2490411bfcedc599ef5'),
    # (f'{PGTUNER_PROFILE_DIR_PATH}/04-pgtuner_mall.toml', 'sha3_512', '1ea1d466880b920f0d7e268f0456654f474bf8c8c8bfcb741973b5c8ff6483513e275437373b703201a7ae6fdf4b0c8515e75e179e5376d9e62008498b2d98b9'),
    # (f'{PGTUNER_PROFILE_DIR_PATH}/05-pgtuner_bigt.toml', 'sha3_512', '5ec631f93963fde436d7f8c2ecbe4503baf734232d7196fa81d4a425b931cbb1b8a340a3fee68ab0a78f27f66416fa145b847cd4552d182991382bd1bc73497c'),
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
