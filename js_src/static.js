/*
This module contains how we control and manipulate the log format for the project by including
a base configuration for the log system, application name, ...



*/

// ==================================================================================================
// Application Information
const __version__ = '0.1.4';
const __VERSION__ = __version__;
const __AUTHOR__ = 'Ichiru Take';

const APP_NAME = 'PGTUNER_DBA'; // This name is used on log.toml,
const SUPPORTED_POSTGRES_VERSIONS = ['13', '14', '15', '16', '17', '18'];
const APP_NAME_LOWER = APP_NAME.toLowerCase();
const APP_NAME_UPPER = APP_NAME.toUpperCase();

const PG_ARCHIVE_DIR = '/var/lib/postgresql/mnt/archive/wal';
const PG_LOG_DIR = '/var/log/postgresql';


// ==================================================================================================
// Instruction Tuning
const MULTI_ITEMS_SPLIT = ';';

// ==================================================================================================
// Define bytes size
const K10 = 1000;
const Ki = 1024;
const M10 = K10 ** 2;
const Mi = Ki ** 2;
const G10 = K10 ** 3;
const Gi = Ki ** 3;
const T10 = K10 ** 4;
const Ti = Ki ** 4;
const P10 = K10 ** 5;
const Pi = Ki ** 5;
const E10 = K10 ** 6;
const Ei = Ki ** 6;

const DB_PAGE_SIZE = 8 * Ki;  // This is already hard-coded in the PostgreSQL source code
const BASE_WAL_SEGMENT_SIZE = 16 * Mi;  // This is already hard-coded in the PostgreSQL source code
// ==================================================================================================
const RANDOM_IOPS = 'random_iops';
const THROUGHPUT = 'throughput';

// ==================================================================================================
// RegEx Patterns for Logging
const YEAR_PATTERN = '%Y';
const MONTH_PATTERN = '%m';
const DAY_PATTERN = '%d';
const HOUR_PATTERN = '%H';
const MINUTE_PATTERN = '%M';
const SECOND_PATTERN = '%S';
const ZONE_PATTERN = '%z';  // Use %Z for timezone name if preferred
const ZONENAME_PATTERN = '%Z';  // Use %Z for timezone name if preferred

// Timer part
const DATE_PATTERN = `${YEAR_PATTERN}-${MONTH_PATTERN}-${DAY_PATTERN}`;
const TIME_PATTERN = `${HOUR_PATTERN}:${MINUTE_PATTERN}:${SECOND_PATTERN}`;
const DATETIME_PATTERN_FOR_FILENAME = '%Y%m%d-%H%M%S';  // e.g. '%Y-%m-%d_%H-%M-%S_%Z'
const DATETIME_PATTERN = [DATE_PATTERN, TIME_PATTERN, ZONE_PATTERN].join(' ');

// ==================================================================================================
// Timing Constants
const NANOSECOND = 1e-9;
const MICROSECOND = 1e-6;
const MILLISECOND = 1e-3;
const SECOND = 1;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;
const MONTH_TIME = Math.round(30.5 * DAY);
const YEAR_TIME = Math.round(365.25 * DAY);

export default {
    __version__,
    __VERSION__,
    __AUTHOR__,
    APP_NAME,
    SUPPORTED_POSTGRES_VERSIONS,
    APP_NAME_LOWER,
    APP_NAME_UPPER,
    DEBUG_MODE,
    WEB_MODE,
    GC_FILE_PATH,
    LOG_FILE_PATH,
    PG_ARCHIVE_DIR,
    PG_LOG_DIR,
    BASE_ENTRY_READER_DIR,
    SUGGESTION_ENTRY_READER_DIR,
    MULTI_ITEMS_SPLIT,
    K10,
    Ki,
    M10,
    Mi,
    G10,
    Gi,
    T10,
    Ti,
    P10,
    Pi,
    E10,
    Ei,
    DB_PAGE_SIZE,
    BASE_WAL_SEGMENT_SIZE,
    RANDOM_IOPS,
    THROUGHPUT,
    SUPPORTED_ALGORITHMS,
    YEAR_PATTERN,
    MONTH_PATTERN,
    DAY_PATTERN,
    HOUR_PATTERN,
    MINUTE_PATTERN,
    SECOND_PATTERN,
    ZONE_PATTERN,
    ZONENAME_PATTERN,
    DATE_PATTERN,
    TIME_PATTERN,
    DATETIME_PATTERN_FOR_FILENAME,
    DATETIME_PATTERN,
    NANOSECOND,
    MICROSECOND,
    MILLISECOND,
    SECOND,
    MINUTE,
    HOUR,
    DAY,
    WEEK,
    MONTH: MONTH_TIME,
    YEAR: YEAR_TIME
};