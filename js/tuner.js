/**
 * This project is a direct conversion of the original Python project :app:`pgtuner` to JavaScript.
 * Only the backend are converted to JavaScript, while the frontend remains in Python, and maintained
 * as a separate project. 
 * Logging and Pydantic are removed, but maintained the same functionality. All variable names, 
 * attributes, and methods are kept the same as the original Python project (including the name).
 * 
 * LICENSE
 * MIT License
 * Copyright (c) 2024-2025 Ichiru Take
 * 
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
 * OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 * ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
 * OR OTHER DEALINGS IN THE SOFTWARE.
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
const SUPPORTED_POSTGRES_VERSIONS = ['13', '14', '15', '16', '17', '18'];
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
    var version = undefined;
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
 * 
 * @returns {string} - A human-readable string representation of the byte size.
 */
const bytesize_to_hr = (bytesize, decimal = false, separator = ' ') => {
    if (typeof bytesize === 'number') {
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
    return min(max(value, min_value), max_value);
};

// =================================================================================
/**
 * Original Source File: ./src/utils/mean.py
 * 
 * This function is used to calculate the generalized mean 
 * 
 */

/**
 * Calculate the generalized mean of the given arguments, and rounding to the specified number of digits.
 * This function is used to calculate the average of the given arguments using the power of the level.
 * If level = 1, it will be the same as the normal average.
 * Ref: https://en.wikipedia.org/wiki/Generalized_mean
 *
 * @param  {...number} args - The numbers to average, followed by an options object.
 * @param {Object} args[args.length - 1] - The options object containing the level and round_ndigits.
 * @returns {number} The generalized mean rounded to the specified number of digits.
 *
 * Example
 * -------
 * generalized_mean(1, 2, 3, { level: 1, round_ndigits: 4 })  // returns 2.0000
 */
function generalized_mean(...args) {
    if (args.length === 0) {
        throw new Error("At least one numeric argument and an options object with property 'level' are required.");
    }
    // Assume the last argument is the options object with property "level"
    const opts = args[args.length - 1];
    if (typeof opts !== 'object' || opts === null || !('level' in opts)) {
        throw new Error("The last argument must be an options object containing the property 'level'.");
    }
    const levelInput = opts.level;
    const round_ndigits = ('round_ndigits' in opts) ? opts.round_ndigits : 4;
    // Remaining arguments are values to average
    const values = args.slice(0, -1);
    let level = levelInput;
    if (level === 0) {
        level = 1e-6; // Small value to prevent division by zero
    }
    // Note: In JavaScript, -0 is equivalent to 0.
    const n = values.length;
    const sumPower = values.reduce((acc, val) => acc + (Math.pow(val, level) / n), 0);
    const result = Math.pow(sumPower, 1 / level);

    // Rounding the number to the specified number of digits
    if (round_ndigits !== null) {
        if (typeof round_ndigits !== 'number' || round_ndigits < 0) {
            throw new Error("The 'round_ndigits' property must be a non-negative number.");
        }
    }
    const factor = Math.pow(10, round_ndigits);
    return Math.round(result * factor) / factor;
}

// =================================================================================
/**
 * Original Source File: ./src/utils/dict_deepmerge.py
 * 
 * This file contains functions for deep merging dictionaries and handling various data types.    
 */

// --- Constants ---
const _max_depth = 6;
const _min_num_base_item_in_layer = 12;
const _max_num_base_item_in_layer = 768;
const _max_num_conf = 100;
const _max_total_items_per_default_conf = (() => {
    let total = 0;
    for (let depth = 1; depth <= _max_depth; depth++) {
        total += Math.max(_min_num_base_item_in_layer, Math.floor(_max_num_base_item_in_layer / (4 ** depth)));
    }
    return total;
})();
const _max_total_items_per_addition_conf = (num_args) => 32 * Math.max(num_args, _max_num_conf);

// Actions for immutable types (level1) and copy actions
// Possible values (as strings): 'override', 'bypass', 'terminate'
// For tuple actions: 'copy', 'deepcopy'
// For mutable action: 'copy' (default) or others
// For list conflict: 'copy', 'extend', etc. (see Python docstring)

// --- Helpers ---
// Custom error types for clarity.
class RecursionError extends Error {
    constructor(message) {
        super(message);
        this.name = "RecursionError";
    }
}

// Cached computation of maximum items allowed at a given depth.
const _max_num_items_in_depth_cache = new Map();
function _max_num_items_in_depth(depth) {
    if (_max_num_items_in_depth_cache.has(depth)) {
        return _max_num_items_in_depth_cache.get(depth);
    }
    const value = Math.max(_min_num_base_item_in_layer, Math.floor(_max_num_base_item_in_layer / (4 ** depth)));
    _max_num_items_in_depth_cache.set(depth, value);
    return value;
}

// Compute depth count: for objects and arrays.
function _depth_count(a) {
    if (a !== null && typeof a === "object") {
        let values;
        if (Array.isArray(a)) {
            values = a;
        } else {
            values = Object.values(a);
        }
        if (values.length === 0) {
            return 0;
        }
        return 1 + Math.max(...values.map(_depth_count));
    }
    return 0;
}

// Compute total number of items recursively in an object.
function _item_total_count(a) {
    if (a !== null && typeof a === "object") {
        let count = Array.isArray(a) ? a.length : Object.keys(a).length;
        let values;
        if (Array.isArray(a)) {
            values = a;
        } else {
            values = Object.values(a);
        }
        for (const v of values) {
            count += _item_total_count(v);
        }
        return count;
    }
    return 0;
}

// A simple shallow copy function. For arrays and plain objects.
function _copy(value) {
    if (Array.isArray(value)) {
        return value.slice();
    } else if (value !== null && typeof value === "object") {
        return Object.assign({}, value);
    }
    return value;
}

// A simple deep copy function using JSON methods.
function _deepcopy(value) {
    // Note: This works if the object is JSON-compatible.
    return JSON.parse(JSON.stringify(value));
}

/**
 * Performs the trigger update on the result for a given key and value using the specified trigger.
 *
 * @param {Object} result - The target object.
 * @param {*} key - The key to update.
 * @param {*} value - The value to update with.
 * @param {string} trigger - The trigger action.
 */
function _trigger_update(result, key, value, trigger) {
    if (trigger === 'override') {
        result[key] = value;
    } else if (trigger === 'bypass') {
        // Do nothing
    } else if (trigger === 'terminate') {
        delete result[key];
    } else if (trigger === 'copy') {
        result[key] = _copy(value);
    } else if (trigger === 'deepcopy') {
        result[key] = _deepcopy(value);
    } else if (trigger === 'extend') {
        // Assuming result[key] is an array:
        result[key] = result[key].concat(value);
    } else if (trigger === 'extend-copy') {
        result[key] = result[key].concat(_copy(value));
    } else if (trigger === 'extend-deepcopy') {
        result[key] = result[key].concat(_deepcopy(value));
    }
    return;
}

/**
 * Recursively merges and updates two dictionaries.
 *
 * @param {Object} a - The base object.
 * @param {Object} b - The overriding object.
 * @param {Object} result - The output object (may be a or its deepcopy based on inline_source).
 * @param {Array<string>} path - The current key path.
 * @param {number} merged_index_item - Index used for error messages.
 * @param {number} curdepth - Current recursion depth.
 * @param {number} maxdepth - Maximum recursion depth.
 * @param {string} not_available_immutable_action
 * @param {string} available_immutable_action
 * @param {string} not_available_immutable_tuple_action
 * @param {string} available_immutable_tuple_action
 * @param {string} not_available_mutable_action
 * @param {string} list_conflict_action
 * @param {boolean} skiperror
 * @returns {Object} The merged result.
 * @throws {Error} When conflicts occur (unless skiperror is true).
 */
function _deepmerge(
    a, b, result, path, merged_index_item, curdepth, maxdepth,
    not_available_immutable_action, available_immutable_action,
    not_available_immutable_tuple_action, available_immutable_tuple_action,
    not_available_mutable_action, list_conflict_action,
    skiperror = false
) {
    if (curdepth >= maxdepth) {
        throw new RecursionError(`The depth of the dictionary (= ${curdepth}) exceeds the maximum depth (= ${maxdepth}).`);
    }
    curdepth += 1;
    const max_num_items_allowed = _max_num_items_in_depth(curdepth);
    if ((Object.keys(a).length + Object.keys(b).length) > (2 * max_num_items_allowed)) {
        throw new RecursionError(`The number of items in the dictionary exceeds twice maximum limit (= ${max_num_items_allowed}).`);
    }
    // For each key in b:
    for (const bkey in b) {
        path.push(bkey);
        const bvalue = b[bkey];
        if (!(bkey in a)) {
            // Key not present in a.
            if (bvalue === null || ["number", "string", "boolean"].includes(typeof bvalue)) {
                _trigger_update(result, bkey, bvalue, not_available_immutable_action);
            } else if (typeof bvalue === "object") {
                _trigger_update(result, bkey, bvalue, not_available_mutable_action);
            }
            else if (!skiperror) {
                throw new TypeError(`Conflict at ${path.slice(0, curdepth).join("->")} in the #${merged_index_item} configuration.`);
            }
        } else {
            let abkey_value = a[bkey];
            // Both are primitives (immutable)
            if (
                (abkey_value === null || ["number", "string", "boolean"].includes(typeof abkey_value)) &&
                (bvalue === null || ["number", "string", "boolean"].includes(typeof bvalue))
            ) {
                _trigger_update(result, bkey, bvalue, available_immutable_action);
            }
            // One is primitive and the other is object — heterogeneous types.
            else if (
                ((abkey_value === null || ["number", "string", "boolean"].includes(typeof abkey_value)) &&
                 (bvalue !== null && typeof bvalue === "object")) ||
                ((abkey_value !== null && typeof abkey_value === "object") &&
                 (bvalue === null || ["number", "string", "boolean"].includes(typeof bvalue)))
            ) {
                if (!skiperror) {
                    throw new TypeError(`Conflict at ${path.slice(0, curdepth).join("->")} in the #${merged_index_item} configuration as value in both sides are heterogeneous of type`);
                }
            }
            // Both are objects (mutable)
            else if ((abkey_value !== null && typeof abkey_value === "object") && (bvalue !== null && typeof bvalue === "object")) {
                // If both are plain objects, recursively merge.
                if (!Array.isArray(abkey_value) && !Array.isArray(bvalue)) {
                    _deepmerge(
                        abkey_value, bvalue, result[bkey], [...path],
                        merged_index_item, curdepth, maxdepth, skiperror,
                        not_available_immutable_action, available_immutable_action,
                        not_available_immutable_tuple_action, available_immutable_tuple_action,
                        not_available_mutable_action, list_conflict_action
                    );
                }
                // If both are arrays, trigger list conflict update.
                else if (Array.isArray(abkey_value) && Array.isArray(bvalue)) {
                    _trigger_update(result, bkey, bvalue, list_conflict_action);
                }
                else if (!skiperror) {
                    throw new TypeError(`Conflict at ${path.slice(0, curdepth).join("->")} in the #${merged_index_item} configuration as value in both sides are heterogeneous or unsupported types`);
                }
            }
            // If the values are equal, do nothing.
            else if (JSON.stringify(abkey_value) === JSON.stringify(bvalue)) {
                // Do nothing.
            }
            // Edge-case: values not equal
            else if (!skiperror) {
                throw new Error(`Conflict at ${path.slice(0, curdepth).join("->")} in the #${merged_index_item} configuration. It can be the result of edge-case or non-supported type`);
            }
        }
        // Pop the last value
        path.pop();
    }
    return result;
}

/**
 * Recursively merges and updates two or more dictionaries.
 * The result is always a new deep copy of the dictionaries (unless inline_source is true).
 *
 * Parameters
 * ----------
 * a : Object
 *     The first dictionary to be merged (usually the default configuration).
 *
 * args : Object[]
 *     The other dictionaries to be merged (custom configurations overriding defaults).
 *
 * Keyword Parameters
 * ------------------
 * inline_source : boolean (default: true)
 *     Whether to merge in-place on source object a.
 *
 * inline_target : boolean (default: false)
 *     Whether to merge in-place on the additional configurations.
 *
 * maxdepth : number (default: _max_depth // 2 + 1)
 *     The maximum depth of the dictionary to be merged.
 *
 * not_available_immutable_action : string (default: 'override')
 *     Action when the key is not present in a for immutable types.
 *
 * available_immutable_action : string (default: 'override')
 *     Action when the key is available in a for immutable types.
 *
 * not_available_immutable_tuple_action : string (default: 'copy')
 *     Action when the key is not present in a for tuple types.
 *
 * available_immutable_tuple_action : string (default: 'copy')
 *     Action when the key is available in a for tuple types.
 *
 * not_available_mutable_action : string (default: 'copy')
 *     Action when the key is not present in a for mutable types.
 *
 * list_conflict_action : string (default: 'copy')
 *     Action when merging lists.
 *
 * skiperror : boolean (default: false)
 *     If true, skip errors on conflict.
 *
 * Returns
 * -------
 * Object
 *     The merged dictionary.
 *
 * Throws
 * ------
 * RecursionError
 *     When the depth of the dictionary exceeds the maximum allowed.
 *
 * TypeError
 *     When conflicting types are found.
 */
function deepmerge(
    a,
    ...args
) {
    // Optional parameters with defaults:
    let {
        inline_source = true,
        inline_target = false,
        maxdepth = Math.floor(_max_depth / 2) + 1,
        not_available_immutable_action = 'override',
        available_immutable_action = 'override',
        not_available_immutable_tuple_action = 'copy',
        available_immutable_tuple_action = 'copy',
        not_available_mutable_action = 'copy',
        list_conflict_action = 'copy',
        skiperror = false
    } = arguments.length > 1 && typeof arguments[arguments.length - 1] === "object" ? args.pop() : {};

    if (args.length === 0) {
        return inline_source ? a : _deepcopy(a);
    }
    if (!(1 <= maxdepth && maxdepth <= _max_depth)) {
        throw new Error(`The depth of the dictionary exceeds the maximum depth allowed (=${_max_depth}).`);
    }
    if (args.length > _max_num_conf) {
        throw new Error(`The number of dictionaries to be merged exceeds the maximum limit (=${_max_num_conf}).`);
    }
    const a_maxdepth = _depth_count(a);
    if (a_maxdepth > maxdepth) {
        throw new Error(`The depth of the first map (=${a_maxdepth}) exceeds the maximum depth (=${maxdepth}).`);
    }
    const a_maxitem = _item_total_count(a);
    if (a_maxitem > _max_total_items_per_default_conf) {
        throw new Error(`The number of items in the first map (=${a_maxitem}) exceeds the maximum limit (=${_max_total_items_per_default_conf}).`);
    }
    let arg_maxitem = 0;
    for (const arg of args) {
        const arg_maxdepth = _depth_count(arg);
        if (arg_maxdepth > maxdepth) {
            throw new Error(`The depth of a map (=${arg_maxdepth}) exceeds the maximum depth (=${maxdepth}).`);
        }
        arg_maxitem += _item_total_count(arg);
    }
    if (arg_maxitem > _max_total_items_per_addition_conf(args.length)) {
        throw new Error(`The number of items in the map (=${arg_maxitem}) exceeds the maximum limit (=${_max_total_items_per_addition_conf(args.length)}).`);
    }
    let result = inline_source ? a : _deepcopy(a);
    args.forEach((arg, idx) => {
        const target = inline_target ? arg : _deepcopy(arg);
        result = _deepmerge(
            result,
            target,
            result,
            [],
            idx,
            0,
            maxdepth,
            not_available_immutable_action,
            available_immutable_action,
            not_available_immutable_tuple_action,
            available_immutable_tuple_action,
            not_available_mutable_action,
            list_conflict_action,
            skiperror
        );
    });
    return result;
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
    return profiles;
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
    return profiles;
};

// ================================================================================
/**
 * Original Source File: ./src/tuner/data/sizing.py
 */
// --------------------------------------------------------------------------
// ENUM choices
const SIZE_PROFILE = ['mini', 'medium', 'large', 'mall', 'bigt'];
const _ascending_specs = {
    size: SIZE_PROFILE,
    vcpu_min: [1, 2, 6, 12, 32],
    vcpu_max: [4, 8, 16, 48, 128],
    ram_gib_min: [2, 8, 24, 48, 128],
    ram_gib_max: [16, 32, 64, 192, 512],
    storage_gib_max: [50, 300, 1024, 5120, 32768],
    network_mbps_max: [500, 1000, 5000, 12500, 30000],
};
function _str_to_num(value) {
    return _ascending_specs.size.indexOf(value);
}

// PG_SIZING: Represents a PostgreSQL sizing profile
class PG_SIZING {
    constructor(value) {
        this.value = value; // one of 'mini', 'medium', etc.
    }

    num() {
        return _str_to_num(this.value);
    }

    lt(other) {
        return this.num() < other.num();
    }

    eq(other) {
        return this.num() === other.num();
    }
}
// Define the PG_SIZING enum members
PG_SIZING.MINI = new PG_SIZING(SIZE_PROFILE[0]);
PG_SIZING.MEDIUM = new PG_SIZING(SIZE_PROFILE[1]);
PG_SIZING.LARGE = new PG_SIZING(SIZE_PROFILE[2]);
PG_SIZING.MALL = new PG_SIZING(SIZE_PROFILE[3]);
PG_SIZING.BIGT = new PG_SIZING(SIZE_PROFILE[4]);

// ----------------------------------------------------------------
// PG_DISK_SIZING: Represents a PostgreSQL disk sizing profile
class PG_DISK_SIZING {
    constructor(code, throughput, iops) {
        this._code = code;
        this._throughput = throughput;
        this._iops = iops;
    }

    diskCode() {
        return this._code;
    }

    throughput() {
        return this._throughput;
    }

    iops() {
        return this._iops;
    }

    _checkDiskType(diskType) {
        const dt = diskType.toLowerCase();
        if (!PG_DISK_SIZING._diskTypeListV2().includes(dt)) {
            throw new Error(`Disk type ${dt} is not available`);
        }
        return this._code.startsWith(dt);
    }

    // Static helper methods and caching
    static _diskTypeListV1() {
        return ['hdd', 'san', 'ssd', 'nvmebox', 'nvmepciev3', 'nvmepciev4', 'nvmepciev5'];
    }

    static _diskTypeListV2() {
        return ['hdd', 'san', 'ssd', 'nvmebox', 'nvmepciev3', 'nvmepciev4', 'nvmepciev5', 'nvmepcie', 'nvme'];
    }

    static _all() {
        return PG_DISK_SIZING.ALL;
    }

    static _list(diskType = null, performanceType = null) {
        let result = PG_DISK_SIZING._all().filter(disk => {
            return diskType === null || disk._checkDiskType(diskType);
        });
        if (performanceType !== null) {
            const keyFn = performanceType === THROUGHPUT ?
                (d) => [d.throughput(), d.iops()] :
                (d) => [d.iops(), d.throughput()];
            result.sort((a, b) => {
                const ka = keyFn(a), kb = keyFn(b);
                return ka[0] - kb[0] || ka[1] - kb[1];
            });
        }
        return result;
    }

    static _findMidpoints(disks, performanceType) {
        const len = disks.length;
        const midpoint = Math.floor(len / 2);
        if (len % 2 === 0) {
            const disk1 = disks[midpoint - 1];
            const disk2 = disks[midpoint];
            return performanceType === THROUGHPUT ?
                (disk1.throughput() + disk2.throughput()) / 2 :
                (disk1.iops() + disk2.iops()) / 2;
        } else {
            const disk = disks[midpoint];
            return performanceType === THROUGHPUT ? disk.throughput() : disk.iops();
        }
    }

    static _getBound(performanceType, disk01, disk02) {
        const diskTable = PG_DISK_SIZING._list(null, performanceType);
        let lowerBound;
        if (disk01 instanceof PG_DISK_SIZING) {
            const idx = diskTable.indexOf(disk01);
            const prev = idx > 0 ? diskTable[idx - 1] : disk01;
            lowerBound = disk01 === prev ? 0 :
                (performanceType === THROUGHPUT ?
                    (disk01.throughput() + prev.throughput()) / 2 :
                    (disk01.iops() + prev.iops()) / 2);
        } else {
            lowerBound = disk01;
        }

        let upperBound;
        if (disk02 instanceof PG_DISK_SIZING) {
            const idx = diskTable.indexOf(disk02);
            const next = idx < diskTable.length - 1 ? diskTable[idx + 1] : disk02;
            upperBound = disk02 === next ?
                2 * (performanceType === THROUGHPUT ? disk02.throughput() : disk02.iops()) :
                (performanceType === THROUGHPUT ?
                    (disk02.throughput() + next.throughput()) / 2 :
                    (disk02.iops() + next.iops()) / 2);
        } else {
            upperBound = disk02;
        }

        if (upperBound < lowerBound) {
            [lowerBound, upperBound] = [upperBound, lowerBound];
        }

        return [Math.floor(lowerBound), Math.ceil(upperBound)];
    }

    static matchBetween(performance, performanceType, disk01, disk02) {
        const diskTable = PG_DISK_SIZING._list(null, performanceType);
        const lastDisk = diskTable[diskTable.length - 1];
        if (performanceType === THROUGHPUT && performance >= lastDisk.throughput()) {
            return true;
        } else if (performanceType !== THROUGHPUT && performance >= lastDisk.iops()) {
            return true;
        }
        const [lowerBound, upperBound] = PG_DISK_SIZING._getBound(performanceType, disk01, disk02);
        return performance >= lowerBound && performance < upperBound;
    }

    static matchDiskSeries(performance, performanceType, diskType, interval = 'all') {
        const disks = PG_DISK_SIZING._list(diskType, performanceType);
        if (!disks.length) {
            throw new Error(`No disk type found when matching ${diskType}`);
        }
        if (interval === 'all') {
            return PG_DISK_SIZING.matchBetween(performance, performanceType, disks[0], disks[disks.length - 1]);
        }
        if (interval === 'weak') {
            return PG_DISK_SIZING.matchBetween(performance, performanceType, disks[0], disks[Math.floor(disks.length / 2)]);
        } else { // 'strong'
            return PG_DISK_SIZING.matchBetween(performance, performanceType, disks[Math.floor(disks.length / 2)], disks[disks.length - 1]);
        }
    }

    static matchOneDisk(performance, performanceType, disk) {
        return PG_DISK_SIZING.matchBetween(performance, performanceType, disk, disk);
    }

    static matchDiskSeriesInRange(performance, performanceType, disk01Type, disk02Type) {
        if (disk01Type === disk02Type) {
            return PG_DISK_SIZING.matchDiskSeries(performance, performanceType, disk01Type);
        }
        const disk01s = PG_DISK_SIZING._list(disk01Type, performanceType);
        const disk02s = PG_DISK_SIZING._list(disk02Type, performanceType);
        if (!disk01s.length || !disk02s.length) {
            throw new Error(`No disk type found when matching ${disk01Type} and ${disk02Type}`);
        }
        const diskCollection = [
            disk01s[0],
            disk01s[disk01s.length - 1],
            disk02s[0],
            disk02s[disk02s.length - 1]
        ];
        const sortFn = performanceType === THROUGHPUT ?
            (a, b) => a.throughput() - b.throughput() || a.iops() - b.iops() :
            (a, b) => a.iops() - b.iops() || a.throughput() - b.throughput();
        diskCollection.sort(sortFn);
        return PG_DISK_SIZING.matchBetween(performance, performanceType, diskCollection[0], diskCollection[diskCollection.length - 1]);
    }
}

// Define the PG_DISK_SIZING enum members
// SATA HDDs
PG_DISK_SIZING.HDDv1 = new PG_DISK_SIZING('hddv1', 100, 250);
PG_DISK_SIZING.HDDv2 = new PG_DISK_SIZING('hddv2', 200, K10);
PG_DISK_SIZING.HDDv3 = new PG_DISK_SIZING('hddv3', 260, 2500);

// SAN/NAS SSDs
PG_DISK_SIZING.SANv1 = new PG_DISK_SIZING('sanv1', 300, 5 * K10);
PG_DISK_SIZING.SANv2 = new PG_DISK_SIZING('sanv2', 330, 8 * K10);
PG_DISK_SIZING.SANv3 = new PG_DISK_SIZING('sanv3', 370, 12 * K10);
PG_DISK_SIZING.SANv4 = new PG_DISK_SIZING('sanv4', 400, 16 * K10);

// SATA SSDs (Local)
PG_DISK_SIZING.SSDv1 = new PG_DISK_SIZING('ssdv1', 450, 20 * K10);
PG_DISK_SIZING.SSDv2 = new PG_DISK_SIZING('ssdv2', 500, 30 * K10);
PG_DISK_SIZING.SSDv3 = new PG_DISK_SIZING('ssdv3', 533, 40 * K10);
PG_DISK_SIZING.SSDv4 = new PG_DISK_SIZING('ssdv4', 566, 50 * K10);
PG_DISK_SIZING.SSDv5 = new PG_DISK_SIZING('ssdv5', 600, 60 * K10);

// Remote NVMe SSD (Usually the NVMe Box)
PG_DISK_SIZING.NVMeBOXv1 = new PG_DISK_SIZING('nvmeboxv1', 800, 80 * K10);
PG_DISK_SIZING.NVMeBOXv2 = new PG_DISK_SIZING('nvmeboxv2', 1000, 100 * K10);
PG_DISK_SIZING.NVMeBOXv3 = new PG_DISK_SIZING('nvmeboxv3', 1400, 120 * K10);
PG_DISK_SIZING.NVMeBOXv4 = new PG_DISK_SIZING('nvmeboxv4', 1700, 140 * K10);

// NVMe PCIe Gen 3 SSDs
PG_DISK_SIZING.NVMePCIev3x4v1 = new PG_DISK_SIZING('nvmepciev3x4v1', 2000, 150 * K10);
PG_DISK_SIZING.NVMePCIev3x4v2 = new PG_DISK_SIZING('nvmepciev3x4v2', 2500, 200 * K10);
PG_DISK_SIZING.NVMePCIev3x4v3 = new PG_DISK_SIZING('nvmepciev3x4v3', 3000, 250 * K10);
PG_DISK_SIZING.NVMePCIev3x4v4 = new PG_DISK_SIZING('nvmepciev3x4v4', 3500, 300 * K10);
PG_DISK_SIZING.NVMePCIev3x4v5 = new PG_DISK_SIZING('nvmepciev3x4v5', 4000, 350 * K10);
PG_DISK_SIZING.NVMePCIev3x4v6 = new PG_DISK_SIZING('nvmepciev3x4v6', 4500, 400 * K10);

// NVMe PCIe Gen 4 SSDs
PG_DISK_SIZING.NVMePCIev4x4v1 = new PG_DISK_SIZING('nvmepciev4x4v1', 4500, 300 * K10);
PG_DISK_SIZING.NVMePCIev4x4v2 = new PG_DISK_SIZING('nvmepciev4x4v2', 5000, 375 * K10);
PG_DISK_SIZING.NVMePCIev4x4v3 = new PG_DISK_SIZING('nvmepciev4x4v3', 5500, 450 * K10);
PG_DISK_SIZING.NVMePCIev4x4v4 = new PG_DISK_SIZING('nvmepciev4x4v4', 6000, 525 * K10);
PG_DISK_SIZING.NVMePCIev4x4v5 = new PG_DISK_SIZING('nvmepciev4x4v5', 6500, 600 * K10);
PG_DISK_SIZING.NVMePCIev4x4v6 = new PG_DISK_SIZING('nvmepciev4x4v6', 7000, 700 * K10);

// NVMe PCIe Gen 5 SSDs
PG_DISK_SIZING.NVMePCIev5x4v1 = new PG_DISK_SIZING('nvmepciev5x4v1', 7000, 750 * K10);
PG_DISK_SIZING.NVMePCIev5x4v2 = new PG_DISK_SIZING('nvmepciev5x4v2', 8500, 850 * K10);
PG_DISK_SIZING.NVMePCIev5x4v3 = new PG_DISK_SIZING('nvmepciev5x4v3', 9500, 950 * K10);
PG_DISK_SIZING.NVMePCIev5x4v4 = new PG_DISK_SIZING('nvmepciev5x4v4', 11000, 1100 * K10);
PG_DISK_SIZING.NVMePCIev5x4v5 = new PG_DISK_SIZING('nvmepciev5x4v5', 12500, 1250 * K10);
PG_DISK_SIZING.NVMePCIev5x4v6 = new PG_DISK_SIZING('nvmepciev5x4v6', 14000, 1400 * K10);

// Populate ALL list
PG_DISK_SIZING.ALL = [
    PG_DISK_SIZING.HDDv1, PG_DISK_SIZING.HDDv2, PG_DISK_SIZING.HDDv3,
    PG_DISK_SIZING.SANv1, PG_DISK_SIZING.SANv2, PG_DISK_SIZING.SANv3, PG_DISK_SIZING.SANv4,
    PG_DISK_SIZING.SSDv1, PG_DISK_SIZING.SSDv2, PG_DISK_SIZING.SSDv3, PG_DISK_SIZING.SSDv4, PG_DISK_SIZING.SSDv5,
    PG_DISK_SIZING.NVMeBOXv1, PG_DISK_SIZING.NVMeBOXv2, PG_DISK_SIZING.NVMeBOXv3, PG_DISK_SIZING.NVMeBOXv4,
    PG_DISK_SIZING.NVMePCIev3x4v1, PG_DISK_SIZING.NVMePCIev3x4v2, PG_DISK_SIZING.NVMePCIev3x4v3,
    PG_DISK_SIZING.NVMePCIev3x4v4, PG_DISK_SIZING.NVMePCIev3x4v5, PG_DISK_SIZING.NVMePCIev3x4v6,
    PG_DISK_SIZING.NVMePCIev4x4v1, PG_DISK_SIZING.NVMePCIev4x4v2, PG_DISK_SIZING.NVMePCIev4x4v3,
    PG_DISK_SIZING.NVMePCIev4x4v4, PG_DISK_SIZING.NVMePCIev4x4v5, PG_DISK_SIZING.NVMePCIev4x4v6,
    PG_DISK_SIZING.NVMePCIev5x4v1, PG_DISK_SIZING.NVMePCIev5x4v2, PG_DISK_SIZING.NVMePCIev5x4v3,
    PG_DISK_SIZING.NVMePCIev5x4v4, PG_DISK_SIZING.NVMePCIev5x4v5, PG_DISK_SIZING.NVMePCIev5x4v6,
];

// =================================================================================
/**
 * Original Source File: ./src/tuner/data/disks.py
 */
/**
 * Convert a disk performance value from string to numeric.
 *
 * @param {string|number} value - The disk performance value.
 * @param {string} mode - Mode (expected to be RANDOM_IOPS or THROUGHPUT).
 * @returns {number} The performance value as a number.
 * @throws {Error} If the value is not a string or a number.
 */
function _string_disk_to_performance(value, mode) {
    if (typeof value === 'number') {
        return value;
    }
    if (typeof value !== 'string') {
        const msg = 'The disk performance value is not a string or integer.';
        throw new Error(msg);
    }
    if (value.trim().match(/^\d+$/)) {
        return parseInt(value, 10);
    }
    // Get the disk based on its name:
    for (const disk of PG_DISK_SIZING) {
        const disk_code = disk.disk_code();
        if (disk_code === value) {
            return (mode === RANDOM_IOPS) ? disk.iops() : disk.throughput();
        } else if (disk_code.startsWith(value) && disk.disk_code().endsWith('v1')) {
            return (mode === RANDOM_IOPS) ? disk.iops() : disk.throughput();
        }
    }
    // If the disk is not found, fallback to the default value:
    return (mode === RANDOM_IOPS) ? PG_DISK_SIZING.SANv1.iops() : PG_DISK_SIZING.SANv1.throughput();
}

/**
 * PG_DISK_PERF stores the disk performance configuration.
 *
 * Properties:
 *   random_iops_spec - The random IOPS metric of a single disk. If provided as a string,
 *                      it will be resolved via _string_disk_to_performance.
 *   random_iops_scale_factor - Scale factor for random IOPS (default: 0.9).
 *   throughput_spec - The read specification of the disk performance. If provided as a string,
 *                     it will be resolved via _string_disk_to_performance.
 *   throughput_scale_factor - Scale factor for throughput (default: 0.9).
 *   per_scale_in_raid - Performance scale factor in RAID configuration (default: 0.75).
 *   num_disks - Number of disks in the system (default: 1).
 *   disk_usable_size - The usable size of the disk system in bytes (default: 20 * Gi).
 *
 * Methods:
 *   model_post_init - Resolves string specifications to numeric values.
 *   raid_scale_factor - Cached computation for RAID scale factor.
 *   single_perf - Cached computation for single disk performance.
 *   perf - Computes the RAID-adjusted performance.
 *
 * Static Methods:
 *   iops_to_throughput - Converts IOPS to throughput.
 *   throughput_to_iops - Converts throughput to IOPS.
 *
 * @param {Object} data A plain object with the tuning properties.
 */
class PG_DISK_PERF {
    constructor(data = {}) {
        // Set defaults. Assumes PG_DISK_SIZING, RANDOM_IOPS, THROUGHPUT, Gi, Mi, DB_PAGE_SIZE are defined globally.
        this.random_iops_spec = (typeof data.random_iops_spec !== 'undefined') ?
            data.random_iops_spec : PG_DISK_SIZING.SANv1.iops();
        this.random_iops_scale_factor = (typeof data.random_iops_scale_factor !== 'undefined') ?
            data.random_iops_scale_factor : 0.9;
        this.throughput_spec = (typeof data.throughput_spec !== 'undefined') ?
            data.throughput_spec : PG_DISK_SIZING.SANv1.throughput();
        this.throughput_scale_factor = (typeof data.throughput_scale_factor !== 'undefined') ?
            data.throughput_scale_factor : 0.9;
        this.per_scale_in_raid = (typeof data.per_scale_in_raid !== 'undefined') ?
            data.per_scale_in_raid : 0.75;
        this.num_disks = (typeof data.num_disks !== 'undefined') ?
            data.num_disks : 1;
        this.disk_usable_size = (typeof data.disk_usable_size !== 'undefined') ?
            data.disk_usable_size : 20 * Gi;
        // Internal cache properties
        this._raid_scale_factor = undefined;
        this._single_perf = undefined;
        // Post initialization to resolve any string specifications
        this.model_post_init();
    }

    /**
     * Post initialization method to resolve string disk performance specifications.
     *
     * If random_iops_spec or throughput_spec are strings, they are converted using _string_disk_to_performance.
     */
    model_post_init() {
        if (typeof this.random_iops_spec === 'string') {
            this.random_iops_spec = _string_disk_to_performance(this.random_iops_spec, RANDOM_IOPS);
        }
        if (typeof this.throughput_spec === 'string') {
            this.throughput_spec = _string_disk_to_performance(this.throughput_spec, THROUGHPUT);
        }
    }

    /**
     * Cached property: Computes the RAID scale factor.
     *
     * @returns {number} The RAID scale factor rounded to 2 decimal places.
     */
    raid_scale_factor() {
        if (this._raid_scale_factor === undefined) {
            const factor = Math.max(1.0, (this.num_disks - 1) * this.per_scale_in_raid + 1.0);
            this._raid_scale_factor = Math.round(factor * 100) / 100;
        }
        return this._raid_scale_factor;
    }

    /**
     * Cached property: Computes the single disk performance.
     *
     * @returns {Array<number>} An array where element 0 is throughput and element 1 is IOPS.
     */
    single_perf() {
        if (this._single_perf === undefined) {
            const s_tput = Math.floor(this.throughput_spec * this.throughput_scale_factor);
            const s_iops = Math.floor(this.random_iops_spec * this.random_iops_scale_factor);
            this._single_perf = [s_tput, s_iops];
        }
        return this._single_perf;
    }

    /**
     * Compute the RAID-adjusted performance.
     *
     * @returns {Array<number>} An array where element 0 is total throughput and element 1 is total IOPS.
     */
    perf() {
        const raid_sf = this.raid_scale_factor();
        const [s_tput, s_iops] = this.single_perf();
        return [Math.floor(s_tput * raid_sf), Math.floor(s_iops * raid_sf)];
    }

    /**
     * Static method: Convert IOPS to throughput.
     *
     * IOPS is measured by the number of 8 KiB blocks.
     * Throughput is measured in MiB.
     *
     * @param {number} iops - The IOPS value.
     * @returns {number} The throughput value.
     */
    static iops_to_throughput(iops) {
        return iops * DB_PAGE_SIZE / Mi;
    }

    /**
     * Static method: Convert throughput to IOPS.
     *
     * Throughput is measured in MiB.
     * IOPS is measured by the number of 8 KiB blocks.
     *
     * @param {number} throughput - The throughput value.
     * @returns {number} The IOPS value.
     */
    static throughput_to_iops(throughput) {
        return throughput * Math.floor(Mi / DB_PAGE_SIZE);
    }
}

// =================================================================================
/**
 * Original Source File: ./src/tuner/data/scope.js
 */

// PG_SCOPE: The applied scope for each of the tuning items.
const PG_SCOPE = Object.freeze({
    VM: 'vm',
    CONNECTION: 'conn',
    FILESYSTEM: 'fs',
    MEMORY: 'memory',
    DISK_IOPS: 'iops',
    NETWORK: 'net',
    LOGGING: 'log',
    QUERY_TUNING: 'query',
    MAINTENANCE: 'maint',
    ARCHIVE_RECOVERY_BACKUP_RESTORE: 'backup',
    EXTRA: 'extra',
    OTHERS: 'others',
});

// PGTUNER_SCOPE: The internal managed scope for the tuning items.
class PGTUNER_SCOPE {
    constructor(value) {
        this.value = value;
    }

    disclaimer() {
        // For simplicity, use the local system time.
        // If GetTimezone is available, you can adjust the time accordingly.
        const dt = new Date().toLocaleString();
        if (this.value === 'kernel_sysctl') {
            return `# Read this disclaimer before applying the tuning result
# ============================================================
# ${APP_NAME_UPPER}-v${__VERSION__}: The tuning is started at ${dt} 
# -> Target Scope: ${this.value}
# DISCLAIMER: This kernel tuning options is based on our experience, and should not be 
# applied directly to the system. Please consult with your database administrator, system
# administrator, or software/system delivery manager before applying the tuning result.
# HOWTO: It is recommended to apply the tuning result by copying the file and pasting it 
# as the final configuration under the /etc/sysctl.d/* directory rather than overwrite 
# previous configuration. Please DO NOT apply the tuning result directly to the system 
# by any means, and ensure that the system is capable of rolling back the changes if the
# system is not working as expected.
# ============================================================
`;
        } else if (this.value === 'database_config') {
            return `# Read this disclaimer before applying the tuning result
# ============================================================
# ${APP_NAME_UPPER}-v${__VERSION__}: The tuning is started at ${dt} 
# -> Target Scope: ${this.value}
# DISCLAIMER: This database tuning options is based on our experience, and should not be 
# applied directly to the system. There is ZERO guarantee that this tuning guideline is 
# the best for your system, for every tables, indexes, workload, and queries. Please 
# consult with your database administrator or software/system delivery manager before
# applying the tuning result.
# HOWTO: It is recommended to apply the tuning result under the /etc/postgresql/* directory 
# or inside the $PGDATA/conf/* or $PGDATA/* directory depending on how you start your
# PostgreSQL server. Please double check the system from the SQL interactive sessions to 
# ensure things are working as expected. Whilst it is possible to start the PostgreSQL 
# server with the new configuration, it could result in lost of configuration (such as new 
# version update, unknown configuration changes, extension or external configuration from 
# 3rd-party tools, or no inherited configuration from the parent directory). It is not 
# recommended to apply the tuning result directly to the system without a proper backup, 
# and ensure the system is capable of rolling back the changes if the system is not working.
# ============================================================
`;
        }
        return "";
    }
}

// Define enum instances for PGTUNER_SCOPE
PGTUNER_SCOPE.KERNEL_SYSCTL = new PGTUNER_SCOPE('kernel_sysctl');
PGTUNER_SCOPE.KERNEL_BOOT = new PGTUNER_SCOPE('kernel_boot');
PGTUNER_SCOPE.DATABASE_CONFIG = new PGTUNER_SCOPE('database_config');


// =================================================================================
/**
 * Original Source File: ./src/tuner/data/optmode.py
 * 
 */
/**
 * The PostgreSQL optimization mode during workload, maintenance, logging experience for DEV/DBA,
 * and possibly other options. Note that this tuning profile should not be relied on as a single source
 * of truth.
 *
 * Parameters:
 * ----------
 *
 * NONE: string = "none"
 *     This mode bypasses the second phase of the tuning process and applies general tuning only.
 *
 * SPIDEY: string = "lightweight"
 *     Suitable for servers with limited resources, applying an easy, basic workload optimization profile.
 *
 * OPTIMUS_PRIME: string = "general"
 *     Suitable for servers with more resources, balancing between data integrity and performance.
 *
 * PRIMORDIAL: string = "aggressive"
 *     Suitable for servers with more resources, applying an aggressive workload configuration with a focus on data integrity.
 */
class PG_PROFILE_OPTMODE {
    static NONE = "none";
    static SPIDEY = "lightweight";
    static OPTIMUS_PRIME = "general";
    static PRIMORDIAL = "aggressive";

    /**
     * Returns the ordering of the profiles.
     *
     * @returns {Array<string>} An array containing the ordered profile modes.
     */
    static profile_ordering() {
        return [
            PG_PROFILE_OPTMODE.NONE,
            PG_PROFILE_OPTMODE.SPIDEY,
            PG_PROFILE_OPTMODE.OPTIMUS_PRIME,
            PG_PROFILE_OPTMODE.PRIMORDIAL
        ];
    }
}

/**
 * Enumeration of PostgreSQL backup tools.
 *
 * Available values:
 *  - DISK_SNAPSHOT: 'Backup by Disk Snapshot'
 *  - PG_DUMP: 'pg_dump/pg_dumpall: Textual backup'
 *  - PG_BASEBACKUP: 'pg_basebackup [--incremental] or streaming replication (byte-capture change): Byte-level backup'
 *  - PG_LOGICAL: 'pg_logical and alike: Logical replication'
 */
class PG_BACKUP_TOOL {
    static DISK_SNAPSHOT = 'Backup by Disk Snapshot';
    static PG_DUMP = 'pg_dump/pg_dumpall: Textual backup';
    static PG_BASEBACKUP = 'pg_basebackup [--incremental] or streaming replication (byte-capture change): Byte-level backup';
    static PG_LOGICAL = 'pg_logical and alike: Logical replication';

    /**
     * Simulates the __missing__ behavior by returning a matching tool for the given key.
     *
     * @param {string|number} key - The key to search for.
     * @returns {string} The matching backup tool.
     * @throws {Error} If no matching backup tool is found.
     */
    static __missing__(key) {
        if (typeof key === 'string') {
            const k = key.trim().toLowerCase();
            switch (k) {
                case 'disk_snapshot':
                    return PG_BACKUP_TOOL.DISK_SNAPSHOT;
                case 'pg_dump':
                    return PG_BACKUP_TOOL.PG_DUMP;
                case 'pg_basebackup':
                    return PG_BACKUP_TOOL.PG_BASEBACKUP;
                case 'pg_logical':
                    return PG_BACKUP_TOOL.PG_LOGICAL;
                default:
                    throw new Error(`Unknown backup tool: ${key}`);
            }
        } else if (typeof key === 'number') {
            const tools = [
                PG_BACKUP_TOOL.DISK_SNAPSHOT,
                PG_BACKUP_TOOL.PG_DUMP,
                PG_BACKUP_TOOL.PG_BASEBACKUP,
                PG_BACKUP_TOOL.PG_LOGICAL
            ];
            if (key < 0 || key >= tools.length) {
                throw new Error(`Unknown backup tool: ${key}`);
            }
            return tools[key];
        }
        throw new Error(`Unknown backup tool: ${key}`);
    }
}

// ==================================================================================
/**
 * Original Source File: ./src/tuner/data/workload.py
 */
/**
This enum represents some typical workloads or usage patterns that can be used to tune the database.
Options:
-------

# Business Workload
TSR_IOT = 'tst' (Time-Series Data / Streaming)
    - Description: Database usually aggregated with timestamped data points.
    - Transaction Lifespan: Short-lived transactions optimized for high frequency for IoT data.
    - Read/Write Balance: Heavy writes with frequent time-stamped data points. Frequent READ operation (
        usually after 1 - 5 minutes) for monitoring, dashboard display, and alerting.
    - Query Complexity: Often simple reads with time-based filtering and aggregations (non-complex data 
        transformation, joins, and aggregations).
    - Data Access (READ) Pattern: Sequential access to time-ordered data.
    - Insertion (WRITE) Pattern: Append-only; constant insertion of new, timestamped records; Continuous 
        or batch insertion of log entries.
    - Typical Usage: Monitoring IoT data, and system performance metrics. Log analysis, monitoring, 
        anomaly detection, and security event correlation.

OLTP = 'oltp' (Online Transaction Processing)
    - Description: Traditional OLTP workload with frequent read and write operations.
    - Transaction Lifespan: Short-lived transactions (milliseconds to seconds).
    - Read/Write Balance: Balanced; often read-heavy but includes frequent writes.
    - Query Complexity: Simple read and write queries, usually targeting single rows or small subsets.
    - Data Access (READ) Pattern: Random access to small subsets of data.
    - Insertion (WRITE) Pattern: Constant insertion and updates, with high concurrency.
    - Typical Usage: Applications like banking, e-commerce, and CRM where data changes frequently.

HTAP = 'htap' (Hybrid Transactional/Analytical Processing)
    - Description: Combines OLTP and OLAP workloads in a single database. Analytic workloads are usually financial
        reporting, real-time analytics.
    - Transaction Lifespan: Mix of short transactional and long analytical queries.
    - Read/Write Balance: Balances frequent writes (OLTP) with complex reads (OLAP).
    - Query Complexity: Simple transactional queries along with complex analytical queries.
    - Data Access (READ) Pattern: Random access for OLTP and sequential access for OLAP.
    - Insertion (WRITE) Pattern: Real-time or near real-time inserts, often through streaming or continuous updates.
    - Typical Usage: Real-time dashboards, fraud detection where operational and historical data are combined.

# Internal Management Workload
OLAP = 'olap' (Online Analytical Processing) && TSR_OLAP = 'tsa' (Time-Series Data Analytics)
    - Description: Analytical workload with complex queries and aggregations.
    - Transaction Lifespan: Long-lived, complex queries (seconds to minutes, even HOUR on large database).
    - Read/Write Balance: Read-heavy; few updates or inserts after initial loading.
    - Query Complexity: Complex read queries with aggregations, joins, and large scans.
    - Data Access (READ) Pattern: Sequential access to large data sets.
    - Insertion (WRITE) Pattern: Bulk insertion during ETL processes, usually at scheduled intervals.
    - Typical Usage: Business analytics and reporting where large data volumes are analyzed.

# Specific Workload such as Search, RAG, Geospatial, and Document Indexing
VECTOR = 'vector'
    - Description: Workload operates over vector-based data type such as SEARCH (search toolbar in Azure),
        INDEX (document indexing) and RAG (Retrieval-Augmented Generation), and GEOSPATIAL (Geospatial Workloads).
        Whilst data and query plans are not identical, they share similar characteristics in terms of Data Access.
    - Transaction Lifespan: Varies based on query complexity, usually fast and low-latency queries.
    - Read/Write Balance: Read-heavy with occasional writes in normal operation (ignore bulk load).
    - Query Complexity: Complex, involving vector search, similarity queries, and geospatial filtering.
    - Data Access (READ) Pattern: Random access to feature vectors, embeddings, and geospatial data.
    - Insertion (WRITE) Pattern: Bulk insertions for training datasets at beginning but some real-time
        and minor/small updates for live models.
    - Typical Usage: Full-text search in e-commerce, knowledge bases, and document search engines; Model training,
        feature extraction, and serving models in recommendation systems; Location-based services, mapping,
        geographic data analysis, proximity searches.

 */
const PG_WORKLOAD = Object.freeze({
    TSR_IOT: "tst",
    OLTP: "oltp",
    HTAP: "htap",
    OLAP: "olap",
    VECTOR: "vector",
});

// ==================================================================================
/**
 * Original Source File: ./src/tuner/data/options.py
 */
// PG_TUNE_USR_KWARGS stores tuning user/app-defined keywords to adjust the tuning phase.
class PG_TUNE_USR_KWARGS {
    constructor(options = {}) {
        // Connection
        this.user_max_connections = options.user_max_connections ?? 0;
        this.superuser_reserved_connections_scale_ratio = options.superuser_reserved_connections_scale_ratio ?? 1.5;
        this.single_memory_connection_overhead = options.single_memory_connection_overhead ?? (5 * Mi);
        this.memory_connection_to_dedicated_os_ratio = options.memory_connection_to_dedicated_os_ratio ?? 0.3;
        // Memory Utilization (Basic)
        this.effective_cache_size_available_ratio = options.effective_cache_size_available_ratio ?? 0.985;
        this.shared_buffers_ratio = options.shared_buffers_ratio ?? 0.25;
        this.max_work_buffer_ratio = options.max_work_buffer_ratio ?? 0.075;
        this.effective_connection_ratio = options.effective_connection_ratio ?? 0.75;
        this.temp_buffers_ratio = options.temp_buffers_ratio ?? 0.25;
        // Memory Utilization (Advanced)
        this.max_normal_memory_usage = options.max_normal_memory_usage ?? 0.45;
        this.mem_pool_tuning_ratio = options.mem_pool_tuning_ratio ?? 0.6;
        this.hash_mem_usage_level = options.hash_mem_usage_level ?? -6;
        this.mem_pool_parallel_estimate = options.mem_pool_parallel_estimate ?? true;
        // Tune logging behaviour
        this.max_query_length_in_bytes = options.max_query_length_in_bytes ?? (2 * Ki);
        this.max_runtime_ms_to_log_slow_query = options.max_runtime_ms_to_log_slow_query ?? (2 * K10);
        this.max_runtime_ratio_to_explain_slow_query = options.max_runtime_ratio_to_explain_slow_query ?? 1.5;
        // WAL control parameters
        this.wal_segment_size = options.wal_segment_size ?? BASE_WAL_SEGMENT_SIZE;
        this.min_wal_size_ratio = options.min_wal_size_ratio ?? 0.05;
        this.max_wal_size_ratio = options.max_wal_size_ratio ?? 0.05;
        this.wal_keep_size_ratio = options.wal_keep_size_ratio ?? 0.05;
        // Vacuum Tuning
        this.autovacuum_utilization_ratio = options.autovacuum_utilization_ratio ?? 0.80;
        this.vacuum_safety_level = options.vacuum_safety_level ?? 2;
    }
}

// PG_TUNE_USR_OPTIONS defines the advanced tuning options.
class PG_TUNE_USR_OPTIONS {
    constructor(options = {}) {
        // Basic profile for system tuning
        this.workload_profile = options.workload_profile ?? PG_SIZING.LARGE;
        this.pgsql_version = options.pgsql_version ?? 17;
        // Disk options for data partitions (required)
        this.data_index_spec = options.data_index_spec; // Expected to be an instance of PG_DISK_PERF
        this.wal_spec = options.wal_spec; // Expected to be an instance of PG_DISK_PERF
        // Data Integrity, Transaction, Recovery, and Replication
        this.max_backup_replication_tool = options.max_backup_replication_tool ?? PG_BACKUP_TOOL.PG_BASEBACKUP;
        this.opt_transaction_lost = options.opt_transaction_lost ?? PG_PROFILE_OPTMODE.NONE;
        this.opt_wal_buffers = options.opt_wal_buffers ?? PG_PROFILE_OPTMODE.SPIDEY;
        this.max_time_transaction_loss_allow_in_second = options.max_time_transaction_loss_allow_in_second ?? 650;
        this.max_num_stream_replicas_on_standby = options.max_num_stream_replicas_on_standby ?? 0;
        this.max_num_logical_replicas_on_standby = options.max_num_logical_replicas_on_standby ?? 0;
        this.offshore_replication = options.offshore_replication ?? false;
        // Database tuning options
        this.workload_type = options.workload_type ?? PG_WORKLOAD.HTAP;
        this.opt_mem_pool = options.opt_mem_pool ?? PG_PROFILE_OPTMODE.OPTIMUS_PRIME;
        this.tuning_kwargs = options.tuning_kwargs ?? new PG_TUNE_USR_KWARGS();
        // Anti-wraparound vacuum tuning options
        this.database_size_in_gib = options.database_size_in_gib ?? 0;
        this.num_write_transaction_per_hour_on_workload = options.num_write_transaction_per_hour_on_workload ?? (50 * K10);
        // System parameters
        this.operating_system = options.operating_system ?? 'linux';
        this.vcpu = options.vcpu ?? 4;
        this.total_ram = options.total_ram ?? (16 * Gi);
        this.base_kernel_memory_usage = options.base_kernel_memory_usage ?? -1;
        this.base_monitoring_memory_usage = options.base_monitoring_memory_usage ?? -1;
        // System tuning flags
        this.enable_sysctl_general_tuning = options.enable_sysctl_general_tuning ?? false;
        this.enable_sysctl_correction_tuning = options.enable_sysctl_correction_tuning ?? false;
        this.enable_database_general_tuning = options.enable_database_general_tuning ?? true;
        this.enable_database_correction_tuning = options.enable_database_correction_tuning ?? true;
        this.align_index = options.align_index ?? 0;

        // Run post-initialization adjustments
        this.model_post_init();
    }

    /**
     * Adjust and validate tuning options.
     */
    model_post_init() {
        // Disable correction tuning if general tuning is off.
        if (!this.enable_sysctl_general_tuning) {
            this.enable_sysctl_correction_tuning = false;
        }
        if (!this.enable_database_general_tuning) {
            this.enable_database_correction_tuning = false;
        }

        // Set base monitoring memory usage if not provided.
        if (this.base_monitoring_memory_usage === -1) {
            this.base_monitoring_memory_usage = 256 * Mi;
            if (this.operating_system === 'containerd') {
                this.base_monitoring_memory_usage = 64 * Mi;
            } else if (this.operating_system === 'PaaS') {
                this.base_monitoring_memory_usage = 0;
            }
            console.debug(`Set the monitoring memory usage to ${bytesize_to_hr(this.base_monitoring_memory_usage, false, ' ')}`);
        }

        // Set base kernel memory usage if not provided.
        if (this.base_kernel_memory_usage === -1) {
            this.base_kernel_memory_usage = 768 * Mi;
            if (this.operating_system === 'containerd') {
                this.base_kernel_memory_usage = 64 * Mi;
            } else if (this.operating_system === 'windows') {
                this.base_kernel_memory_usage = 2 * Gi;
            } else if (this.operating_system === 'PaaS') {
                this.base_kernel_memory_usage = 0;
            }
            console.debug(`Set the kernel memory usage to ${bytesize_to_hr(this.base_kernel_memory_usage, false, ' ')}`);
        }

        // Check that the PostgreSQL version is supported.
        if (!SUPPORTED_POSTGRES_VERSIONS.includes(this.pgsql_version.toLocaleString())) {
            console.warn(`The PostgreSQL version ${this.pgsql_version} is not in the supported version list. Forcing the version to the latest supported version.`);
            this.pgsql_version = SUPPORTED_POSTGRES_VERSIONS[SUPPORTED_POSTGRES_VERSIONS.length - 1];
        }

        // Check minimal usable RAM.
        if (this.usable_ram < 4 * Gi) {
            const _sign = (this.usable_ram >= 0) ? '+' : '-';
            const _msg = `The usable RAM ${_sign}${bytesize_to_hr(this.usable_ram, false, ' ')} is less than 4 GiB. Tuning may not be accurate.`;
            console.warn(_msg);
        }

        // Adjust database size based on data volume.
        const _database_limit = Math.ceil((this.data_index_spec.disk_usable_size / Gi) * 0.90);
        if (this.database_size_in_gib === 0) {
            console.warn('Database size is 0 GiB; estimating as 60% of data volume.');
            this.database_size_in_gib = Math.ceil((this.data_index_spec.disk_usable_size / Gi) * 0.60);
        }
        if (this.database_size_in_gib > _database_limit) {
            console.warn(`Database size ${this.database_size_in_gib} GiB exceeds 90% of data volume; capping to ${_database_limit} GiB.`);
            this.database_size_in_gib = _database_limit;
        }
    }

    /**
     * Cached property: maps hardware scope keys to the workload profile.
     * @returns {Object<string, *>} An object mapping scopes to this.workload_profile.
     */
    get hardware_scope() {
        if (!this._hardware_scope) {
            this._hardware_scope = {
                cpu: this.workload_profile,
                mem: this.workload_profile,
                net: this.workload_profile,
                disk: this.workload_profile,
                overall: this.workload_profile
            };
        }
        return this._hardware_scope;
    }

    /**
     * Translates a term to its corresponding hardware scope.
     * @param {string|null} term - The term for hardware scope.
     * @returns {*} The corresponding workload profile.
     */
    translate_hardware_scope(term) {
        if (term) {
            term = term.toLowerCase().trim();
            if (this.hardware_scope.hasOwnProperty(term)) {
                return this.hardware_scope[term];
            } else {
                console.debug(`Hardware scope ${term} not supported -> falling back to overall profile.`);
            }
        }
        return this.workload_profile;
    }

    /**
     * Cached property: calculates usable RAM by subtracting kernel and monitoring usage from total RAM.
     * @returns {number} The usable RAM in bytes.
     * @throws {Error} If usable RAM is less than 0.
     */
    get usable_ram() {
        if (this._usable_ram === undefined) {
            let mem_available = this.total_ram;
            mem_available -= this.base_kernel_memory_usage;
            mem_available -= this.base_monitoring_memory_usage;
            if (mem_available < 0) {
                throw new Error('The available memory is less than 0. Please check the memory usage.');
            }
            this._usable_ram = mem_available;
        }
        return this._usable_ram;
    }
}

// ==================================================================================
/**
 * Original Source File: ./src/tuner/data/items.js
 */
const _FLOAT_PRECISION = 4; // Default float precision for PG_TUNE_ITEM
// The string punctuation characters
const _STRING_PUNCTUATION = `"!"#$%&'()*+,-./:;<=>?@[\]^_{}|`;

class PG_TUNE_ITEM {
    constructor(data) {
        // Required fields
        this.key = data.key;
        this.before = data.before;
        this.after = data.after;
        this.comment = data.comment || null;

        // Custom-reserved variables for developers
        this.style = data.style !== undefined ? data.style : "$1 = '$2'";
        this.trigger = data.trigger;
        this.partial_func = data.partial_func || null;
        this.hardware_scope = data.hardware_scope; // Expected as a tuple [hardware type, sizing value]
    }

    out(output_if_difference_only = false, include_comment = false, custom_style = null) {
        // If output_if_difference_only is true and before equals after, return an empty string.
        if (output_if_difference_only && this.before === this.after) {
            return '';
        }
        let texts = [];

        if (include_comment && this.comment !== null) {
            // Transform the comment by prefixing each line with "# "
            const formattedComment = String(this.comment)
                .split('\n')
                .map(line => `# ${line}`)
                .join('\n');
            texts.push(formattedComment);
        }

        const style = custom_style || this.style || "$1 = $2";
        if (!style.includes("$1") || !style.includes("$2")) {
            throw new Error(`Invalid style configuration: ${style} due to missing $1 and $2`);
        }
        // Remove duplicated spaces if present
        const cleanedStyle = style.replace(/\s\s+/g, ' ');
        const afterDisplay = this.out_display();
        const resultStyle = cleanedStyle.replace("$1", this.key).replace("$2", afterDisplay).trim();

        texts.push(resultStyle);
        return texts.join('');
    }

    out_display(override_value = null) {
        let value = override_value !== null ? override_value : this.after;

        if (this.partial_func && typeof this.partial_func === 'function') {
            value = this.partial_func(value);
        } else if (typeof value === 'number') {
            // Rounding and converting to fixed point string
            value = value.toFixed(_FLOAT_PRECISION);
            // Remove trailing zeros and possible trailing dot
            value = value.replace(/(\.\d*?[1-9])0+$/,'$1').replace(/\.0+$/,'').replace(/\.$/, '.0');
        }
        if (typeof value !== 'string') {
            value = String(value);
        }
        // Trim whitespace if value contains a decimal point and remove trailing zeros
        if (value.includes('.')) {
            value = value.trim().replace(/(\.\d*?)0+$/, '$1');
            if (value.endsWith('.')) {
                value += '0';
            }
        }
        // If the original after value is a string that contains whitespace or punctuation, wrap it in single quotes.
        if (typeof this.after === 'string' &&
            (this.after.includes(' ') || _STRING_PUNCTUATION.split('').some(p => this.after.includes(p)))) {
            value = `'${value}'`;
        }
        return value;
    }

    transform_keyname() {
        return this.key.split('_').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
    }
}

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_0.py
 * 
 * The layout is splited between category which shared this format:
_<Scope>_<Description>_PROFILE = {
    "<tuning_item_name>": {
        'tune_op': Callable(),          # Optional, used to define the function to calculate the value
        'default': <default_value>,     # Must have and a constant and not a function
        'comment': "<description>",     # An optional description
        'instructions': {
            "*_default": <default_value>,  # Optional, used to define the default value for each tuning profile
            "*": Callable(),               # Optional, used to define the function to calculate the value
        }
    }
}
 */

// This could be increased if your database server is not under hypervisor and run under Xeon_v6, recent AMD EPYC 
// (2020) or powerful ARM CPU, or AMD Threadripper (2020+). But in most cases, the 4x scale factor here is enough 
// to be generalized. Even on PostgreSQL 14, the scaling is significant when the PostgreSQL server is not 
// virtualized and have a lot of CPU to use (> 32 - 96|128 cores).    
const __BASE_RESERVED_DB_CONNECTION = 3; 
const __SCALE_FACTOR_CPU_TO_CONNECTION = 4;
const __DESCALE_FACTOR_RESERVED_DB_CONNECTION = 4; // This is the descaling factor for reserved connections

function _GetNumConnections(options, response, use_reserved_connection = false, use_full_connection = false) {
    // This function is used to calculate the number of connections that can be used by the PostgreSQL server. The number
    // of connections is calculated based on the number of logical CPU cores available on the system and the scale factor.
    managed_cache = response.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG);
    try {
        let total_connections = managed_cache['max_connections'];
        let reserved_connections = managed_cache['reserved_connections'] + managed_cache['superuser_reserved_connections'];
    } catch (e) {
        throw new Error("This function required the connection must be triggered and placed in the managed cache: " + e);
    }
    if (!use_reserved_connection) {
        total_connections -= reserved_connections;
    } else {
        printf("The reserved mode is enabled (not recommended) as reserved connections are purposely different " + 
            "usage such as troubleshooting, maintenance, **replication**, sharding, cluster, ...");
    }
    if (!use_full_connection) {
        total_connections *= options.tuning_kwargs.effective_connection_ratio;
    }
    return Math.ceil(total_connections);  
}

