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

// ================================================================================
/**
 * Original Source File: ./src/utils/pydantic_utils.py
 * This file is part of the pgtuner project, containing static variables and constants such as
 * application information, instruction identification, timing constants, hard-coded values, and
 * regular expression patterns.
 */

/**
 * Converts a byte size to a human-readable string.
 *
 * @param {number} bytesize - The byte size to convert.
 * @param {boolean} [decimal=false] - If true, use decimal units (e.g. 1000 bytes per KB). If false, use binary units (e.g. 1024 bytes per KiB).
 * @param {string} [separator=' '] - A string used to split the value and unit. Defaults to an empty whitespace string (' ').
 * @returns {string} - A human-readable string representation of the byte size.
 */
const bytesize_to_hr = (bytesize, decimal = false, separator = ' ') => {
    if (typeof bytesize !== 'number') {
        bytesize = Math.floor(bytesize);
    }
    if (bytesize === 0) {
        return `0${separator}B`;
    }
    if (bytesize < 0) {
        throw new Error('Negative byte size is not supported');
    }
    let divisor, units, final_unit;
    if (decimal) {
        divisor = 1000;
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
        final_unit = 'EB';
    } else {
        divisor = 1024;
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'];
        final_unit = 'EiB';
    }
    let num = bytesize;
    for (let unit of units) {
        if (Math.abs(num) < divisor) {
            if (unit === 'B') {
                return `${num.toFixed(0)}${separator}${unit}`;
            } else {
                return `${num.toFixed(1)}${separator}${unit}`;
            }
        }
        num /= divisor;
    }
    return `${num.toFixed(1)}${separator}${final_unit}`;
}

/**
 * This function is used to ensure we re-align the :var:`value` to the nearest :var:`page_size`
 * so that the modified :var:`value` is a multiple of the :var:`page_size`.
 * @param {number} value - The value to be realigned.
 * @param {number} page_size - The page size to align to. Default is 8 * 1024 (8 KiB).
 * @returns {Array<number>} - An array containing the lower and upper bounds of the realigned value.
 */
const realign_value = (value, page_size = DB_PAGE_SIZE) => {
    if (typeof value === 'number') {
        value = Math.floor(value);
    }
    const d = Math.floor(value / page_size);
    const m = value % page_size;
    return [d * page_size, (d + (m > 0 ? 1 : 0)) * page_size];
}

/**
 * This function is used to ensure the :var:`value` is casted under the range of :var:`min_value`
 * and :var:`max_value`.
 *
 * @param {number} value - The value to be capped.
 * @param {number} min_value - The minimum value.
 * @param {number} max_value - The maximum value.
 * @param {Array<number>} [redirectNumber=null] - An optional array containing two numbers. If the
 * value is equal to the first number, it will be replaced by the second number.
 * @returns {number} - The capped value.
 */
const cap_value = (value, min_value, max_value, redirectNumber = null) => {
    if (redirectNumber && redirectNumber.length === 2 && value === redirectNumber[0]) {
        value = redirectNumber[1];
    }
    return Math.min(Math.max(value, min_value), max_value);
};

// =================================================================================
/**
 * Original Source File: ./src/utils/mean.py
 */

/**
 * Calculate the generalized mean of the given arguments and rounding to the specified number of digits.
 * This function is used to calculate the average of the given arguments using the power of the level.
 * If level = 1, it will be the same as the normal average.
 * Ref: https://en.wikipedia.org/wiki/Generalized_mean
 *
 * Parameters
 * ----------
 * @param {number[]} x - The series of numbers to be averaged.
 * @param {number} level - The level of the generalized mean.
 * @param {number} round_ndigits - The number of digits to round to.
 *
 * Example
 * -------
 * generalized_mean([1, 2], 1, 4)  // returns 1.5
 * generalized_mean([1, 2], -6, 4)  // returns 1.1196
 */
function generalized_mean(x, level, round_ndigits = 4) {
    if (level === 0) {
        level = 1e-6; // Small value to prevent division by zero
    }
    const n = x.length;
    const sumPower = x.reduce((acc, val) => acc + Math.pow(val, level), 0);
    const result = Math.pow(sumPower / n, 1 / level);

    // Rounding the number to the specified number of digits
    if (round_ndigits !== null) {
        if (typeof round_ndigits !== 'number') {
            throw new Error("The 'round_ndigits' property must be a number.");
        }

        if (round_ndigits < 0) {
            throw new Error("The 'round_ndigits' property must be a non-negative number.");
        }
    }
    const factor = Math.pow(10, round_ndigits);
    return Math.round(result * factor) / factor;
}


