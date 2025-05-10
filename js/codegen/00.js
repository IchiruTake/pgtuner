/**
 * This project is a direct conversion of the original Python project :app:`pgtuner` to JavaScript.
 * Only the backend is converted to JavaScript, while the frontend remains in Python, and maintained
 * as a separate project.
 * Logging and Pydantic are removed but maintained the same functionality. All variable names,
 * attributes, and methods are kept the same as the original Python project (including the name).
 *
 */

// ================================================================================
/**
 * Original Source File: ./src/utils/static.py
 * This file is part of the pgtuner project, containing static variables and constants such as
 * application information, instruction identification, timing constants, hard-coded values, and
 * regular expression patterns.
 */

// Application Information
const __version__ = '0.1.5';
const __VERSION__ = __version__;
const __AUTHOR__ = 'Ichiru Take';

const APP_NAME = 'PGTUNER_DBA'; // This name is used on log.toml,
const SUPPORTED_POSTGRES_VERSIONS = [13, 14, 15, 16, 17, 18];
const APP_NAME_LOWER = APP_NAME.toLowerCase();
const APP_NAME_UPPER = APP_NAME.toUpperCase();

const PG_ARCHIVE_DIR = '/var/lib/postgresql/mnt/archive/wal';
const PG_LOG_DIR = '/var/log/postgresql';

// Instruction Tuning
const MULTI_ITEMS_SPLIT = ';';

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

// Hard-coded values in the PostgreSQL source code
const DB_PAGE_SIZE = 8 * Ki;
const BASE_WAL_SEGMENT_SIZE = 16 * Mi; // This is customizable in PostgreSQL
const RANDOM_IOPS = 'random_iops';
const THROUGHPUT = 'throughput';

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

function getJSVersion() {
    let version = undefined;
    if (String.prototype.trim) {
        version = 5;
        if (Array.prototype.map) {
            version = 6;
            if (Array.prototype.includes) {
                version = 7;
                if (Object.values) {
                    version = 8;
                    if (Promise.prototype.finally) {
                        version = 9;
                        if (Array.prototype.flat) {
                            version = 10;
                            if (String.prototype.matchAll) {
                                version = 11;
                                if (String.prototype.replaceAll) {
                                    version = 12;
                                    if (Object.hasOwn) {
                                        version = 13;
                                        if (Array.prototype.toSorted) {
                                            version = 14;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    if (version) {
        return "1." + version;
    } else {
        return "unknown";
    }
}

let javascript_version = getJSVersion();
console.log(`JavaScript version: ${javascript_version}`); // Expected ES6 or higher