function _GetMemConnInTotal(options, response, use_reserved_connection = false, use_full_connection = false) {
    /* 
    The memory usage per connection is varied and some articles said it could range on scale 1.5 - 14 MiB,
    or 5 - 10 MiB so we just take this ratio. This memory is assumed to be on one connection without execute
    any query or transaction.
    References:
    - https://www.cybertec-postgresql.com/en/postgresql-connection-memory-usage/
    - https://cloud.ibm.com/docs/databases-for-postgresql?topic=databases-for-postgresql-managing-connections
    - https://techcommunity.microsoft.com/blog/adforpostgresql/analyzing-the-limits-of-connection-scalability-in-postgres/1757266
    - https://techcommunity.microsoft.com/blog/adforpostgresql/improving-postgres-connection-scalability-snapshots/1806462
    Here is our conclusion:
    - PostgreSQL apply one-process-per-connection TCP connection model, and the connection memory usage during idle
    could be significant on small system, especially during the OLTP workload.
    - Idle connections leads to more frequent context switches, harmful to the system with less vCPU core. And
    degrade not only the transaction throughput but also the latency.
    */
    let num_conns = _GetNumConnections(options, response, use_reserved_connection, use_full_connection);
    let mem_conn_overhead = options.tuning_kwargs.single_memory_connection_overhead;
    return num_conns * mem_conn_overhead;
}