// =================================================================================
/**
 * Original Source File: ./src/tuner/profile/common.py
 *
 * This contains some common functions during the general tuning, which is used to perform the
 * validation and modification of the profile data. The functions are:
 * - merge_extra_info_to_profile: Merge the extra information into the profile data.
 * - type_validation: Perform the type validation for the profile data.
 * - rewrite_items: Drop the deprecated items from the profile data.
 */
const merge_extra_info_to_profile = (profiles) => {
    /* Merge the profile data into a single file. */
    for (const [unused_1, [unused_2, items, extra_default]] of Object.entries(profiles)) {
        for (const [default_key, default_value] of Object.entries(extra_default)) {
            for (const [itm_name, itm_value] of Object.entries(items)) {
                if (!(default_key in itm_value)) {
                    itm_value[default_key] = default_value;
                }
            }
        }
    }
    return null;
};
const type_validation = (profiles) => {
    /* Type validation for the profile data. */
    for (const [unused_1, [scope, category_profile, unused_2]] of Object.entries(profiles)) {
        for (const [mkey, tune_entry] of Object.entries(category_profile)) {
            // Narrow check
            if (typeof tune_entry !== 'object' || tune_entry === null) {
                throw new Error(`The tuning key body of ${mkey} is not a dictionary.`);
            }
            if (typeof mkey !== 'string') {
                throw new Error(`The key ${mkey} is not a string.`);
            }
            const keys = mkey.split(MULTI_ITEMS_SPLIT).map(k => k.trim());
            if (!keys.every(k => k && !k.includes(' '))) {
                throw new Error(`The key representation ${mkey} is empty or contains whitespace.`);
            }

            // Body check
            if (!('default' in tune_entry)) {
                throw new Error(`The default value is not found in the tuning key body of ${mkey} this could lead to no result of tuning`);
            }
            if (typeof tune_entry['default'] === 'function' || tune_entry['default'] === null) {
                throw new Error(`${mkey}: The default value must be a non-null static value.`);
            }
            if ('tune_op' in tune_entry && typeof tune_entry['tune_op'] !== 'function') {
                throw new Error(`${mkey}: The generic tuning operation must be a function.`);
            }

            if ('instructions' in tune_entry) {
                if (typeof tune_entry['instructions'] !== 'object' || tune_entry['instructions'] === null) {
                    throw new Error(`${mkey}: The profile-based instructions must be a dictionary of mixed instructions and static value.`);
                }
                for (const [pr_key, pr_value] of Object.entries(tune_entry['instructions'])) {
                    if (typeof pr_key === 'function' || pr_key === null) {
                        throw new Error(`${mkey}-ins-${pr_key}: The profile key must be a non-null, non-empty static value.`);
                    }
                    if (pr_key.endsWith('_default')) {
                        if (typeof pr_value === 'function' || pr_value === null) {
                            throw new Error(`${mkey}-ins-${pr_key}: The profile default value must be a non-null static value.`);
                        }
                    } else {
                        if (typeof pr_value !== 'function') {
                            throw new Error(`${mkey}-ins-${pr_key}: The profile tuning guideline must be a function.`);
                        }
                    }
                }
            }
        }
    }
    return null;
};
const rewrite_items = (profiles) => {
    /** Drop the deprecated items from the profile data. */
    for (const [unused_1, [unused_2, items, unused_3]] of Object.entries(profiles)) {
        const remove_keys = [];
        for (const [mkey, unused_4] of Object.entries(items)) {
            if (mkey.startsWith('-')) {
                remove_keys.push(mkey.slice(1));
            }
        }
        for (const rm_key of remove_keys) {
            if (rm_key in items) {
                if (rm_key.includes(MULTI_ITEMS_SPLIT)) {
                    throw new Error(`Only a single tuning key is allowed for deletion: ${rm_key}`);
                }
                delete items[rm_key];
            } else {
                console.warn(`The tuning key ${rm_key} is expected to be removed but not found in its scope or tuning result.`);
            }
            delete items[`-${rm_key}`];
        }
    }
    return null;
};
const show_profile = (profile) => {
    /* Show the profile data. */
    for (const [key, value] of Object.entries(profile)) {
        console.debug(key, value[1]);
    }
    return null;
}