function _CalcSharedBuffers(options) {
    let shared_buffers_ratio = options.tuning_kwargs.shared_buffers_ratio;
    if (shared_buffers_ratio < 0.25) {
        _logger.warning('The shared_buffers_ratio is too low, which official PostgreSQL documentation recommended ' +
            'the starting point is 25% of RAM or over. Please consider increasing the ratio.');
    }
    let shared_buffers = Math.max(options.usable_ram * shared_buffers_ratio, 128 * Mi);
    if (shared_buffers == 128 * Mi) {
        _logger.warning('No benefit is found on tuning this variable');
    }
    // Re-align the number (always use the lower bound for memory safety) -> We can set to 32-128 pages, or
    // probably higher as when the system have much RAM, an extra 1 pages probably not a big deal
    shared_buffers = realign_value(shared_buffers, { page_size : DB_PAGE_SIZE })[options.align_index];
    _logger.debug(`shared_buffers: ${Math.floor(shared_buffers / Mi)}MiB`);
    return shared_buffers;
}

function _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response) {
    /* 
    There are some online documentations that gives you a generic formula for work_mem (not the temp_buffers), besides
    some general formulas. For example:
    - [25]: work_mem = (RAM - shared_buffers) / (16 * vCPU cores).
    - pgTune: work_mem = (RAM - shared_buffers) / (3 * max_connections) / max_parallel_workers_per_gather
    - Microsoft TechCommunity (*): RAM / max_connections / 16   (1/16 is conservative factors)

    Whilst these settings are good and bad, from Azure docs, "Unlike shared buffers, which are in the shared memory
    area, work_mem is allocated in a per-session or per-query private memory space. By setting an adequate work_mem
    size, you can significantly improve the efficiency of these operations and reduce the need to write temporary
    data to disk". Whilst this advice is good in general, I believe not every applications have the ability to
    change it on-the-fly due to the application design, database sizing, the number of connections and CPUs, and
    the change of data after time of usage before considering specific tuning. Unless it is under interactive
    sessions made by developers or DBA, those are not there. 

    From our rationale, when we target on first on-board database, we don't know how the application will behave
    on it wished queries, but we know its workload type, and it safeguard. So this is our solution.
    work_mem = ratio * (RAM - shared_buffers - overhead_of_os_conn) * threshold / effective_user_connections

    And then we cap it to below a 64 MiB - 1.5 GiB (depending on workload) to ensure our setup is don't
    exceed the memory usage.
    - https://techcommunity.microsoft.com/blog/adforpostgresql/optimizing-query-performance-with-work-mem/4196408
    */
    let pgmem_available = int(options.usable_ram) - group_cache['shared_buffers'];
    let _mem_conns = _GetMemConnInTotal(options, response, use_reserved_connection=false, use_full_connection=true);
    pgmem_available -= _mem_conns * options.tuning_kwargs.memory_connection_to_dedicated_os_ratio;
    if ('wal_buffers' in global_cache) {   // I don't know if this make significant impact?
        pgmem_available -= global_cache['wal_buffers'];
    }
    let max_work_buffer_ratio = options.tuning_kwargs.max_work_buffer_ratio;
    let active_connections = _GetNumConnections(options, response, use_reserved_connection=false,
                                                use_full_connection=false);
    let total_buffers = int(pgmem_available * max_work_buffer_ratio) // active_connections;
    // Minimum to 1 MiB and maximum is varied between workloads
    let max_cap = int(1.5 * Gi);
    if (options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG, PG_WORKLOAD.TSR_IOT)) {
        max_cap = 256 * Mi;
    }
    if (options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE)) {
        // I don't think I will make risk beyond this number
        max_cap = 8 * Gi;
    }
    let temp_buffer_ratio = options.tuning_kwargs.temp_buffers_ratio;
    let temp_buffers = cap_value(total_buffers * temp_buffer_ratio, 1 * Mi, max_cap);
    let work_mem = cap_value(total_buffers * (1 - temp_buffer_ratio), 1 * Mi, max_cap);
    
    // Realign the number (always use the lower bound for memory safety)
    temp_buffers = realign_value(int(temp_buffers), page_size=DB_PAGE_SIZE)[options.align_index];
    work_mem = realign_value(int(work_mem), page_size=DB_PAGE_SIZE)[options.align_index];
    _logger.debug(`temp_buffers: ${Math.floor(temp_buffers / Mi)}MiB`);
    _logger.debug(`work_mem: ${Math.floor(work_mem / Mi)}MiB`);
    
    return [temp_buffers, work_mem];
}

function _CalcTempBuffers(group_cache, global_cache, options, response) {
    return _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[0];
}

function _CalcWorkMem(group_cache, global_cache, options, response) {
    return _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[1];
}

function _GetMaxConns(options, group_cache, min_user_conns, max_user_conns) {
    total_reserved_connections = group_cache['reserved_connections'] + group_cache['superuser_reserved_connections'];
    if (options.tuning_kwargs.user_max_connections != 0) {
        _logger.debug('The max_connections variable is overridden by the user so no constraint here.');
        allowed_connections = options.tuning_kwargs.user_max_connections;
        return allowed_connections + total_reserved_connections;
    }
    // Make a small upscale here to future-proof database scaling, and reduce the number of connections
    _upscale = __SCALE_FACTOR_CPU_TO_CONNECTION;  // / max(0.75, options.tuning_kwargs.effective_connection_ratio)
    console.debug("The max_connections variable is determined by the number of logical CPU count " + 
        "with the scale factor of ${__SCALE_FACTOR_CPU_TO_CONNECTION}x.");
    _minimum = Math.max(min_user_conns, total_reserved_connections);
    max_connections = cap_value(Math.ceil(options.vcpu * _upscale), _minimum, max_user_conns) + total_reserved_connections;
    console.debug("max_connections: ${max_connections}");
    return max_connections;
}

function _GetReservedConns(options, minimum, maximum, superuser_mode = false, base_reserved_connection = null) {
    if (base_reserved_connection == null) {
        base_reserved_connection = __BASE_RESERVED_DB_CONNECTION;
    }
    // 1.5x here is heuristically defined to limit the number of superuser reserved connections
    if (!superuser_mode) {
        reserved_connections = options.vcpu / __DESCALE_FACTOR_RESERVED_DB_CONNECTION;
    } else { 
        superuser_heuristic_percentage = options.tuning_kwargs.superuser_reserved_connections_scale_ratio;
        descale_factor = __DESCALE_FACTOR_RESERVED_DB_CONNECTION * superuser_heuristic_percentage;
        reserved_connections = int(options.vcpu / descale_factor);
    }
    return cap_value(reserved_connections, minimum, maximum) + base_reserved_connection;
}

function _CalcEffectiveCacheSize(group_cache, global_cache, options, response) {
    /*
    The following setup made by the Azure PostgreSQL team. The reason is that their tuning guideline are better as 
    compared as what I see in AWS PostgreSQL. The Azure guideline is to take the available 
    memory (RAM - shared_buffers):
    https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/server-parameters-table-query-tuning-planner-cost-constants?pivots=postgresql-17#effective_cache_size
    and https://dba.stackexchange.com/questions/279348/postgresql-does-effective-cache-size-includes-shared-buffers
    Default is half of physical RAM memory on most tuning guideline
    */
    pgmem_available = int(options.usable_ram);    // Make a copy
    pgmem_available -= global_cache['shared_buffers'];
    _mem_conns = _GetMemConnInTotal(options, response, use_reserved_connection=false, use_full_connection=true);
    pgmem_available -= _mem_conns * options.tuning_kwargs.memory_connection_to_dedicated_os_ratio;

    // Re-align the number (always use the lower bound for memory safety)
    effective_cache_size = pgmem_available * options.tuning_kwargs.effective_cache_size_available_ratio;
    effective_cache_size = realign_value(int(effective_cache_size), page_size=DB_PAGE_SIZE)[options.align_index];
    console.debug("Effective cache size: ${Math.floor(effective_cache_size / Mi)}MiB");
    return effective_cache_size;
}

function _CalcWalBuffers(group_cache, global_cache, options, response, minimum, maximum) {
    /*
    See this article: https://www.cybertec-postgresql.com/en/wal_level-what-is-the-difference/
    It is only benefit when you use COPY instead of SELECT. For other thing, the spawning of
    WAL buffers is not necessary. We don't care the large of one single WAL file 
    */
    shared_buffers = global_cache['shared_buffers'];
    usable_ram_noswap = options.usable_ram;
    function fn(x) {
        return 1024 * (37.25 * Math.log(x) + 2) * 0.90;  // Measure in KiB
    } 
    oldstyle_wal_buffers = min(floor(shared_buffers / 32), options.tuning_kwargs.wal_segment_size);  // Measured in bytes
    wal_buffers = max(oldstyle_wal_buffers, fn(usable_ram_noswap / Gi) * Ki);
    return realign_value(cap_value(Math.ceil(wal_buffers), minimum, maximum), page_size=DB_PAGE_SIZE)[options.align_index];
}

// ----------------------------------------------------------------------------------------------------------------
_DB_CONN_PROFILE = {
    // Connections
    'superuser_reserved_connections': {
        'instructions': {
            'mini': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 3, superuser_mode=true, base_reserved_connection=1),
            'medium': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 5, superuser_mode=true, base_reserved_connection=2),
        },
        'tune_op': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 10, superuser_mode=true),
        'default': __BASE_RESERVED_DB_CONNECTION,
    },
    'reserved_connections': {
        'instructions': {
            'mini': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 3, superuser_mode=false, base_reserved_connection=1),
            'medium': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 5, superuser_mode=false, base_reserved_connection=2),
        },
        'tune_op': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 10, superuser_mode=false),
        'default': __BASE_RESERVED_DB_CONNECTION,
    },
    'max_connections': {
        'instructions': {
            'mini': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 10, 30),
            'medium': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 15, 65),
            'large': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 30, 100),
            'mall': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 40, 175),
            'bigt': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 50, 250),
        },
        'default': 30,
    },
    'listen_addresses': {
        'default': '*',
    }
}

_DB_RESOURCE_PROFILE = {
    // Memory and CPU
    'shared_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcSharedBuffers(options),
        'default': 128 * Mi,
        'partial_func': (value) => "${floor(value / Mi)}MB",
    },
    'temp_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcTempBuffers(group_cache, global_cache, options, response),
        'default': 8 * Mi,
        'partial_func': (value) => "${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB",
    },
    'work_mem': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcWorkMem(group_cache, global_cache, options, response),
        'default': 4 * Mi,
        'partial_func': (value) => "${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB",
    },
    'hash_mem_multiplier': {
        'default': 2.0,
    },
}

_DB_VACUUM_PROFILE = {
    // Memory and Worker
    'autovacuum': {
        'default': 'on',
    },
    'autovacuum_max_workers': {
        'instructions': {
            'mini_default': 1,
            'medium_default': 2,
            'large': (group_cache, global_cache, options, response) => cap_value(Math.floor(options.vcpu / 4) + 1, 2, 5),
            'mall': (group_cache, global_cache, options, response) => cap_value(Math.floor(options.vcpu / 3.5) + 1, 3, 6),
            'bigt': (group_cache, global_cache, options, response) => cap_value(Math.floor(options.vcpu / 3) + 1, 3, 8),
        },
        'default': 3,
        'hardware_scope': 'cpu',
    },
    'autovacuum_naptime': {
        'tune_op': (group_cache, global_cache, options, response) => SECOND * (15 + 30 * (group_cache['autovacuum_max_workers'] - 1)),
        'default': 1 * MINUTE,
        'partial_func': (value) => "${Math.floor(value / SECOND)}s",
    },
    'maintenance_work_mem': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[1],
        'default': 64 * Mi,
        'post-condition-group': (value, cache, options) => value * cache['autovacuum_max_workers'] < Math.floor(options.usable_ram / 2),
        'partial_func': (value) => "${Math.floor(value / Mi)}MB",
    },
    'autovacuum_work_mem': {
        'default': -1,
    },
    // Threshold and Scale Factor: For the information, I would use the [08] as the base optimization profile and could 
    // be applied on most scenarios, except that you are having an extremely large table where 0.1% is too large.
    'autovacuum_vacuum_threshold; autovacuum_vacuum_insert_threshold; autovacuum_analyze_threshold': {
        'instructions': {
            'mini_default': Math.floor(K10 / 2),
        },
        'hardware_scope': 'overall',
        'default': 2 * K10,
    },
    'autovacuum_vacuum_scale_factor; autovacuum_vacuum_insert_scale_factor; autovacuum_analyze_scale_factor': {
        'instructions': {
            'mini_default': 0.010,
            'mall_default': 0.002,
            'bigt_default': 0.002,
        },
        'hardware_scope': 'overall',
        'default': 0.005,
    },
    'autovacuum_vacuum_cost_delay': {
        'default': 2,
        'partial_func': (value) => "${value}ms",
    },
    'autovacuum_vacuum_cost_limit': {
        'default': -1,
    },
    'vacuum_cost_delay': {
        'default': 0,
        'partial_func': (value) => "${value}s",
    },
    'vacuum_cost_limit': {
        'instructions': {
            'large_default': 500,
            'mall_default': K10,
            'bigt_default': K10,
        },
        'default': 200,
    },
    'vacuum_cost_page_hit': {
        'default': 1,
    },
    'vacuum_cost_page_miss': {
        'default': 2,
    },
    'vacuum_cost_page_dirty': {
        'default': 20,
    },
    // Transaction ID and MultiXact
    // See here: https://postgresqlco.nf/doc/en/param/autovacuum_freeze_max_age/
    // and https://www.youtube.com/watch?v=vtjjaEVPAb8 at (30:02)
    'autovacuum_freeze_max_age': {
        'default': 500 * M10,
    },
    'vacuum_freeze_table_age': {
        'tune_op': (group_cache, global_cache, options, response) => realign_value(Math.ceil(group_cache['autovacuum_freeze_max_age'] * 0.85), page_size=250 * K10)[options.align_index],
        'default': 150 * M10,
    },
    'vacuum_freeze_min_age': {
        'default': 50 * M10,
    },
    'autovacuum_multixact_freeze_max_age': {
        'default': 850 * M10,
    },
    'vacuum_multixact_freeze_table_age': {
        'tune_op': (group_cache, global_cache, options, response) => realign_value(Math.ceil(group_cache['autovacuum_multixact_freeze_max_age'] * 0.85), page_size=250 * K10)[options.align_index],
        'default': 150 * M10,
    },
    'vacuum_multixact_freeze_min_age': {
        'default': 5 * M10,
    },
}

_DB_BGWRITER_PROFILE = {
    // We don't tune the bgwriter_flush_after = 512 KiB as it is already optimal and PostgreSQL said we don't need
    // to tune it
    'bgwriter_delay': {
        'default': 300,
        'hardware_scope': 'overall',
        'partial_func': (value) => "${value}ms",
    },
    'bgwriter_lru_maxpages': {
        'instructions': {
            'large_default': 350,
            'mall_default': 425,
            'bigt_default': 500,
        },
        'default': 300,
    },
    'bgwriter_lru_multiplier': {
        'default': 2.0,
    },
    'bgwriter_flush_after': {
        'default': 512 * Ki,
        'partial_func': (value) => "${Math.floor(value / Ki)}kB",
    },
}

_DB_ASYNC_DISK_PROFILE = {
    'effective_io_concurrency': {
        'default': 16,
    },
    'maintenance_io_concurrency': {
        'default': 10,
    },
    'backend_flush_after': {
        'default': 0,
    },
}

_DB_ASYNC_CPU_PROFILE = {
    'max_worker_processes': {
        'tune_op': (group_cache, global_cache, options, response) => cap_value(Math.ceil(options.vcpu * 1.5) + 2, 4, 512),
        'default': 8,
    },
    'max_parallel_workers': {
        'tune_op': (group_cache, global_cache, options, response) => min(cap_value(Math.ceil(options.vcpu * 1.125), 4, 512), group_cache['max_worker_processes']),
        'default': 8,
    },
    'max_parallel_workers_per_gather': {
        'tune_op': (group_cache, global_cache, options, response) => min(cap_value(Math.ceil(options.vcpu / 3), 2, 32), group_cache['max_parallel_workers']),
        'default': 2,
    },
    'max_parallel_maintenance_workers': {
        'tune_op': (group_cache, global_cache, options, response) => min(cap_value(Math.ceil(options.vcpu / 2), 2, 32), group_cache['max_parallel_workers']),
        'default': 2,
    },
    'min_parallel_table_scan_size': {
        'instructions': {
            'medium_default': 16 * Mi,
            'large_default': 24 * Mi,
            'mall_default': 32 * Mi,
            'bigt_default': 32 * Mi,
        },
        'default': 8 * Mi,
        'partial_func': (value) => '${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB',
    },
    'min_parallel_index_scan_size': {
        'tune_op': (group_cache, global_cache, options, response) => max(group_cache['min_parallel_table_scan_size'] / 16, 512 * Ki),
        'default': 512 * Ki,
        'partial_func': (value) => '${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB',
    },
}

_DB_WAL_PROFILE = {
    // For these settings, please refer to the [13] and [14] for more information
    'wal_level': {
        'default': 'replica',
    },
    'synchronous_commit': {
        'default': 'on',
    },
    'full_page_writes': {
        'default': 'on',
    },
    'fsync': {
        'default': 'on',
    },
    'wal_compression': {
        'default': 'pglz',
    },
    'wal_init_zero': {
        'default': 'on',
    },
    'wal_recycle': {
        'default': 'on',
    },
    'wal_log_hints': {
        'default': 'on',
    },
    // See Ref [16-19] for tuning the wal_writer_delay and commit_delay
    'wal_writer_delay': {
        'instructions': {
            "mini_default": K10,
        },
        'default': 200,
        'partial_func': (value) => "${value}ms",
    },
    'wal_writer_flush_after': {
        'default': 1 * Mi,
        'partial_func': (value) => "${Math.floor(value / Mi)}MB",
    },
    // This setting means that when you have at least 5 transactions in pending, the delay (interval by commit_delay)
    // would be triggered (assuming maybe more transactions are coming from the client or application level)
    // ============================== CHECKPOINT ==============================
    // Checkpoint tuning are based on [20-23]: Our wishes is to make the database more reliable and perform better,
    // but reducing un-necessary read/write operation
    'checkpoint_timeout': {
        'instructions': {
            'mini_default': 30 * MINUTE,
            'mall_default': 10 * MINUTE,
            'bigt_default': 10 * MINUTE,
        },
        'default': 15 * MINUTE,
        'hardware_scope': 'overall',
        'partial_func': (value) => '${Math.floor(value / MINUTE)}min',
    },
    'checkpoint_flush_after': {
        'default': 256 * Ki,
        'partial_func': (value) => '${Math.floor(value / Ki)}kB',
    },
    'checkpoint_completion_target': {
        'default': 0.9,
    },
    'checkpoint_warning': {
        'default': 30,
        'partial_func': (value) => "${value}s",
    },
    // ============================== WAL SIZE ==============================
    'min_wal_size': {
        'tune_op': (group_cache, global_cache, options, response) => 10 * options.tuning_kwargs.wal_segment_size,
        'default': 10 * BASE_WAL_SEGMENT_SIZE,
        'partial_func': (value) => '${Math.floor(value / Mi)}MB',
    },
    'max_wal_size': {
        'instructions': {
            'mini_default': 2 * Gi,
            'medium_default': 4 * Gi,
            'large_default': 8 * Gi,
            'mall_default': 16 * Gi,
            'bigt_default': 32 * Gi,
        },
        'default': 8 * Gi,
        'partial_func': (value) => '${Math.floor(value / Mi)}MB',
    },
    'wal_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => 
            _CalcWalBuffers(group_cache, global_cache, options, response, minimum=Math.floor(BASE_WAL_SEGMENT_SIZE / 2), 
                            maximum=BASE_WAL_SEGMENT_SIZE * 16),
        'default': 2 * BASE_WAL_SEGMENT_SIZE,
        'hardware_scope': 'mem',
    },
    // ============================== ARCHIVE && RECOVERY ==============================
    'archive_mode': {
        'default': 'on',
    },
    'archive_timeout': {
        'instructions': {
            'mini_default': 1 * HOUR,
            'mall_default': 30 * MINUTE,
            'bigt_default': 30 * MINUTE,
        },
        'default': 45 * MINUTE,
        'hardware_scope': 'overall',
        'partial_func': (value) => '${value}s',
    },
}

_DB_RECOVERY_PROFILE = {
    'recovery_end_command': {
        'default': 'pg_ctl stop -D $PGDATA',
    },
}

_DB_REPLICATION_PROFILE = {
    // Sending Servers
    'max_wal_senders': {
        'default': 3,
        'hardware_scope': 'net',
    },
    'max_replication_slots': {
        'default': 3,
        'hardware_scope': 'net',
    },
    'wal_keep_size': {
        // Don't worry since if you use replication_slots, its default is -1 (keep all WAL); but if replication
        // for disaster recovery (not for offload READ queries or high-availability)
        'default': 25 * BASE_WAL_SEGMENT_SIZE,
        'partial_func': (value) => '${Math.floor(value / Mi)}MB',
    },
    'max_slot_wal_keep_size': {
        'default': -1,
    },
    'wal_sender_timeout': {
        'instructions': {
            'mall_default': 2 * MINUTE,
            'bigt_default': 2 * MINUTE,
        },
        'default': MINUTE,
        'hardware_scope': 'net',
        'partial_func': (value) => '${value}s',
    },
    'track_commit_timestamp': {
        'default': 'on',
    },
    'logical_decoding_work_mem': {
        'tune_op': (group_cache, global_cache, options, response) => 
            realign_value(cap_value(Math.floor(group_cache['maintenance_work_mem'] / 8), 32 * Mi, 2 * Gi), 
        page_size=DB_PAGE_SIZE)[options.align_index],
        'default': 64 * Mi,
    },
}

_DB_QUERY_PROFILE = {
    // Query tuning
    'seq_page_cost': {
        'default': 1.0,
    },
    'random_page_cost': {
        'default': 2.60,
    },
    'cpu_tuple_cost': {
        'default': 0.03,
    },
    'cpu_index_tuple_cost': {
        'default': 0.005,
    },
    'cpu_operator_cost': {
        'default': 0.001,
    },
    'effective_cache_size': {
        'tune_op': _CalcEffectiveCacheSize,
        'default': 4 * Gi,
        'partial_func': (value) => "${Math.floor(value / Mi)}MB",
    },
    'default_statistics_target': {
        'instructions': {
            'large_default': 300,
            'mall_default': 400,
            'bigt_default': 500,
        },
        'default': 100,
    },
    // Join and Parallelism (TODO)
    'join_collapse_limit': {
        'instructions': {
            'large_default': 12,
            'mall_default': 16,
            'bigt_default': 20,
        },
        'default': 8,
    },
    'from_collapse_limit': {
        'instructions': {
            'large_default': 12,
            'mall_default': 16,
            'bigt_default': 20,
        },
        'default': 8,
    },
    'plan_cache_mode': {
        'default': 'auto',
    },
    'geqo': {
        'default': 'on',
    },
    'geqo_threshold': {
        'instructions': {
            'large_default': 12,
            'mall_default': 16,
            'bigt_default': 20,
        },
        'default': 8,
    },
    'geqo_effort': {
        'instructions': {
            'large_default': 4,
            'mall_default': 5,
            'bigt_default': 6,
        },
        'default': 3,
    },
    'geqo_pool_size': {
        'default': 0,
    },
    'geqo_generations': {
        'default': 0,
    },
    'geqo_selection_bias': {
        'default': 2.0,
    },
    'geqo_seed': {
        'default': 0,
    },
    // Parallelism
    'parallel_setup_cost': {
        'instructions': {
            'mall_default': 750,
            "bigt_default": 500,
        },
        'default': 1000,
    },
    'parallel_tuple_cost': {
        'instructions': {
            'large': (group_cache, global_cache, options, response) => min(group_cache['cpu_tuple_cost'] * 10, 0.1),
            'mall': (group_cache, global_cache, options, response) => min(group_cache['cpu_tuple_cost'] * 10, 0.1),
            'bigt': (group_cache, global_cache, options, response) => min(group_cache['cpu_tuple_cost'] * 10, 0.1),
        },
        'default': 0.1,
    },
    // Commit Behaviour
    'commit_delay': {
        'instructions': {
            'large_default': 500,
            'mall_default': 500,
            'bigt_default': 200,
        },
        'default': 1 * K10,
        'hardware_scope': 'overall',
    },
    'commit_siblings': {
        'instructions': {
            "large_default": 8,
            "mall_default": 10,
            "bigt_default": 10,
        },
        'default': 5,
        'hardware_scope': 'overall',
    },
    // Statistics
    'track_activity_query_size': {
        'default': 2 * Ki,
        'partial_func': (value) => '${value}B',
    },
    'track_counts': {
        'default': 'on',
    },
    'track_io_timing': {
        'default': 'on',
        'hardware_scope': 'cpu',
    },
}

_DB_LOG_PROFILE = {
    // Where to Log
    'logging_collector': {
        'default': 'on',
    },
    'log_destination': {
        'default': 'stderr',
    },
    'log_directory': {
        'default': 'log',
    },
    'log_filename': {
        'default': 'postgresql-%Y-%m-%d_%H%M.log',
    },
    'log_rotation_age': {
        // For best-case it is good to make the log rotation happens by time-based rather than size-based
        'instructions': {
            'mini_default': 3 * DAY,
            'mall_default': 6 * HOUR,
            'bigt_default': 4 * HOUR,
        },
        'default': 1 * DAY,
        'partial_func': (value) => "${Math.floor(value / HOUR)}h",
    },
    'log_rotation_size': {
        'instructions': {
            'mini_default': 32 * Mi,
            'medium_default': 64 * Mi,
        },
        'default': 256 * Mi,
        'partial_func': (value) => "${Math.floor(value / Mi)}MB",
    },
    'log_truncate_on_rotation': {
        'default': 'on',
    },
    // What to log
    'log_autovacuum_min_duration': {
        'default': 300 * K10,
        'partial_func': (value) => "${Math.floor(value / K10)}s",
    },
    'log_checkpoints': {
        'default': 'on',
    },
    'log_connections': {
        'default': 'on',
    },
    'log_disconnections': {
        'default': 'on',
    },
    'log_duration': {
        'default': 'on',
    },
    'log_error_verbosity': {
        'default': 'VERBOSE',
    },
    'log_line_prefix': {
        'default': '%m [%p] %quser=%u@%r@%a_db=%d,backend=%b,xid=%x %v,log=%l',
    },
    'log_lock_waits': {
        'default': 'on',
    },
    'log_recovery_conflict_waits': {
        'default': 'on',
    },
    'log_statement': {
        'default': 'mod',
    },
    'log_replication_commands': {
        'default': 'on',
    },
    'log_min_duration_statement': {
        'default': 2 * K10,
        'partial_func': (value) => "{value}ms",
    },
    'log_min_error_statement': {
        'default': 'ERROR',
    },
    'log_parameter_max_length': {
        'tune_op': (group_cache, global_cache, options, response) => global_cache['track_activity_query_size'],
        'default': -1,
        'partial_func': (value) => "${value}B",
    },
    'log_parameter_max_length_on_error': {
        'tune_op': (group_cache, global_cache, options, response) => global_cache['track_activity_query_size'],
        'default': -1,
        'partial_func': (value) => "${value}B",
    },
}

_DB_TIMEOUT_PROFILE = {
    // Transaction Timeout should not be moved away from default, but we can customize the statement_timeout and
    // lock_timeout
    // Add +1 seconds to avoid checkpoint_timeout happens at same time as idle_in_transaction_session_timeout
    'idle_in_transaction_session_timeout': {
        'default': 5 * MINUTE + 1,
        'partial_func': (value) => "${value}s",
    },
    'statement_timeout': {
        'default': 0,
        'partial_func': (value) => "${value}s",
    },
    'lock_timeout': {
        'default': 0,
        'partial_func': (value) => "${value}s",
    },
    'deadlock_timeout': {
        'default': 1 * SECOND,
        'partial_func': (value) => "${value}s",
    },
}

// Library (You don't need to tune these variable as they are not directly related to the database performance)
_DB_LIB_PROFILE = {
    'shared_preload_libraries': {
        'default': 'auto_explain,pg_prewarm,pgstattuple,pg_stat_statements,pg_buffercache,pg_visibility',   // pg_repack, Not pg_squeeze
    },
    // Auto Explain
    'auto_explain.log_min_duration': {
        'tune_op': (group_cache, global_cache, options, response) => 
            realign_value(int(global_cache['log_min_duration_statement'] * 1.5), page_size=20)[options.align_index],
        'default': -1,
        'partial_func': (value) => "${value}ms",
    },
    'auto_explain.log_analyze': {
        'default': 'off',
    },
    'auto_explain.log_buffers': {
        'default': 'on',
    },
    'auto_explain.log_wal': {
        'default': 'on',
    },
    'auto_explain.log_settings': {
        'default': 'off',
    },
    'auto_explain.log_triggers': {
        'default': 'off',
    },
    'auto_explain.log_verbose': {
        'default': 'on',
    },
    'auto_explain.log_format': {
        'default': 'text',
    },
    'auto_explain.log_level': {
        'default': 'LOG',
    },
    'auto_explain.log_timing': {
        'default': 'on',
    },
    'auto_explain.log_nested_statements': {
        'default': 'off',
    },
    'auto_explain.sample_rate': {
        'default': 1.0,
    },
    // PG_STAT_STATEMENTS
    'pg_stat_statements.max': {
        'instructions': {
            'large_default': 10 * K10,
            'mall_default': 15 * K10,
            'bigt_default': 20 * K10,
        },
        'default': 5 * K10,
    },
    'pg_stat_statements.track': {
        'default': 'all',
    },
    'pg_stat_statements.track_utility': {
        'default': 'on',
    },
    'pg_stat_statements.track_planning': {
        'default': 'off',
    },
    'pg_stat_statements.save': {
        'default': 'on',
    },
}

// Validate and remove the invalid library configuration
const preload_libraries = new Set(_DB_LIB_PROFILE['shared_preload_libraries']['default'].split(','));
for (const key of Object.keys(_DB_LIB_PROFILE)) {
    if (key.includes('.') && !preload_libraries.has(key.split('.')[0])) {
        delete _DB_LIB_PROFILE[key];
    }
}

const DB0_CONFIG_PROFILE = {
    "connection": [PG_SCOPE.CONNECTION, _DB_CONN_PROFILE, { hardware_scope: 'cpu' }],
    "memory": [PG_SCOPE.MEMORY, _DB_RESOURCE_PROFILE, { hardware_scope: 'mem' }],
    "maintenance": [PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, { hardware_scope: 'overall' }],
    "background_writer": [PG_SCOPE.OTHERS, _DB_BGWRITER_PROFILE, { hardware_scope: 'disk' }],
    "asynchronous_disk": [PG_SCOPE.OTHERS, _DB_ASYNC_DISK_PROFILE, { hardware_scope: 'disk' }],
    "asynchronous_cpu": [PG_SCOPE.OTHERS, _DB_ASYNC_CPU_PROFILE, { hardware_scope: 'cpu' }],
    "wal": [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_WAL_PROFILE, { hardware_scope: 'disk' }],
    "query": [PG_SCOPE.QUERY_TUNING, _DB_QUERY_PROFILE, { hardware_scope: 'cpu' }],
    "log": [PG_SCOPE.LOGGING, _DB_LOG_PROFILE, { hardware_scope: 'disk' }],
    "replication": [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_REPLICATION_PROFILE, { hardware_scope: 'disk' }],
    "timeout": [PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    "lib": [PG_SCOPE.EXTRA, _DB_LIB_PROFILE, { hardware_scope: 'overall' }],
};
merge_extra_info_to_profile(DB0_CONFIG_PROFILE);
type_validation(DB0_CONFIG_PROFILE);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_13.py
 */

// DB13_CONFIG_MAPPING is an empty object currently
const DB13_CONFIG_MAPPING = {};

// If DB13_CONFIG_MAPPING is non-empty, make a shallow copy of DB0_CONFIG_PROFILE;
// otherwise, use DB0_CONFIG_PROFILE directly.
const DB13_CONFIG_PROFILE = Object.keys(DB13_CONFIG_MAPPING).length > 0
    ? { ...DB0_CONFIG_PROFILE }
    : DB0_CONFIG_PROFILE;
console.debug(`DB13_CONFIG_PROFILE: ${JSON.stringify(DB13_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_14.py
 */

// Timeout profile
const _DB14_TIMEOUT_PROFILE = {
    "idle_session_timeout": {
        "default": 0,
        "partial_func": value => `${value}s`,
    },
};

// Query profile
const _DB14_QUERY_PROFILE = {
    "track_wal_io_timing": {
        "default": 'on',
    },
};

// Vacuum profile
const _DB14_VACUUM_PROFILE = {
    "vacuum_failsafe_age": {
        "default": 1600000000,
    },
    "vacuum_multixact_failsafe_age": {
        "default": 1600000000,
    }
};

// -------------------------------------------------------------------
// Merge mapping: use tuples as arrays
const DB14_CONFIG_MAPPING = {
    timeout: [PG_SCOPE.OTHERS, _DB14_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    query: [PG_SCOPE.QUERY_TUNING, _DB14_QUERY_PROFILE, { hardware_scope: 'overall' }],
    maintenance: [PG_SCOPE.MAINTENANCE, _DB14_VACUUM_PROFILE, { hardware_scope: 'overall' }],
};

// Merge extra info and validate types
merge_extra_info_to_profile(DB14_CONFIG_MAPPING);
type_validation(DB14_CONFIG_MAPPING);

// Deep copy DB0_CONFIG_PROFILE.
// Here we use JSON methods for simplicity; adjust if your objects contain non-serializable values.
let DB14_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE}

// If there is a configuration mapping, merge the corresponding parts using deepMerge.
if (Object.keys(DB14_CONFIG_MAPPING).length > 0) {
    for (const [key, value] of Object.entries(DB14_CONFIG_MAPPING)) {
        if (key in DB14_CONFIG_PROFILE) {
            // Merge the second element of the tuple (the profile dict)
            deepmerge(DB14_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
        }
    }
    rewrite_items(DB14_CONFIG_PROFILE);
};
console.debug(`DB14_CONFIG_PROFILE: ${JSON.stringify(DB14_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_15.py
 */

// Log profile
const _DB15_LOG_PROFILE = {
    "log_startup_progress_interval": {
        "default": K10,
        "partial_func": value => `${value}s`,
    },
};
// Timeout profile
const _DB15_TIMEOUT_PROFILE = {
    "idle_session_timeout": {
        "default": 0,
        "partial_func": value => `${value}s`,
    },
};
// Query profile
const _DB15_QUERY_PROFILE = {
    "track_wal_io_timing": {
        "default": 'on',
    },
};
// Vacuum profile
const _DB15_VACUUM_PROFILE = {
    "vacuum_failsafe_age": {
        "default": 1600000000,
    },
    "vacuum_multixact_failsafe_age": {
        "default": 1600000000,
    }
};

// -------------------------------------------------------------------
// Merge mapping: use tuples as arrays
const DB15_CONFIG_MAPPING = {
    log: [PG_SCOPE.LOGGING, _DB15_LOG_PROFILE, { hardware_scope: 'disk' }],
    timeout: [PG_SCOPE.OTHERS, _DB15_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    query: [PG_SCOPE.QUERY_TUNING, _DB15_QUERY_PROFILE, { hardware_scope: 'overall' }],
    maintenance: [PG_SCOPE.MAINTENANCE, _DB15_VACUUM_PROFILE, { hardware_scope: 'overall' }],
};

// Merge extra info and validate types
merge_extra_info_to_profile(DB15_CONFIG_MAPPING);
type_validation(DB15_CONFIG_MAPPING);

// Deep copy DB0_CONFIG_PROFILE.
// Here we use JSON methods for simplicity; adjust if your objects contain non-serializable values.
let DB15_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE}

// If there is a configuration mapping, merge the corresponding parts using deepMerge.
if (Object.keys(DB15_CONFIG_MAPPING).length > 0) {
    for (const [key, value] of Object.entries(DB15_CONFIG_MAPPING)) {
        if (key in DB15_CONFIG_PROFILE) {
            // Merge the second element of the tuple (the profile dict)
            deepmerge(DB15_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
        }
    }
    rewrite_items(DB15_CONFIG_PROFILE);
};
console.debug(`DB15_CONFIG_PROFILE: ${JSON.stringify(DB15_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_16.py
 */
// Log profile
const _DB16_LOG_PROFILE = {
	"log_startup_progress_interval": {}
		"default": K10,
		"partial_func": value => `${value}s`,
	},
};

// Vacuum profile
const _DB16_VACUUM_PROFILE = {
	"vacuum_buffer_usage_limit": {
		"tune_op": (group_cache, global_cache, options, response) =>
			realign_value(cap_value(Math.floor(group_cache['maintenance_work_mem'] / 16), 2 * Mi, 16 * Gi),
			page_size=DB_PAGE_SIZE)[options.align_index],
		"default": 2 * Mi,
		"hardware_scope": "mem",
		"partial_func": value => `${Math.floor(value / Mi)}MB`,
	},
	"vacuum_failsafe_age": {
		"default": 1600000000,
	},
	"vacuum_multixact_failsafe_age": {
		"default": 1600000000,
	}
};

// WAL profile
const _DB16_WAL_PROFILE = {
	"wal_compression": {
		"default": "zstd",
	},
};

// Timeout profile
const _DB16_TIMEOUT_PROFILE = {
    "idle_session_timeout": {
        "default": 0,
        "partial_func": value => `${value}s`,
    },
};
// Query profile
const _DB16_QUERY_PROFILE = {
    "track_wal_io_timing": {
        "default": 'on',
    },
};

// -------------------------------------------------------------------
// Merge mapping: use tuples as arrays
const DB16_CONFIG_MAPPING = {
	log: [PG_SCOPE.LOGGING, _DB16_LOG_PROFILE, { hardware_scope: 'disk' }],
	timeout: [PG_SCOPE.OTHERS, _DB16_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
	query: [PG_SCOPE.QUERY_TUNING, _DB16_QUERY_PROFILE, { hardware_scope: 'overall' }],
	maintenance: [PG_SCOPE.MAINTENANCE, _DB16_VACUUM_PROFILE, { hardware_scope: 'overall' }],
	wal: [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB16_WAL_PROFILE, { hardware_scope: 'disk' }],
};
// Merge extra info and validate types
merge_extra_info_to_profile(DB16_CONFIG_MAPPING);
type_validation(DB16_CONFIG_MAPPING);
// Deep copy DB0_CONFIG_PROFILE.
// Here we use JSON methods for simplicity; adjust if your objects contain non-serializable values.
let DB16_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE}
// If there is a configuration mapping, merge the corresponding parts using deepMerge.
if (Object.keys(DB16_CONFIG_MAPPING).length > 0) {
	for (const [key, value] of Object.entries(DB16_CONFIG_MAPPING)) {
		if (key in DB16_CONFIG_PROFILE) {
			// Merge the second element of the tuple (the profile dict)
			deepmerge(DB16_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
		}
	}
	rewrite_items(DB16_CONFIG_PROFILE);
};
console.debug(`DB16_CONFIG_PROFILE: ${JSON.stringify(DB16_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_17.py
 */
// Log profile
const _DB17_LOG_PROFILE = {
	"log_startup_progress_interval": {}
		"default": K10,
		"partial_func": value => `${value}s`,
	},
};

// Vacuum profile
const _DB17_VACUUM_PROFILE = {
	"vacuum_buffer_usage_limit": {
		"tune_op": (group_cache, global_cache, options, response) =>
			realign_value(cap_value(Math.floor(group_cache['maintenance_work_mem'] / 16), 2 * Mi, 16 * Gi),
			page_size=DB_PAGE_SIZE)[options.align_index],
		"default": 2 * Mi,
		"hardware_scope": "mem",
		"partial_func": value => `${Math.floor(value / Mi)}MB`,
	},
	"vacuum_failsafe_age": {
		"default": 1600000000,
	},
	"vacuum_multixact_failsafe_age": {
		"default": 1600000000,
	}
};

// WAL profile
const _DB17_WAL_PROFILE = {
	"wal_compression": {
		"default": "zstd",
	},
	"summarize_wal": {
		"default": "on",
	},
	"wal_summary_keep_time": {
		"default": Math.floor(30 * DAY / MINUTE),
		"partial_func": value => `${Math.floor(value / MINUTE)}min`,
	},
};

// Timeout profile
const _DB17_TIMEOUT_PROFILE = {
    "idle_session_timeout": {
        "default": 0,
        "partial_func": value => `${value}s`,
    },
};
// Query profile
const _DB17_QUERY_PROFILE = {
    "track_wal_io_timing": {
        "default": 'on',
    },
};

// -------------------------------------------------------------------
// Merge mapping: use tuples as arrays
const DB17_CONFIG_MAPPING = {
	log: [PG_SCOPE.LOGGING, _DB17_LOG_PROFILE, { hardware_scope: 'disk' }],
	timeout: [PG_SCOPE.OTHERS, _DB17_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
	query: [PG_SCOPE.QUERY_TUNING, _DB17_QUERY_PROFILE, { hardware_scope: 'overall' }],
	maintenance: [PG_SCOPE.MAINTENANCE, _DB17_VACUUM_PROFILE, { hardware_scope: 'overall' }],
	wal: [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB17_WAL_PROFILE, { hardware_scope: 'disk' }],
};

// Merge extra info and validate types
merge_extra_info_to_profile(DB17_CONFIG_MAPPING);
type_validation(DB17_CONFIG_MAPPING);

// Deep copy DB0_CONFIG_PROFILE.
// Here we use JSON methods for simplicity; adjust if your objects contain non-serializable values.
let DB17_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE}

// If there is a configuration mapping, merge the corresponding parts using deepMerge.
if (Object.keys(DB17_CONFIG_MAPPING).length > 0) {
	for (const [key, value] of Object.entries(DB17_CONFIG_MAPPING)) {
		if (key in DB17_CONFIG_PROFILE) {
			// Merge the second element of the tuple (the profile dict)
			deepmerge(DB17_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
		}
	}
	rewrite_items(DB17_CONFIG_PROFILE);
};
console.debug(`DB17_CONFIG_PROFILE: ${JSON.stringify(DB17_CONFIG_PROFILE)}`);

// ==================================================================================










