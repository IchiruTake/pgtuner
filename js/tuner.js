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
    return Math.min(Math.max(value, min_value), max_value);
};

// =================================================================================
/**
 * Original Source File: ./src/utils/mean.py
 *
 */

/**
 * Calculate the generalized mean of the given arguments, and rounding to the specified number of digits.
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
 * generalized_mean(1, 2, 3, { level: 1, round_ndigits: 4 })  // returns 2.0000
 */
function generalized_mean(x, level, round_ndigits) {
    if (level === 0) {
        level = 1e-6; // Small value to prevent division by zero
    }
    const n = x.length;
    const sumPower = x.reduce((acc, val) => acc + Math.pow(val, level), 0);
    const result = Math.pow(sumPower / n, 1 / level);

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

// Compute the total number of items recursively in an object.
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
                        merged_index_item, curdepth, maxdepth,
                        not_available_immutable_action, available_immutable_action,
                        not_available_immutable_tuple_action, available_immutable_tuple_action,
                        not_available_mutable_action, list_conflict_action, skiperror,
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

    valueOf() {
        return this.value;
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
 * Original Source File: ./src/tuner/data/scope.py
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

    valueOf() {
        return this.value;
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
# as the final configuration under the /etc/sysctl.d/ directory rather than overwrite
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
# HOWTO: It is recommended to apply the tuning result under the /etc/postgresql/ directory
# or inside the $PGDATA/conf/ or $PGDATA/ directory depending on how you start your
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
 * Original Source File: ./src/tuner/data/items.py
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
            // Rounding and converting to a fixed point string
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
 * The layout is split between category which shared this format:
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
    let managed_cache = response.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG);
    try {
        let total_connections = managed_cache['max_connections'];
        let reserved_connections = managed_cache['reserved_connections'] + managed_cache['superuser_reserved_connections'];
        if (!use_reserved_connection) {
            total_connections -= reserved_connections;
        } else {
            console.debug(`The reserved mode is enabled (not recommended) as reserved connections are purposely 
            different usage such as troubleshooting, maintenance, **replication**, sharding, cluster, ...`)
        }
        if (!use_full_connection) {
            total_connections *= options.tuning_kwargs.effective_connection_ratio;
        }
        return Math.ceil(total_connections);
    } catch (e) {
        throw new Error("This function required the connection must be triggered and placed in the managed cache: " + e);
    }
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
        console.warning('The shared_buffers_ratio is too low, which official PostgreSQL documentation recommended ' +
            'the starting point is 25% of RAM or over. Please consider increasing the ratio.');
    }
    let shared_buffers = Math.max(options.usable_ram * shared_buffers_ratio, 128 * Mi);
    if (shared_buffers === 128 * Mi) {
        console.warning('No benefit is found on tuning this variable');
    }
    // Re-align the number (always use the lower bound for memory safety) -> We can set to 32-128 pages, or
    // probably higher as when the system have much RAM, an extra 1 pages probably not a big deal
    shared_buffers = realign_value(shared_buffers, DB_PAGE_SIZE)[options.align_index];
    console.debug(`shared_buffers: ${Math.floor(shared_buffers / Mi)}MiB`);
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
    let pgmem_available = options.usable_ram - group_cache['shared_buffers'];
    let _mem_conns = _GetMemConnInTotal(options, response, false, true);
    pgmem_available -= _mem_conns * options.tuning_kwargs.memory_connection_to_dedicated_os_ratio;
    if ('wal_buffers' in global_cache) {   // I don't know if this make significant impact?
        pgmem_available -= global_cache['wal_buffers'];
    }
    let max_work_buffer_ratio = options.tuning_kwargs.max_work_buffer_ratio;
    let active_connections = _GetNumConnections(options, response, false, false);
    let total_buffers = pgmem_available * max_work_buffer_ratio // active_connections;
    // Minimum to 1 MiB and maximum is varied between workloads
    let max_cap = 1.5 * Gi;
    if (options.workload_type === PG_WORKLOAD.TSR_IOT) {
        max_cap = 256 * Mi;
    }
    if (options.workload_type === PG_WORKLOAD.HTAP || options.workload_type === PG_WORKLOAD.OLAP) {
        // I don't think I will make risk beyond this number
        max_cap = 8 * Gi;
    }
    let temp_buffer_ratio = options.tuning_kwargs.temp_buffers_ratio;
    let temp_buffers = cap_value(total_buffers * temp_buffer_ratio, 1 * Mi, max_cap);
    let work_mem = cap_value(total_buffers * (1 - temp_buffer_ratio), 1 * Mi, max_cap);
    
    // Realign the number (always use the lower bound for memory safety)
    temp_buffers = realign_value(Math.floor(temp_buffers), DB_PAGE_SIZE)[options.align_index];
    work_mem = realign_value(Math.floor(work_mem), DB_PAGE_SIZE)[options.align_index];
    console.debug(`temp_buffers: ${Math.floor(temp_buffers / Mi)}MiB`);
    console.debug(`work_mem: ${Math.floor(work_mem / Mi)}MiB`);
    
    return [temp_buffers, work_mem];
}

function _CalcTempBuffers(group_cache, global_cache, options, response) {
    return _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[0];
}

function _CalcWorkMem(group_cache, global_cache, options, response) {
    return _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[1];
}

function _GetMaxConns(options, group_cache, min_user_conns, max_user_conns) {
    let total_reserved_connections = group_cache['reserved_connections'] + group_cache['superuser_reserved_connections'];
    if (options.tuning_kwargs.user_max_connections !== 0) {
        console.debug('The max_connections variable is overridden by the user so no constraint here.');
        const allowed_connections = options.tuning_kwargs.user_max_connections;
        return allowed_connections + total_reserved_connections;
    }
    // Make a small upscale here to future-proof database scaling, and reduce the number of connections
    let _upscale = __SCALE_FACTOR_CPU_TO_CONNECTION;  // / max(0.75, options.tuning_kwargs.effective_connection_ratio)
    console.debug("The max_connections variable is determined by the number of logical CPU count " + 
        "with the scale factor of ${__SCALE_FACTOR_CPU_TO_CONNECTION}x.");
    let _minimum = Math.max(min_user_conns, total_reserved_connections);
    let max_connections = cap_value(Math.ceil(options.vcpu * _upscale), _minimum, max_user_conns) + total_reserved_connections;
    console.debug(`max_connections: ${max_connections}`);
    return max_connections;
}

function _GetReservedConns(options, minimum, maximum, superuser_mode = false, base_reserved_connection = null) {
    if (base_reserved_connection == null) {
        base_reserved_connection = __BASE_RESERVED_DB_CONNECTION;
    }
    // 1.5x here is heuristically defined to limit the number of superuser reserved connections
    let reserved_connections;
    let descale_factor;
    let superuser_heuristic_percentage;
    if (!superuser_mode) {
        reserved_connections = options.vcpu / __DESCALE_FACTOR_RESERVED_DB_CONNECTION;
    } else {
        superuser_heuristic_percentage = options.tuning_kwargs.superuser_reserved_connections_scale_ratio;
        descale_factor = __DESCALE_FACTOR_RESERVED_DB_CONNECTION * superuser_heuristic_percentage;
        reserved_connections = Math.floor(options.vcpu / descale_factor);
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
    let pgmem_available = Math.floor(options.usable_ram);    // Make a copy
    pgmem_available -= global_cache['shared_buffers'];
    let _mem_conns = _GetMemConnInTotal(options, response, false, true);
    pgmem_available -= _mem_conns * options.tuning_kwargs.memory_connection_to_dedicated_os_ratio;

    // Re-align the number (always use the lower bound for memory safety)
    let effective_cache_size = pgmem_available * options.tuning_kwargs.effective_cache_size_available_ratio;
    effective_cache_size = realign_value(Math.floor(effective_cache_size), DB_PAGE_SIZE)[options.align_index];
    console.debug("Effective cache size: ${Math.floor(effective_cache_size / Mi)}MiB");
    return effective_cache_size;
}

function _CalcWalBuffers(group_cache, global_cache, options, response, minimum, maximum) {
    /*
    See this article: https://www.cybertec-postgresql.com/en/wal_level-what-is-the-difference/
    It is only benefit when you use COPY instead of SELECT. For other thing, the spawning of
    WAL buffers is not necessary. We don't care the large of one single WAL file 
    */
    let shared_buffers = global_cache['shared_buffers'];
    let usable_ram_noswap = options.usable_ram;
    function fn(x) {
        return 1024 * (37.25 * Math.log(x) + 2) * 0.90;  // Measure in KiB
    } 
    let oldstyle_wal_buffers = Math.min(Math.floor(shared_buffers / 32), options.tuning_kwargs.wal_segment_size);  // Measured in bytes
    let wal_buffers = Math.max(oldstyle_wal_buffers, fn(usable_ram_noswap / Gi) * Ki);
    return realign_value(cap_value(Math.ceil(wal_buffers), minimum, maximum), DB_PAGE_SIZE)[options.align_index];
}

// ----------------------------------------------------------------------------------------------------------------
_DB_CONN_PROFILE = {
    // Connections
    'superuser_reserved_connections': {
        'instructions': {
            'mini': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 3, true, 1),
            'medium': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 5, true, 2),
        },
        'tune_op': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 10, true),
        'default': __BASE_RESERVED_DB_CONNECTION,
    },
    'reserved_connections': {
        'instructions': {
            'mini': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 3, false, 1),
            'medium': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 5, false, 2),
        },
        'tune_op': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 10, false),
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
    'listen_addresses': { 'default': '*', }
}

_DB_RESOURCE_PROFILE = {
    // Memory and CPU
    'shared_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcSharedBuffers(options),
        'default': 128 * Mi,
        'partial_func': (value) => `${Math.floor(value / Mi)}MB`,
    },
    'temp_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcTempBuffers(group_cache, global_cache, options, response),
        'default': 8 * Mi,
        'partial_func': (value) => `${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB`,
    },
    'work_mem': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcWorkMem(group_cache, global_cache, options, response),
        'default': 4 * Mi,
        'partial_func': (value) => `${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB`,
    },
    'hash_mem_multiplier': { 'default': 2.0, },
}

_DB_VACUUM_PROFILE = {
    // Memory and Worker
    'autovacuum': { 'default': 'on', },
    'autovacuum_max_workers': {
        'instructions': {
            'mini_default': 1,
            'medium_default': 2,
            'large': (group_cache, global_cache, options, response) =>
                cap_value(Math.floor(options.vcpu / 4) + 1, 2, 5),
            'mall': (group_cache, global_cache, options, response) =>
                cap_value(Math.floor(options.vcpu / 3.5) + 1, 3, 6),
            'bigt': (group_cache, global_cache, options, response) =>
                cap_value(Math.floor(options.vcpu / 3) + 1, 3, 8),
        },
        'default': 3,
        'hardware_scope': 'cpu',
    },
    'autovacuum_naptime': {
        'tune_op': (group_cache, global_cache, options, response) =>
            SECOND * (15 + 30 * (group_cache['autovacuum_max_workers'] - 1)),
        'default': 1 * MINUTE,
        'partial_func': (value) => `${Math.floor(value / SECOND)}s`,
    },
    'maintenance_work_mem': {
        'tune_op': (group_cache, global_cache, options, response) =>
            _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[1],
        'default': 64 * Mi,
        'post-condition-group': (value, cache, options) =>
            value * cache['autovacuum_max_workers'] < Math.floor(options.usable_ram / 2),
        'partial_func': (value) => `${Math.floor(value / Mi)}MB`,
    },
    'autovacuum_work_mem': { 'default': -1, },
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
    'autovacuum_vacuum_cost_delay': { 'default': 2, 'partial_func': (value) => `${value}ms`, },
    'autovacuum_vacuum_cost_limit': { 'default': -1,  },
    'vacuum_cost_delay': { 'default': 0, 'partial_func': (value) => `${value}s`, },
    'vacuum_cost_limit': {
        'instructions': {
            'large_default': 500,
            'mall_default': K10,
            'bigt_default': K10,
        },
        'default': 200,
    },
    'vacuum_cost_page_hit': { 'default': 1, },
    'vacuum_cost_page_miss': { 'default': 2, },
    'vacuum_cost_page_dirty': { 'default': 20, },
    // Transaction ID and MultiXact
    // See here: https://postgresqlco.nf/doc/en/param/autovacuum_freeze_max_age/
    // and https://www.youtube.com/watch?v=vtjjaEVPAb8 at (30:02)
    'autovacuum_freeze_max_age': { 'default': 500 * M10, },
    'vacuum_freeze_table_age': {
        'tune_op': (group_cache, global_cache, options, response) =>
            realign_value(Math.ceil(group_cache['autovacuum_freeze_max_age'] * 0.85),
                250 * K10)[options.align_index],
        'default': 150 * M10,
    },
    'vacuum_freeze_min_age': { 'default': 50 * M10, },
    'autovacuum_multixact_freeze_max_age': { 'default': 850 * M10, },
    'vacuum_multixact_freeze_table_age': {
        'tune_op': (group_cache, global_cache, options, response) =>
            realign_value(Math.ceil(group_cache['autovacuum_multixact_freeze_max_age'] * 0.85),
                250 * K10)[options.align_index],
        'default': 150 * M10,
    },
    'vacuum_multixact_freeze_min_age': { 'default': 5 * M10, },
}

_DB_BGWRITER_PROFILE = {
    // We don't tune the bgwriter_flush_after = 512 KiB as it is already optimal and PostgreSQL said we don't need
    // to tune it
    'bgwriter_delay': {
        'default': 300,
        'hardware_scope': 'overall',
        'partial_func': (value) => `${value}ms`,
    },
    'bgwriter_lru_maxpages': {
        'instructions': {
            'large_default': 350,
            'mall_default': 425,
            'bigt_default': 500,
        },
        'default': 300,
    },
    'bgwriter_lru_multiplier': { 'default': 2.0, },
    'bgwriter_flush_after': {
        'default': 512 * Ki,
        'partial_func': (value) => `${Math.floor(value / Ki)}kB`,
    },
}

_DB_ASYNC_DISK_PROFILE = {
    'effective_io_concurrency': { 'default': 16, },
    'maintenance_io_concurrency': { 'default': 10, },
    'backend_flush_after': { 'default': 0, },
}

_DB_ASYNC_CPU_PROFILE = {
    'max_worker_processes': {
        'tune_op': (group_cache, global_cache, options, response) =>
            cap_value(Math.ceil(options.vcpu * 1.5) + 2, 4, 512),
        'default': 8,
    },
    'max_parallel_workers': {
        'tune_op': (group_cache, global_cache, options, response) =>
            Math.min(cap_value(Math.ceil(options.vcpu * 1.125), 4, 512), group_cache['max_worker_processes']),
        'default': 8,
    },
    'max_parallel_workers_per_gather': {
        'tune_op': (group_cache, global_cache, options, response) =>
            Math.min(cap_value(Math.ceil(options.vcpu / 3), 2, 32), group_cache['max_parallel_workers']),
        'default': 2,
    },
    'max_parallel_maintenance_workers': {
        'tune_op': (group_cache, global_cache, options, response) =>
            Math.min(cap_value(Math.ceil(options.vcpu / 2), 2, 32), group_cache['max_parallel_workers']),
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
        'partial_func': (value) => `${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB`,
    },
    'min_parallel_index_scan_size': {
        'tune_op': (group_cache, global_cache, options, response) => Math.max(group_cache['min_parallel_table_scan_size'] / 16, 512 * Ki),
        'default': 512 * Ki,
        'partial_func': (value) => `${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB`,
    },
}

_DB_WAL_PROFILE = {
    // For these settings, please refer to the [13] and [14] for more information
    'wal_level': { 'default': 'replica', },
    'synchronous_commit': { 'default': 'on', },
    'full_page_writes': { 'default': 'on', },
    'fsync': { 'default': 'on', },
    'wal_compression': { 'default': 'pglz', },
    'wal_init_zero': { 'default': 'on', },
    'wal_recycle': { 'default': 'on', },
    'wal_log_hints': { 'default': 'on', },
    // See Ref [16-19] for tuning the wal_writer_delay and commit_delay
    'wal_writer_delay': {
        'instructions': {
            "mini_default": K10,
        },
        'default': 200,
        'partial_func': (value) => `${value}ms`,
    },
    'wal_writer_flush_after': { 'default': 1 * Mi, 'partial_func': (value) => `${Math.floor(value / Mi)}MB`, },
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
        'partial_func': (value) => `${Math.floor(value / MINUTE)}min`,
    },
    'checkpoint_flush_after': { 'default': 256 * Ki, 'partial_func': (value) => `${Math.floor(value / Ki)}kB`, },
    'checkpoint_completion_target': { 'default': 0.9, },
    'checkpoint_warning': { 'default': 30, 'partial_func': (value) => `${value}s`, },
    // ============================== WAL SIZE ==============================
    'min_wal_size': {
        'tune_op': (group_cache, global_cache, options, response) => 10 * options.tuning_kwargs.wal_segment_size,
        'default': 10 * BASE_WAL_SEGMENT_SIZE,
        'partial_func': (value) => `${Math.floor(value / Mi)}MB`,
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
        'partial_func': (value) => `${Math.floor(value / Mi)}MB`,
    },
    'wal_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => 
            _CalcWalBuffers(group_cache, global_cache, options, response, Math.floor(BASE_WAL_SEGMENT_SIZE / 2),
                            BASE_WAL_SEGMENT_SIZE * 16),
        'default': 2 * BASE_WAL_SEGMENT_SIZE,
        'hardware_scope': 'mem',
    },
    // ============================== ARCHIVE && RECOVERY ==============================
    'archive_mode': { 'default': 'on', },
    'archive_timeout': {
        'instructions': {
            'mini_default': 1 * HOUR,
            'mall_default': 30 * MINUTE,
            'bigt_default': 30 * MINUTE,
        },
        'default': 45 * MINUTE,
        'hardware_scope': 'overall',
        'partial_func': (value) => `${value}s`,
    },
}

_DB_RECOVERY_PROFILE = {
    'recovery_end_command': { 'default': 'pg_ctl stop -D $PGDATA', },
}

_DB_REPLICATION_PROFILE = {
    // Sending Servers
    'max_wal_senders': { 'default': 3, 'hardware_scope': 'net', },
    'max_replication_slots': { 'default': 3, 'hardware_scope': 'net', },
    'wal_keep_size': {
        // Don't worry since if you use replication_slots, its default is -1 (keep all WAL); but if replication
        // for disaster recovery (not for offload READ queries or high-availability)
        'default': 25 * BASE_WAL_SEGMENT_SIZE,
        'partial_func': (value) => `${Math.floor(value / Mi)}MB`,
    },
    'max_slot_wal_keep_size': { 'default': -1, },
    'wal_sender_timeout': {
        'instructions': {
            'mall_default': 2 * MINUTE,
            'bigt_default': 2 * MINUTE,
        },
        'default': MINUTE,
        'hardware_scope': 'net',
        'partial_func': (value) => `${value}s`,
    },
    'track_commit_timestamp': { 'default': 'on', },
    'logical_decoding_work_mem': {
        'tune_op': (group_cache, global_cache, options, response) => 
            realign_value(cap_value(Math.floor(group_cache['maintenance_work_mem'] / 8), 32 * Mi, 2 * Gi),
                DB_PAGE_SIZE)[options.align_index],
        'default': 64 * Mi,
    },
}

_DB_QUERY_PROFILE = {
    // Query tuning
    'seq_page_cost': { 'default': 1.0, },
    'random_page_cost': { 'default': 2.60, },
    'cpu_tuple_cost': { 'default': 0.03, },
    'cpu_index_tuple_cost': { 'default': 0.005, },
    'cpu_operator_cost': { 'default': 0.001, },
    'effective_cache_size': {
        'tune_op': _CalcEffectiveCacheSize,
        'default': 4 * Gi,
        'partial_func': (value) => `${Math.floor(value / Mi)}MB`,
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
            'large': (group_cache, global_cache, options, response) => Math.min(group_cache['cpu_tuple_cost'] * 10, 0.1),
            'mall': (group_cache, global_cache, options, response) => Math.min(group_cache['cpu_tuple_cost'] * 10, 0.1),
            'bigt': (group_cache, global_cache, options, response) => Math.min(group_cache['cpu_tuple_cost'] * 10, 0.1),
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
    'track_activity_query_size': { 'default': 2 * Ki, 'partial_func': (value) => `${value}B`, },
    'track_counts': { 'default': 'on', },
    'track_io_timing': { 'default': 'on', 'hardware_scope': 'cpu', },
}

_DB_LOG_PROFILE = {
    // Where to Log
    'logging_collector': { 'default': 'on', },
    'log_destination': { 'default': 'stderr', },
    'log_directory': { 'default': 'log', },
    'log_filename': { 'default': 'postgresql-%Y-%m-%d_%H%M.log', },
    'log_rotation_age': {
        // For best-case it is good to make the log rotation happens by time-based rather than size-based
        'instructions': {
            'mini_default': 3 * DAY,
            'mall_default': 6 * HOUR,
            'bigt_default': 4 * HOUR,
        },
        'default': 1 * DAY,
        'partial_func': (value) => `${Math.floor(value / HOUR)}h`,
    },
    'log_rotation_size': {
        'instructions': {
            'mini_default': 32 * Mi,
            'medium_default': 64 * Mi,
        },
        'default': 256 * Mi,
        'partial_func': (value) => `${Math.floor(value / Mi)}MB`,
    },
    'log_truncate_on_rotation': { 'default': 'on', },
    // What to log
    'log_autovacuum_min_duration': { 'default': 300 * K10, 'partial_func': (value) => `${Math.floor(value / K10)}s`, },
    'log_checkpoints': { 'default': 'on', },
    'log_connections': { 'default': 'on', },
    'log_disconnections': { 'default': 'on', },
    'log_duration': { 'default': 'on', },
    'log_error_verbosity': { 'default': 'VERBOSE', },
    'log_line_prefix': { 'default': '%m [%p] %quser=%u@%r@%a_db=%d,backend=%b,xid=%x %v,log=%l', },
    'log_lock_waits': { 'default': 'on', },
    'log_recovery_conflict_waits': { 'default': 'on', },
    'log_statement': { 'default': 'mod', },
    'log_replication_commands': { 'default': 'on', },
    'log_min_duration_statement': { 'default': 2 * K10, 'partial_func': (value) => `{value}ms`, },
    'log_min_error_statement': { 'default': 'ERROR', },
    'log_parameter_max_length': {
        'tune_op': (group_cache, global_cache, options, response) => global_cache['track_activity_query_size'],
        'default': -1,
        'partial_func': (value) => `${value}B`,
    },
    'log_parameter_max_length_on_error': {
        'tune_op': (group_cache, global_cache, options, response) => global_cache['track_activity_query_size'],
        'default': -1,
        'partial_func': (value) => `${value}B`,
    },
}

_DB_TIMEOUT_PROFILE = {
    // Transaction Timeout should not be moved away from default, but we can customize the statement_timeout and
    // lock_timeout
    // Add +1 seconds to avoid checkpoint_timeout happens at same time as idle_in_transaction_session_timeout
    'idle_in_transaction_session_timeout': { 'default': 5 * MINUTE + 1, 'partial_func': (value) => `${value}s`, },
    'statement_timeout': { 'default': 0, 'partial_func': (value) => `${value}s`, },
    'lock_timeout': { 'default': 0, 'partial_func': (value) => `${value}s`, },
    'deadlock_timeout': { 'default': 1 * SECOND, 'partial_func': (value) => `${value}s`, },
}

// Library (You don't need to tune these variables as they are not directly related to the database performance)
_DB_LIB_PROFILE = {
    'shared_preload_libraries': {
        'default': 'auto_explain,pg_prewarm,pgstattuple,pg_stat_statements,pg_buffercache,pg_visibility',   // pg_repack, Not pg_squeeze
    },
    // Auto Explain
    'auto_explain.log_min_duration': {
        'tune_op': (group_cache, global_cache, options, response) => 
            realign_value(Math.floor(global_cache['log_min_duration_statement'] * 3 / 2), 20)[options.align_index],
        'default': -1,
        'partial_func': (value) => `${value}ms`,
    },
    'auto_explain.log_analyze': { 'default': 'off', },
    'auto_explain.log_buffers': { 'default': 'on', },
    'auto_explain.log_wal': { 'default': 'on', },
    'auto_explain.log_settings': { 'default': 'off', },
    'auto_explain.log_triggers': { 'default': 'off', },
    'auto_explain.log_verbose': { 'default': 'on', },
    'auto_explain.log_format': { 'default': 'text', },
    'auto_explain.log_level': { 'default': 'LOG', },
    'auto_explain.log_timing': { 'default': 'on', },
    'auto_explain.log_nested_statements': { 'default': 'off', },
    'auto_explain.sample_rate': { 'default': 1.0, },
    // PG_STAT_STATEMENTS
    'pg_stat_statements.max': {
        'instructions': {
            'large_default': 10 * K10,
            'mall_default': 15 * K10,
            'bigt_default': 20 * K10,
        },
        'default': 5 * K10,
    },
    'pg_stat_statements.track': { 'default': 'all', },
    'pg_stat_statements.track_utility': { 'default': 'on', },
    'pg_stat_statements.track_planning': { 'default': 'off', },
    'pg_stat_statements.save': { 'default': 'on', },
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

const DB13_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE };
console.debug(`DB13_CONFIG_PROFILE: ${JSON.stringify(DB13_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_14.py
 */

// Timeout profile
const _DB14_TIMEOUT_PROFILE = {
    "idle_session_timeout": { "default": 0, "partial_func": value => `${value}s`, },
};
// Query profile
const _DB14_QUERY_PROFILE = {
    "track_wal_io_timing": { "default": 'on', },
};
// Vacuum profile
const _DB14_VACUUM_PROFILE = {
    "vacuum_failsafe_age": { "default": 1600000000, },
    "vacuum_multixact_failsafe_age": { "default": 1600000000, }
};

// Merge mapping: use tuples as arrays
const DB14_CONFIG_MAPPING = {
    timeout: [PG_SCOPE.OTHERS, _DB14_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    query: [PG_SCOPE.QUERY_TUNING, _DB14_QUERY_PROFILE, { hardware_scope: 'overall' }],
    maintenance: [PG_SCOPE.MAINTENANCE, _DB14_VACUUM_PROFILE, { hardware_scope: 'overall' }],
};
merge_extra_info_to_profile(DB14_CONFIG_MAPPING);
type_validation(DB14_CONFIG_MAPPING);
let DB14_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE};
if (Object.keys(DB14_CONFIG_MAPPING).length > 0) {
    for (const [key, value] of Object.entries(DB14_CONFIG_MAPPING)) {
        if (key in DB14_CONFIG_PROFILE) {
            // Merge the second element of the tuple (the profile dict)
            deepmerge(DB14_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
        }
    }
    rewrite_items(DB14_CONFIG_PROFILE);
}
console.debug(`DB14_CONFIG_PROFILE: ${JSON.stringify(DB14_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_15.py
 */

// Log profile
const _DB15_LOG_PROFILE = {
    "log_startup_progress_interval": { "default": K10, "partial_func": value => `${value}s`, },
};
// Timeout profile
const _DB15_TIMEOUT_PROFILE = {
    "idle_session_timeout": { "default": 0, "partial_func": value => `${value}s`, },
};
// Query profile
const _DB15_QUERY_PROFILE = {
    "track_wal_io_timing": { "default": 'on', },
};
// Vacuum profile
const _DB15_VACUUM_PROFILE = {
    "vacuum_failsafe_age": { "default": 1600000000, },
    "vacuum_multixact_failsafe_age": { "default": 1600000000, }
};

// Merge mapping: use tuples as arrays
const DB15_CONFIG_MAPPING = {
    log: [PG_SCOPE.LOGGING, _DB15_LOG_PROFILE, { hardware_scope: 'disk' }],
    timeout: [PG_SCOPE.OTHERS, _DB15_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    query: [PG_SCOPE.QUERY_TUNING, _DB15_QUERY_PROFILE, { hardware_scope: 'overall' }],
    maintenance: [PG_SCOPE.MAINTENANCE, _DB15_VACUUM_PROFILE, { hardware_scope: 'overall' }],
};
merge_extra_info_to_profile(DB15_CONFIG_MAPPING);
type_validation(DB15_CONFIG_MAPPING);
let DB15_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE};
if (Object.keys(DB15_CONFIG_MAPPING).length > 0) {
    for (const [key, value] of Object.entries(DB15_CONFIG_MAPPING)) {
        if (key in DB15_CONFIG_PROFILE) {
            // Merge the second element of the tuple (the profile dict)
            deepmerge(DB15_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
        }
    }
    rewrite_items(DB15_CONFIG_PROFILE);
}
console.debug(`DB15_CONFIG_PROFILE: ${JSON.stringify(DB15_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_16.py
 */
// Log profile
const _DB16_LOG_PROFILE = {
	"log_startup_progress_interval": { "default": K10, "partial_func": value => `${value}s`, },
};
// Vacuum profile
const _DB16_VACUUM_PROFILE = {
	"vacuum_buffer_usage_limit": {
		"tune_op": (group_cache, global_cache, options, response) =>
			realign_value(cap_value(Math.floor(group_cache['maintenance_work_mem'] / 16), 2 * Mi, 16 * Gi),
			DB_PAGE_SIZE)[options.align_index],
		"default": 2 * Mi,
		"hardware_scope": "mem",
		"partial_func": value => `${Math.floor(value / Mi)}MB`,
	},
    "vacuum_failsafe_age": { "default": 1600000000, },
    "vacuum_multixact_failsafe_age": { "default": 1600000000, }
};
// WAL profile
const _DB16_WAL_PROFILE = {
	"wal_compression": { "default": "zstd", },
};
// Timeout profile
const _DB16_TIMEOUT_PROFILE = {
    "idle_session_timeout": { "default": 0, "partial_func": value => `${value}s`, },
};
// Query profile
const _DB16_QUERY_PROFILE = {
    "track_wal_io_timing": { "default": 'on', },
};


// Merge mapping: use tuples as arrays
const DB16_CONFIG_MAPPING = {
	log: [PG_SCOPE.LOGGING, _DB16_LOG_PROFILE, { hardware_scope: 'disk' }],
	timeout: [PG_SCOPE.OTHERS, _DB16_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
	query: [PG_SCOPE.QUERY_TUNING, _DB16_QUERY_PROFILE, { hardware_scope: 'overall' }],
	maintenance: [PG_SCOPE.MAINTENANCE, _DB16_VACUUM_PROFILE, { hardware_scope: 'overall' }],
	wal: [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB16_WAL_PROFILE, { hardware_scope: 'disk' }],
};
merge_extra_info_to_profile(DB16_CONFIG_MAPPING);
type_validation(DB16_CONFIG_MAPPING);
let DB16_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE}
if (Object.keys(DB16_CONFIG_MAPPING).length > 0) {
	for (const [key, value] of Object.entries(DB16_CONFIG_MAPPING)) {
		if (key in DB16_CONFIG_PROFILE) {
			// Merge the second element of the tuple (the profile dict)
			deepmerge(DB16_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
		}
	}
	rewrite_items(DB16_CONFIG_PROFILE);
}
console.debug(`DB16_CONFIG_PROFILE: ${JSON.stringify(DB16_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_17.py
 */
// Log profile
const _DB17_LOG_PROFILE = {
	"log_startup_progress_interval": {
		"default": K10,
		"partial_func": value => `${value}s`,
	}
};
// Vacuum profile
const _DB17_VACUUM_PROFILE = {
    "vacuum_buffer_usage_limit": {
        "tune_op": (group_cache, global_cache, options, response) =>
            realign_value(cap_value(Math.floor(group_cache['maintenance_work_mem'] / 16), 2 * Mi, 16 * Gi),
                DB_PAGE_SIZE)[options.align_index],
        "default": 2 * Mi,
        "hardware_scope": "mem",
        "partial_func": value => `${Math.floor(value / Mi)}MB`,
    },
    "vacuum_failsafe_age": { "default": 1600000000, },
    "vacuum_multixact_failsafe_age": { "default": 1600000000, }
};
// WAL profile
const _DB17_WAL_PROFILE = {
	"wal_compression": { "default": "zstd", },
	"summarize_wal": { "default": "on", },
	"wal_summary_keep_time": {
		"default": Math.floor(30 * DAY / MINUTE),
		"partial_func": value => `${Math.floor(value / MINUTE)}min`,
	},
};
// Timeout profile
const _DB17_TIMEOUT_PROFILE = {
    "idle_session_timeout": { "default": 0, "partial_func": value => `${value}s`, },
};
// Query profile
const _DB17_QUERY_PROFILE = {
    "track_wal_io_timing": { "default": 'on', },
};

// Merge mapping: use tuples as arrays
const DB17_CONFIG_MAPPING = {
	log: [PG_SCOPE.LOGGING, _DB17_LOG_PROFILE, { hardware_scope: 'disk' }],
	timeout: [PG_SCOPE.OTHERS, _DB17_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
	query: [PG_SCOPE.QUERY_TUNING, _DB17_QUERY_PROFILE, { hardware_scope: 'overall' }],
	maintenance: [PG_SCOPE.MAINTENANCE, _DB17_VACUUM_PROFILE, { hardware_scope: 'overall' }],
	wal: [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB17_WAL_PROFILE, { hardware_scope: 'disk' }],
};
merge_extra_info_to_profile(DB17_CONFIG_MAPPING);
type_validation(DB17_CONFIG_MAPPING);
let DB17_CONFIG_PROFILE = { ...DB0_CONFIG_PROFILE}
if (Object.keys(DB17_CONFIG_MAPPING).length > 0) {
	for (const [key, value] of Object.entries(DB17_CONFIG_MAPPING)) {
		if (key in DB17_CONFIG_PROFILE) {
			// Merge the second element of the tuple (the profile dict)
			deepmerge(DB17_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
		}
	}
	rewrite_items(DB17_CONFIG_PROFILE);
}
console.debug(`DB17_CONFIG_PROFILE: ${JSON.stringify(DB17_CONFIG_PROFILE)}`);

// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/shared.py
 * This module is to perform specific tuning and calculation on the PostgreSQL database server.
 */

// The time required to create, opened and close a file. This has been tested with all disk cache flushed,
// Windows (NTFS) and Linux (EXT4/XFS) on i7-8700H with Python 3.12 on NVMEv3 SSD and old HDD
const _FILE_ROTATION_TIME_MS = 0.21 * 2  // 0.21 ms on average when direct bare-metal, 2-3x on virtualized
function wal_time(wal_buffers, data_amount_ratio, wal_segment_size, wal_writer_delay_in_ms, wal_throughput) {
    // The time required to flush the full WAL buffers to disk (assuming we have no write after the flush)
    // or wal_writer_delay is being woken up or 2x of wal_buffers are synced
    console.debug('Estimate the time required to flush the full WAL buffers to disk');
    const data_amount = Math.floor(wal_buffers * data_amount_ratio);
    const num_wal_files_required = Math.floor(data_amount / wal_segment_size) + 1;
    const rotate_time_in_ms = num_wal_files_required * _FILE_ROTATION_TIME_MS;
    const write_time_in_ms = (data_amount / Mi) / wal_throughput * K10;

    // Calculate maximum how many delay time
    let delay_time = 0;
    if (data_amount_ratio > 1) {
        let num_delay = Math.floor(data_amount_ratio);
        const fractional = data_amount_ratio - num_delay;
        if (fractional === 0) {
            num_delay -= 1;
        }
        delay_time = num_delay * wal_writer_delay_in_ms;
    }
    const total_time = rotate_time_in_ms + write_time_in_ms + delay_time;
    const msg = `Estimate the time required to flush the full-queued WAL buffers ${bytesize_to_hr(data_amount)} to disk: rotation time: ${rotate_time_in_ms.toFixed(2)} ms, write time: ${write_time_in_ms.toFixed(2)} ms, delay time: ${delay_time.toFixed(2)} ms --> Total: ${total_time.toFixed(2)} ms with ${num_wal_files_required} WAL files.`;
    return {
        numWalFiles: num_wal_files_required,
        rotateTime: rotate_time_in_ms,
        writeTime: write_time_in_ms,
        delayTime: delay_time,
        totalTime: total_time,
        msg: msg
    };
}

function checkpoint_time(checkpoint_timeout_second, checkpoint_completion_target, shared_buffers,
                         shared_buffers_ratio, effective_cache_size, max_wal_size, data_disk_iops) {
    console.debug('Estimate the time required to flush the full WAL buffers to disk');
    const checkpoint_duration = Math.ceil(checkpoint_timeout_second * checkpoint_completion_target);
    const data_tran_tput = PG_DISK_PERF.iops_to_throughput(data_disk_iops)
    const data_max_mib_written = data_tran_tput * checkpoint_duration;

    let data_amount = Math.floor(shared_buffers * shared_buffers_ratio);    // Measured in bytes
    data_amount = Math.min(data_amount, effective_cache_size, max_wal_size);  // Measured in bytes
    const page_amount = Math.floor(data_amount / DB_PAGE_SIZE);
    const data_write_time = Math.floor((data_amount / Mi) / data_tran_tput);  // Measured in seconds
    const data_disk_utilization = data_write_time / checkpoint_duration;
    return {
        'checkpoint_duration': checkpoint_duration,
        'data_disk_translated_tput': data_tran_tput,
        'data_disk_max_mib_written': data_max_mib_written,

        'data_amount': data_amount,
        'page_amount': page_amount,

        'data_write_time': data_write_time,
        'data_disk_utilization': data_disk_utilization,
    }
}

function vacuum_time(hit_cost, miss_cost, dirty_cost, delay_ms, cost_limit, data_disk_iops) {
    console.debug('Estimate the time required to vacuum the dirty pages');
    const budget_per_sec = Math.ceil(cost_limit / delay_ms * K10);
    // Estimate the maximum number of pages that can be vacuumed in one second
    const max_num_hit_page = Math.floor(budget_per_sec / hit_cost);
    const max_num_miss_page = Math.floor(budget_per_sec / miss_cost);
    const max_num_dirty_page = Math.floor(budget_per_sec / dirty_cost);
    // Calculate the data amount in MiB per cycle
    const max_hit_data = PG_DISK_PERF.iops_to_throughput(max_num_hit_page);
    const max_miss_data = PG_DISK_PERF.iops_to_throughput(max_num_miss_page);
    const max_dirty_data = PG_DISK_PERF.iops_to_throughput(max_num_dirty_page);
    // Some informative message
    const _disk_tput = PG_DISK_PERF.iops_to_throughput(data_disk_iops);
    const _msg = `Reporting the time spent for normal vacuuming with the cost budget of ${budget_per_sec} in 1 second. 
HIT (page in shared_buffers): ${max_num_hit_page} page -> Throughput: ${max_hit_data.toFixed(2)} MiB/s -> Safe to GO: ${max_hit_data < 10 * K10} (< 10 GiB/s for low DDR3)
MISS (page in disk cache): ${max_num_miss_page} page -> Throughput: ${max_miss_data.toFixed(2)} MiB/s -> Safe to GO: ${max_miss_data < 5 * K10} (< 5 GiB/s for low DDR3)
DIRTY (page in disk): ${max_num_dirty_page} page -> Throughput: ${max_dirty_data.toFixed(2)} MiB/s -> Safe to GO: ${max_dirty_data < _disk_tput} (< Data Disk IOPS)`;

    // Scenario: 5:5:1 (frequent vacuum) or 1:1:1 (rarely vacuum)
    const _551page = Math.floor(budget_per_sec / (5 * hit_cost + 5 * miss_cost + dirty_cost));
    const _551data = PG_DISK_PERF.iops_to_throughput(_551page * 5 + _551page);
    const _111page = Math.floor(budget_per_sec / (hit_cost + miss_cost + dirty_cost));
    const _111data = PG_DISK_PERF.iops_to_throughput(_111page * 1 + _111page);
    return {
        max_num_hit_page: max_num_hit_page,
        max_num_miss_page: max_num_miss_page,
        max_num_dirty_page: max_num_dirty_page,
        max_hit_data: max_hit_data,
        max_miss_data: max_miss_data,
        max_dirty_data: max_dirty_data,
        '5:5:1_page': _551page,
        '5:5:1_data': _551data,
        '1:1:1_page': _111page,
        '1:1:1_data': _111data,
        msg: _msg
    }
}

function vacuum_scale(threshold, scale_factor) {
    console.debug('Estimate the number of changed or dead tuples to trigger normal vacuum');
    const _fn = (num_rows) => Math.floor(threshold + scale_factor * num_rows);
    // Table Size (small): 10K rows
    const dead_at_10k = _fn(10_000);
    // Table Size (medium): 300K rows
    const dead_at_300k = _fn(300_000);
    // Table Size (large): 10M rows
    const dead_at_10m = _fn(10_000_000);
    // Table Size (giant): 300M rows
    const dead_at_100m = _fn(100_000_000);
    // Table Size (huge): 1B rows
    const dead_at_1b = _fn(1_000_000_000);
    // Table Size (giant): 10B rows
    const dead_at_10b = _fn(10_000_000_000);

    const msg = `The threshold of ${threshold} will trigger the normal vacuum when the number of changed or dead tuples exceeds ${threshold * scale_factor} tuples.
-> Table Size: 10K rows -> Dead Tuples: ${dead_at_10k} tuples
-> Table Size: 300K rows -> Dead Tuples: ${dead_at_300k} tuples
-> Table Size: 10M rows -> Dead Tuples: ${dead_at_10m} tuples
-> Table Size: 100M rows -> Dead Tuples: ${dead_at_100m} tuples
-> Table Size: 1B rows -> Dead Tuples: ${dead_at_1b} tuples
-> Table Size: 10B rows -> Dead Tuples: ${dead_at_10b} tuples`;
    return {
        '10k': dead_at_10k,
        '300k': dead_at_300k,
        '10m': dead_at_10m,
        '100m': dead_at_100m,
        '1b': dead_at_1b,
        '10b': dead_at_10b,
        msg: msg
    }
}


// ==================================================================================
/**
 * Original Source File: ./src/tuner/pg_dataclass.py
 */
class PG_TUNE_REQUEST {
    constructor(options) {
        this.options = options;
        this.include_comment = options.include_comment || false;
        this.custom_style = options.custom_style || null;
    }
}

// This section is managed by the application
class PG_TUNE_RESPONSE {
    constructor() {
        this.outcome = { }
        this.outcome_cache = { }
        this.outcome[PGTUNER_SCOPE.DATABASE_CONFIG] = {};
        this.outcome_cache[PGTUNER_SCOPE.DATABASE_CONFIG] = {};
    }

    get_managed_items(target, scope) {
        return this.outcome.get(target).get(scope);
    }

    get_managed_cache(target) {
        return this.outcome_cache.get(target);
    }

    _generate_content_as_file(target, request, backup_settings = true, exclude_names = null) {
        let content = [target.disclaimer(), '\n'];
        if (backup_settings) {
            content.push(`# User Options: ${JSON.stringify(request.options)}\n`);
        }
        for (const [scope, items] of this.outcome.get(target)) {
            content.push(`## ===== SCOPE: ${scope} ===== \n`);
            for (const [item_name, item] of items) {
                if (exclude_names === null || !exclude_names.has(item_name)) {
                    content.push(item.out(request.include_comment, request.custom_style));
                }
                content.push('\n' + (request.include_comment ? '\n\n\n' : '\n'));
            }
        }
        return content.join('');
    }

    _generate_content_as_response(target, exclude_names = null, output_format = 'conf') {
        let content = {};
        for (const [_, items] of this.outcome.get(target)) {
            for (const [item_name, item] of items) {
                if (exclude_names === null || !exclude_names.has(item_name)) {
                    content[item_name] = item.out_display(null);
                }
            }
        }
        if (output_format === 'conf') {
            return Object.entries(content).map(([k, v]) => `${k} = ${v}`).join('\n');
        }
        return content;
    }

    generate_content(target, request, exclude_names = null, backup_settings = true, output_format = 'conf') {
        if (exclude_names !== null && Array.isArray(exclude_names)) {
            exclude_names = new Set(exclude_names);
        }
        if (output_format === 'file') {
            return this._generate_content_as_file(target, request, backup_settings, exclude_names);
        } else if (['json', 'conf'].includes(output_format)) {
            return this._generate_content_as_response(target, exclude_names, output_format);
        } else {
            throw new Error(`Invalid output format: ${output_format}. Expected one of "json", "conf", "file".`);
        }
    }

    report(options, use_full_connection = false, ignore_report = true) {
        // Cache result first
        const _kwargs = options.tuning_kwargs;
        const usable_ram_noswap = options.usable_ram;
        const usable_ram_noswap_hr = bytesize_to_hr(usable_ram_noswap);
        const total_ram = options.total_ram;
        const total_ram_hr = bytesize_to_hr(total_ram);
        const usable_ram_noswap_ratio = usable_ram_noswap / total_ram;
        const managed_cache = this.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG);

        // Number of Connections
        const max_user_conns = (managed_cache['max_connections'] - managed_cache['superuser_reserved_connections'] - managed_cache['reserved_connections']);
        const os_conn_overhead = (max_user_conns * _kwargs.single_memory_connection_overhead * _kwargs.memory_connection_to_dedicated_os_ratio);
        let num_user_conns = max_user_conns;
        if (!use_full_connection) {
            num_user_conns = Math.ceil(max_user_conns * _kwargs.effective_connection_ratio);
        }

        // Shared Buffers and WAL buffers
        const shared_buffers = managed_cache['shared_buffers'];
        const wal_buffers = managed_cache['wal_buffers'];

        // Temp Buffers and Work Mem
        const temp_buffers = managed_cache['temp_buffers'];
        const work_mem = managed_cache['work_mem'];
        const hash_mem_multiplier = managed_cache['hash_mem_multiplier'];

        // Higher level would assume more hash-based operations, which reduce the work_mem in correction-tuning phase
        // Smaller level would assume less hash-based operations, which increase the work_mem in correction-tuning phase
        // real_world_work_mem = work_mem * hash_mem_multiplier
        const real_world_mem_scale = generalized_mean(1, hash_mem_multiplier, _kwargs.hash_mem_usage_level);
        const real_world_work_mem = work_mem * real_world_mem_scale;
        const total_working_memory = (temp_buffers + real_world_work_mem);
        const total_working_memory_hr = bytesize_to_hr(total_working_memory);

        let max_total_memory_used = shared_buffers + wal_buffers + os_conn_overhead;
        max_total_memory_used += total_working_memory * num_user_conns;
        const max_total_memory_used_ratio = max_total_memory_used / usable_ram_noswap;
        const max_total_memory_used_hr = bytesize_to_hr(max_total_memory_used);

        if (ignore_report && !_kwargs.mem_pool_parallel_estimate) {
            return ['', max_total_memory_used];
        }

        // Work Mem but in Parallel
        const _parallel_report = this.calc_worker_in_parallel(options, num_user_conns);
        const num_parallel_workers = _parallel_report['num_parallel_workers'];
        const num_sessions = _parallel_report['num_sessions'];
        const num_sessions_in_parallel = _parallel_report['num_sessions_in_parallel'];
        const num_sessions_not_in_parallel = _parallel_report['num_sessions_not_in_parallel'];

        const parallel_work_mem_total = real_world_work_mem * (num_parallel_workers + num_sessions_in_parallel);
        const parallel_work_mem_in_session = real_world_work_mem * (1 + managed_cache['max_parallel_workers_per_gather']);

        // Ensure the number of active user connections always larger than the num_sessions
        // The maximum 0 here is meant that all connections can have full parallelism
        const single_work_mem_total = real_world_work_mem * num_sessions_not_in_parallel;
        let max_total_memory_used_with_parallel = shared_buffers + wal_buffers + os_conn_overhead;
        max_total_memory_used_with_parallel += (parallel_work_mem_total + single_work_mem_total);
        max_total_memory_used_with_parallel += temp_buffers * num_user_conns;
        const max_total_memory_used_with_parallel_ratio = max_total_memory_used_with_parallel / usable_ram_noswap;
        const max_total_memory_used_with_parallel_hr = bytesize_to_hr(max_total_memory_used_with_parallel);
        const _epsilon_scale = use_full_connection ? 4 : 2;

        if (ignore_report && _kwargs.mem_pool_parallel_estimate) {
            return ['', max_total_memory_used_with_parallel];
        }

        // Effective Cache Size
        const effective_cache_size = managed_cache['effective_cache_size'];

        // WAL Times
        const wal_throughput = options.wal_spec.perf()[0];
        const wal10 = wal_time(wal_buffers, 1.0, _kwargs.wal_segment_size, managed_cache['wal_writer_delay'], wal_throughput);
        const wal15 = wal_time(wal_buffers, 1.5, _kwargs.wal_segment_size, managed_cache['wal_writer_delay'], wal_throughput);
        const wal20 = wal_time(wal_buffers, 2.0, _kwargs.wal_segment_size, managed_cache['wal_writer_delay'], wal_throughput);

        // Vacuum and Maintenance
        let real_autovacuum_work_mem = managed_cache['autovacuum_work_mem'];
        if (real_autovacuum_work_mem === -1) {
            real_autovacuum_work_mem = managed_cache['maintenance_work_mem'];
        }
        if (options.pgsql_version < 17) {
            // The VACUUM use adaptive radix tree which performs better and not being silently capped at 1 GiB
            // since PostgreSQL 17+
            // https://www.postgresql.org/docs/17/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM
            // and https://www.postgresql.org/docs/16/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM
            real_autovacuum_work_mem = Math.min(1 * Gi, real_autovacuum_work_mem);
        }

        // Checkpoint Timing
        const [data_tput, data_iops] = options.data_index_spec.perf()
        const checkpoint_timeout = managed_cache['checkpoint_timeout'];
        const checkpoint_completion_target = managed_cache['checkpoint_completion_target'];
        const _ckpt_iops = PG_DISK_PERF.throughput_to_iops(0.70 * generalized_mean(PG_DISK_PERF.iops_to_throughput(data_iops), data_tput, -2.5));   // The merge between sequential IOPS and random IOPS with weighted average of -2.5 and 70% efficiency
        const ckpt05 = checkpoint_time(checkpoint_timeout, checkpoint_completion_target, shared_buffers, 0.05, effective_cache_size, managed_cache['max_wal_size'], _ckpt_iops);
        const ckpt30 = checkpoint_time(checkpoint_timeout, checkpoint_completion_target, shared_buffers, 0.30, effective_cache_size, managed_cache['max_wal_size'], _ckpt_iops);
        const ckpt95 = checkpoint_time(checkpoint_timeout, checkpoint_completion_target, shared_buffers, 0.95, effective_cache_size, managed_cache['max_wal_size'], _ckpt_iops);

        // Background Writers
        const bgwriter_page_per_second = Math.ceil(managed_cache['bgwriter_lru_maxpages'] * (K10 / managed_cache['bgwriter_delay']));
        const bgwriter_throughput = PG_DISK_PERF.iops_to_throughput(bgwriter_page_per_second);

        // Auto-vacuum and Maintenance
        const vacuum_report = vacuum_time(managed_cache['vacuum_cost_page_hit'], managed_cache['vacuum_cost_page_miss'], managed_cache['vacuum_cost_page_dirty'], managed_cache['autovacuum_vacuum_cost_delay'], managed_cache['vacuum_cost_limit'], data_iops);
        const normal_vacuum = vacuum_scale(managed_cache['autovacuum_vacuum_threshold'], managed_cache['autovacuum_vacuum_scale_factor']);
        const normal_analyze = vacuum_scale(managed_cache['autovacuum_analyze_threshold'], managed_cache['autovacuum_analyze_scale_factor']);
        // See the PostgreSQL source code of how they sample randomly to get statistics
        const _sampling_rows = 300 * managed_cache['default_statistics_target'];

        // Anti-wraparound Vacuum
        // Transaction ID
        const num_hourly_write_transaction = options.num_write_transaction_per_hour_on_workload;
        const min_hr_txid = managed_cache['vacuum_freeze_min_age'] / num_hourly_write_transaction;
        const norm_hr_txid = managed_cache['vacuum_freeze_table_age'] / num_hourly_write_transaction;
        const max_hr_txid = managed_cache['autovacuum_freeze_max_age'] / num_hourly_write_transaction;

        // Row Locking in Transaction
        const min_hr_row_lock = managed_cache['vacuum_multixact_freeze_min_age'] / num_hourly_write_transaction;
        const norm_hr_row_lock = managed_cache['vacuum_multixact_freeze_table_age'] / num_hourly_write_transaction;
        const max_hr_row_lock = managed_cache['autovacuum_multixact_freeze_max_age'] / num_hourly_write_transaction;

        // Report
        const _report = `
# ===============================================================        
# Memory Estimation Test by ${APP_NAME_UPPER}
From server-side, the PostgreSQL memory usable arena is at most ${usable_ram_noswap_hr} or ${(usable_ram_noswap_ratio * 100).toFixed(2)} (%) of the total RAM (${total_ram_hr}).
    All other variables must be bounded and computed within the available memory.
    CPU: ${options.vcpu} logical cores
RAM: ${total_ram_hr} or ratio: ${((total_ram / options.vcpu / Gi).toFixed(1))}.

Arguments: use_full_connection=${use_full_connection}
Report Summary (memory, over usable RAM):
----------------------------------------
* PostgreSQL memory (estimate): ${max_total_memory_used_hr} or ${(max_total_memory_used_ratio * 100).toFixed(2)} (%) over usable RAM.
    - The Shared Buffers is ${bytesize_to_hr(shared_buffers)} or ${(shared_buffers / usable_ram_noswap * 100).toFixed(2)} (%)
    - The Wal Buffers is ${bytesize_to_hr(wal_buffers)} or ${(wal_buffers / usable_ram_noswap * 100).toFixed(2)} (%)
    - The connection overhead is ${bytesize_to_hr(os_conn_overhead)} with ${num_user_conns} total user connections
        + Active user connections: ${max_user_conns}
        + Peak assumption is at ${bytesize_to_hr(os_conn_overhead / _kwargs.memory_connection_to_dedicated_os_ratio)}
        + Reserved & Superuser Reserved Connections: ${managed_cache['max_connections'] - max_user_conns}
        + Need Connection Pool such as PgBouncer: ${num_user_conns >= 100}
    - The total maximum working memory (assuming with one full use of work_mem and temp_buffers):
        + SINGLE: ${total_working_memory_hr} per user connections or ${(total_working_memory / usable_ram_noswap * 100).toFixed(2)} (%)
            -> Real-World Mem Scale: ${(_kwargs.temp_buffers_ratio + (1 - _kwargs.temp_buffers_ratio) * real_world_mem_scale).toFixed(2)}
            -> Temp Buffers: ${bytesize_to_hr(temp_buffers)} :: Work Mem: ${bytesize_to_hr(work_mem)}
            -> Hash Mem Multiplier: ${hash_mem_multiplier} ::  Real-World Work Mem: ${bytesize_to_hr(real_world_work_mem)}
            -> Total: ${(total_working_memory * num_user_conns / usable_ram_noswap * 100).toFixed(2)} (%)
        + PARALLEL:
            -> Workers :: Gather Workers=${managed_cache['max_parallel_workers_per_gather']} :: Worker in Pool=${managed_cache['max_parallel_workers']} << Workers Process=${managed_cache['max_worker_processes']}
            -> Parallelized Session: ${num_sessions_in_parallel} :: Non-parallelized Session: ${num_sessions_not_in_parallel}
            -> Work memory assuming single query (1x work_mem)
                * Total parallelized sessions = ${num_sessions} with ${num_sessions_in_parallel - num_sessions} leftover session
                * Maximum work memory in parallelized session(s) without temp_buffers :
                    - 1 parallelized session: ${bytesize_to_hr(parallel_work_mem_in_session)} or ${(parallel_work_mem_in_session / usable_ram_noswap * 100).toFixed(2)} (%)
                    - Total (in parallel): ${bytesize_to_hr(parallel_work_mem_total)} or ${(parallel_work_mem_total / usable_ram_noswap * 100).toFixed(2)} (%)
                    - Total (in single): ${bytesize_to_hr(single_work_mem_total)} or ${(single_work_mem_total / usable_ram_noswap * 100).toFixed(2)} (%)
                * Maximum work memory in parallelized session(s) with temp_buffers:
                    - 1 parallelized session: ${bytesize_to_hr(parallel_work_mem_in_session + temp_buffers)} or ${((parallel_work_mem_in_session + temp_buffers) / usable_ram_noswap * 100).toFixed(2)} (%)
                    - Total (in parallel): ${bytesize_to_hr(parallel_work_mem_total + temp_buffers * num_user_conns)} or ${((parallel_work_mem_total + temp_buffers * num_user_conns) / usable_ram_noswap * 100).toFixed(2)} (%)
                    - Total (in single): ${bytesize_to_hr(single_work_mem_total + temp_buffers * num_user_conns)} or ${((single_work_mem_total + temp_buffers * num_user_conns) / usable_ram_noswap * 100).toFixed(2)} (%)
    - Effective Cache Size: ${bytesize_to_hr(effective_cache_size)} or ${(effective_cache_size / usable_ram_noswap * 100).toFixed(2)} (%)

* Zero parallelized session >> Memory in use: ${max_total_memory_used_hr}
    - Memory Ratio: ${(max_total_memory_used_ratio * 100).toFixed(2)} (%)
    - Normal Memory Usage: ${max_total_memory_used_ratio <= Math.min(1.0, _kwargs.max_normal_memory_usage)} (${(_kwargs.max_normal_memory_usage * 100).toFixed(1)} % memory threshold)
    - P3: Generally Safe in Workload: ${max_total_memory_used_ratio <= 0.70} (70 % memory threshold)
    - P2: Sufficiently Safe for Production: ${max_total_memory_used_ratio <= 0.80} (80 % memory threshold)
    - P1: Risky for Production: ${max_total_memory_used_ratio <= 0.90} (90 % memory threshold)
* With parallelized session >> Memory in use: ${max_total_memory_used_with_parallel_hr}
    - Memory Ratio: ${(max_total_memory_used_with_parallel_ratio * 100).toFixed(2)} (%)
    - Normal Memory Usage: ${max_total_memory_used_with_parallel_ratio <= Math.min(1.0, _kwargs.max_normal_memory_usage)} (${(_kwargs.max_normal_memory_usage * 100).toFixed(1)} % memory threshold)
    - P3: Generally Safe in Workload: ${max_total_memory_used_with_parallel_ratio <= 0.70} (70 % memory threshold)
    - P2: Sufficiently Safe for Production: ${max_total_memory_used_with_parallel_ratio <= 0.80} (80 % memory threshold)
    - P1: Risky for Production: ${max_total_memory_used_with_parallel_ratio <= 0.90} (90 % memory threshold)

Report Summary (others):
-----------------------  
* Maintenance and (Auto-)Vacuum:
    - Autovacuum (by definition): ${managed_cache['autovacuum_work_mem']}
        + Working memory per worker: ${bytesize_to_hr(real_autovacuum_work_mem)}
        + Max Workers: ${managed_cache['autovacuum_max_workers']} --> Total Memory: ${bytesize_to_hr(real_autovacuum_work_mem * managed_cache['autovacuum_max_workers'])} or ${(real_autovacuum_work_mem * managed_cache['autovacuum_max_workers'] / usable_ram_noswap * 100).toFixed(2)} (%)
    - Maintenance:
        + Max Workers: ${managed_cache['max_parallel_maintenance_workers']}
        + Total Memory: ${bytesize_to_hr(managed_cache['maintenance_work_mem'] * managed_cache['max_parallel_maintenance_workers'])} or ${(managed_cache['maintenance_work_mem'] * managed_cache['max_parallel_maintenance_workers'] / usable_ram_noswap * 100).toFixed(2)} (%)
        + Parallel table scan size: ${bytesize_to_hr(managed_cache['min_parallel_table_scan_size'])}
        + Parallel index scan size: ${bytesize_to_hr(managed_cache['min_parallel_index_scan_size'])}
    - Autovacuum Trigger (table-level):
        + Vacuum  :: Scale Factor=${(managed_cache['autovacuum_vacuum_scale_factor'] * 100).toFixed(2)} (%) :: Threshold=${managed_cache['autovacuum_vacuum_threshold']}
        + Analyze :: Scale Factor=${(managed_cache['autovacuum_analyze_scale_factor'] * 100).toFixed(2)} (%) :: Threshold=${managed_cache['autovacuum_analyze_threshold']}
        + Insert  :: Scale Factor=${(managed_cache['autovacuum_vacuum_insert_scale_factor'] * 100).toFixed(2)} (%) :: Threshold=${managed_cache['autovacuum_vacuum_insert_threshold']}
        Report when number of dead tuples is reached:
        + 10K rows :: Vacuum=${normal_vacuum['10k']} :: Insert/Analyze=${normal_analyze['10k']}
        + 300K rows :: Vacuum=${normal_vacuum['300k']} :: Insert/Analyze=${normal_analyze['300k']}
        + 10M rows :: Vacuum=${normal_vacuum['10m']} :: Insert/Analyze=${normal_analyze['10m']}
        + 100M rows :: Vacuum=${normal_vacuum['100m']} :: Insert/Analyze=${normal_analyze['100m']}
        + 1B rows :: Vacuum=${normal_vacuum['1b']} :: Insert/Analyze=${normal_analyze['1b']}
    - Cost-based Vacuum:  
        + Page Cost Relative Factor :: Hit=${managed_cache['vacuum_cost_page_hit']} :: Miss=${managed_cache['vacuum_cost_page_miss']} :: Dirty/Disk=${managed_cache['vacuum_cost_page_dirty']}
        + Autovacuum cost: ${managed_cache['autovacuum_vacuum_cost_limit']} --> Vacuum cost: ${managed_cache['vacuum_cost_limit']}
        + Autovacuum delay: ${managed_cache['autovacuum_vacuum_cost_delay']} (ms) --> Vacuum delay: ${managed_cache['vacuum_cost_delay']} (ms)
        + IOPS Spent: ${(data_iops * _kwargs.autovacuum_utilization_ratio).toFixed(1)} pages or ${PG_DISK_PERF.iops_to_throughput((data_iops * _kwargs.autovacuum_utilization_ratio).toFixed(1))} MiB/s
        + Vacuum Report on Worst Case Scenario:
            We safeguard against WRITE since most READ in production usually came from RAM/cache before auto-vacuuming, but not safeguard against pure, zero disk read.
            -> Hit (page in shared_buffers): Maximum ${vacuum_report['max_num_hit_page']} pages or RAM throughput ${(vacuum_report['max_hit_data']).toFixed(2)} MiB/s
                RAM Safety: ${vacuum_report['max_hit_data'] < 10 * K10} (< 10 GiB/s for low DDR3)
            -> Miss (page in disk cache): Maximum ${vacuum_report['max_num_miss_page']} pages or Disk throughput ${(vacuum_report['max_miss_data']).toFixed(2)} MiB/s
                # See encoding here: https://en.wikipedia.org/wiki/64b/66b_encoding; NVME SSD with PCIe 3.0+ or USB 3.1
                NVME10 Safety: ${vacuum_report['max_miss_data'] < 10 / 8 * 64 / 66 * K10} (< 10 GiB/s, 64b/66b encoding)
                SATA3 Safety: ${vacuum_report['max_miss_data'] < 6 / 8 * 6 / 8 * K10} (< 6 GiB/s, 6b/8b encoding)
                Disk Safety: ${vacuum_report['max_num_miss_page'] < data_iops} (< Data Disk IOPS)
            -> Dirty (page in data disk volume): Maximum ${vacuum_report['max_num_dirty_page']} pages or Disk throughput ${(vacuum_report['max_dirty_data']).toFixed(2)} MiB/s
                Disk Safety: ${vacuum_report['max_num_dirty_page'] < data_iops} (< Data Disk IOPS)
        + Other Scenarios with H:M:D ratio as 5:5:1 (frequent), or 1:1:1 (rarely)
            5:5:1 or ${vacuum_report['5:5:1_page'] * 6} disk pages -> IOPS capacity of ${(vacuum_report['5:5:1_data']).toFixed(2)} MiB/s (write=${(vacuum_report['5:5:1_data'] * 1 / 6).toFixed(2)} MiB/s)
            -> Safe: ${vacuum_report['5:5:1_page'] * 6 < data_iops} (< Data Disk IOPS)
            1:1:1 or ${vacuum_report['1:1:1_page'] * 3} disk pages -> IOPS capacity of ${(vacuum_report['1:1:1_data']).toFixed(2)} MiB/s (write=${(vacuum_report['1:1:1_data'] * 1 / 2).toFixed(2)} MiB/s)
            -> Safe: ${vacuum_report['1:1:1_page'] * 3 < data_iops} (< Data Disk IOPS)
    - Transaction (Tran) ID Wraparound and Anti-Wraparound Vacuum:
        + Workload Write Transaction per Hour: ${num_hourly_write_transaction}
        + TXID Vacuum :: Minimum=${min_hr_txid.toFixed(2)} hrs :: Manual=${norm_hr_txid.toFixed(2)} hrs :: Auto-forced=${max_hr_txid.toFixed(2)} hrs
        + XMIN,XMAX Vacuum :: Minimum=${min_hr_row_lock.toFixed(2)} hrs :: Manual=${norm_hr_row_lock.toFixed(2)} hrs :: Auto-forced=${max_hr_row_lock.toFixed(2)} hrs

* Background Writers:
    - Delay: ${managed_cache['bgwriter_delay']} (ms) for maximum ${managed_cache['bgwriter_lru_maxpages']} dirty pages
        + ${bgwriter_page_per_second} pages per second or ${bgwriter_throughput.toFixed(1)} MiB/s in random WRITE IOPs

* Checkpoint:        
    - Effective Timeout: ${(checkpoint_timeout * checkpoint_completion_target).toFixed(1)} seconds (${checkpoint_timeout}::${checkpoint_completion_target})
    - Checkpoint timing analysis at 70% random IOPS:
        + 5% of shared_buffers:
            -> Data Amount: ${bytesize_to_hr(ckpt05['data_amount'])} :: ${ckpt05['page_amount']} pages
            -> Expected Time: ${ckpt05['data_write_time']} seconds with ${ckpt05['data_disk_utilization'] * 100} (%) utilization
            -> Safe Test :: Time-based Check <- ${ckpt05['data_write_time'] <= checkpoint_timeout * checkpoint_completion_target}
        + 30% of shared_buffers:
            -> Data Amount: ${bytesize_to_hr(ckpt30['data_amount'])} :: ${ckpt30['page_amount']} pages
            -> Expected Time: ${ckpt30['data_write_time']} seconds with ${ckpt30['data_disk_utilization'] * 100} (%) utilization
            -> Safe Test :: Time-based Check <- ${ckpt30['data_write_time'] <= checkpoint_timeout * checkpoint_completion_target}
        + 95% of shared_buffers:
            -> Data Amount: ${bytesize_to_hr(ckpt95['data_amount'])} :: ${ckpt95['page_amount']} pages
            -> Expected Time: ${ckpt95['data_write_time']} seconds with ${ckpt95['data_disk_utilization'] * 100} (%) utilization
            -> Safe Test :: Time-based Check <- ${ckpt95['data_write_time'] <= checkpoint_timeout * checkpoint_completion_target}
            
* Query Planning and Optimization:
    - Page Cost :: Sequential=${managed_cache['seq_page_cost'].toFixed(2)} :: Random=${managed_cache['random_page_cost'].toFixed(2)}
    - CPU Cost :: Tuple=${managed_cache['cpu_tuple_cost'].toFixed(4)} :: Index=${managed_cache['cpu_index_tuple_cost'].toFixed(4)} :: Operator=${managed_cache['cpu_operator_cost'].toFixed(4)}
    - Bitmap Heap Planning :: Workload=${managed_cache['effective_io_concurrency']} :: Maintenance=${managed_cache['maintenance_io_concurrency']}
    - Parallelism :: Setup=${managed_cache['parallel_setup_cost']} :: Tuple=${managed_cache['parallel_tuple_cost'].toFixed(2)}
    - Batched Commit Delay: ${managed_cache['commit_delay']} (ms)
    
* Write-Ahead Logging and Data Integrity:
    - WAL Level: ${managed_cache['wal_level']} with ${managed_cache['wal_compression']} compression algorithm
    - WAL Segment Size (1 file): ${bytesize_to_hr(_kwargs.wal_segment_size)}
    - Integrity:
        + Synchronous Commit: ${managed_cache['synchronous_commit']}
        + Full Page Writes: ${managed_cache['full_page_writes']}
        + Fsync: ${managed_cache['fsync']}
    - Buffers Write Cycle within Data Loss Time: ${options.max_time_transaction_loss_allow_in_millisecond} ms (depend on WAL volume throughput)
        + 1.0x when opt_wal_buffers=${PG_PROFILE_OPTMODE.SPIDEY}:
            -> Elapsed Time :: Rotate: ${wal10['rotate_time'].toFixed(2)} ms :: Write: ${wal10['write_time'].toFixed(2)} ms :: Delay: ${wal10['delay_time'].toFixed(2)} ms
            -> Total Time :: ${wal10['total_time'].toFixed(2)} ms during ${wal10['num_wal_files']} WAL files
            -> OK for Transaction Loss: ${wal10['total_time'] <= options.max_time_transaction_loss_allow_in_millisecond}
        + 1.5x when opt_wal_buffers=${PG_PROFILE_OPTMODE.OPTIMUS_PRIME}:
            -> Elapsed Time :: Rotate: ${wal15['rotate_time'].toFixed(2)} ms :: Write: ${wal15['write_time'].toFixed(2)} ms :: Delay: ${wal15['delay_time'].toFixed(2)} ms
            -> Total Time :: ${wal15['total_time'].toFixed(2)} ms during ${wal15['num_wal_files']} WAL files
            -> OK for Transaction Loss: ${wal15['total_time'] <= options.max_time_transaction_loss_allow_in_millisecond}
        + 2.0x when opt_wal_buffers=${PG_PROFILE_OPTMODE.PRIMORDIAL}:
            -> Elapsed Time :: Rotate: ${wal20['rotate_time'].toFixed(2)} ms :: Write: ${wal20['write_time'].toFixed(2)} ms :: Delay: ${wal20['delay_time'].toFixed(2)} ms
            -> Total Time :: ${wal20['total_time'].toFixed(2)} ms during ${wal20['num_wal_files']} WAL files
            -> OK for Transaction Loss: ${wal20['total_time'] <= options.max_time_transaction_loss_allow_in_millisecond}
    - WAL Sizing:  
        + Max WAL Size for Automatic Checkpoint: ${bytesize_to_hr(managed_cache['max_wal_size'])} or ${managed_cache['max_wal_size'] / options.wal_spec.perf()[0]} seconds
        + Min WAL Size for WAL recycle instead of removal: ${bytesize_to_hr(managed_cache['min_wal_size'])}
            -> Disk usage must below ${((1 - managed_cache['min_wal_size'] / options.wal_spec.disk_usable_size) * 100).toFixed(2)} (%)
        + WAL Keep Size for PITR/Replication: ${bytesize_to_hr(managed_cache['wal_keep_size'])} or minimum ${(managed_cache['wal_keep_size'] / options.wal_spec.disk_usable_size * 100).toFixed(2)} (%)
    
* Timeout:
    - Idle-in-Transaction Session Timeout: ${managed_cache['idle_in_transaction_session_timeout']} seconds
    - Statement Timeout: ${managed_cache['statement_timeout']} seconds
    - Lock Timeout: ${managed_cache['lock_timeout']} seconds
        
WARNING (if any) and DISCLAIMER:
------------------------------------------
* These calculations could be incorrect due to capping, precision adjustment, rounding; and it is 
just the estimation. Please take proper consultant and testing to verify the actual memory usage, 
and bottleneck between processes.
* The working memory whilst the most critical part are in the assumption of **basic** full usage 
(one single HASH-based query and one CTE) and all connections are in the same state. It is best 
to test it under your **real** production business workload rather than this estimation report.
* For the autovacuum threshold, it is best to adjust it based on the actual table size, its 
active portion compared to the total size and its time, and the actual update/delete/insert 
rate to avoid bloat rather than using our above setting; but for general use, the current 
default is OK unless you are working on table with billion of rows or more.    
* Update the timeout based on your business requirement, database workload, and the 
application's behavior.
* Not every parameter can be covered or tuned, and not every parameter can be added as-is.
As mentioned, consult with your developer, DBA, and system administrator to ensure the
best performance and reliability of the database system.
# ===============================================================      
        `;

    }

    calc_worker_in_parallel(options, num_active_user_conns) {
        const managed_cache = this.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG);
        const _kwargs = options.tuning_kwargs;

        // Calculate the number of parallel workers
        const num_parallel_workers = Math.min(managed_cache['max_parallel_workers'], managed_cache['max_worker_processes']);

        // How many sessions can be in parallel
        const num_sessions = Math.floor(num_parallel_workers / managed_cache['max_parallel_workers_per_gather']);
        const remain_workers = num_parallel_workers % managed_cache['max_parallel_workers_per_gather'];
        const num_sessions_in_parallel = num_sessions + (remain_workers > 0 ? 1 : 0);

        // Ensure the number of active user connections always larger than the num_sessions
        // The maximum 0 here is meant that all connections can have full parallelism
        const num_sessions_not_in_parallel = Math.max(0, num_active_user_conns - num_sessions_in_parallel);

        return {
            'num_parallel_workers': num_parallel_workers,
            'num_sessions': num_sessions,
            'num_sessions_in_parallel': num_sessions_in_parallel,
            'num_sessions_not_in_parallel': num_sessions_not_in_parallel,
            'work_mem_parallel_scale': (num_parallel_workers + num_sessions_in_parallel + num_sessions_not_in_parallel) / num_active_user_conns
        }

    }
}



// ==================================================================================
/**
 * Original Source File: ./src/base.py
 * This file is used to perform the general tuning based on the above profile
 */

/**
 * This function is a simple wrapper to call the tuning operation and handle any exceptions that may occur.
 */

function _VarTune(request, response, group_cache, global_cache, tune_op, default_value) {
    if (tune_op !== null) {
        try {
            return [tune_op(group_cache, global_cache, request.options, response), tune_op];
        } catch (e) {
            console.error(`Error in tuning operation: ${e} --> Returning the default value.`);
        }
    }
    return [default_value, default_value];
}

function _MakeItm(key, before, after, trigger, tuneEntry, hardwareScope) {
    return new PG_TUNE_ITEM({
        key: key,
        before: before,
        after: after,
        trigger: trigger,
        hardware_scope: hardwareScope,
        comment: tuneEntry.comment || null,
        style: tuneEntry.style || null,
        partial_func: tuneEntry.partial_func || null
    });
}

function _GetFnDefault(key, tune_entry, hw_scope) {
    let msg = '';
    if (!('instructions' in tune_entry)) { // No profile-based tuning
        msg = `DEBUG: Profile-based tuning is not found for this item ${key} -> Use the general tuning instead.`;
        console.debug(msg);
        const fn = tune_entry.tune_op || null;
        const default_value = tune_entry.default;
        return [fn, default_value, msg];
    }

    // Profile-based Tuning
    const profile_fn = tune_entry.instructions[hw_scope.value] || tune_entry.tune_op || null;
    let profile_default = tune_entry.instructions[`${hw_scope.value}_default`] || null;
    if (profile_default === null) {
        profile_default = tune_entry.default;
        if (profile_fn === null || typeof profile_fn !== 'function') {
            msg = `WARNING: Profile-based tuning function collection is not found for this item ${key} and the associated hardware scope '${hw_scope}' is NOT found, pushing to use the generic default.`;
            console.warn(msg);
        }
    }
    return [profile_fn, profile_default, msg];

}

/**
 * This function is the entry point for the general tuning process. It accept
 * @param request
 * @param response
 * @param target
 * @param target_items
 * @constructor
 */

function Optimize(request, response, target, target_items) {
    const global_cache = response.outcome_cache[target];
    const dummy_fn = () => true;
    for (const [unused_1, [scope, category, unused_2]] of Object.entries(target_items)) {
        const group_cache = {};
        const group_itm = []; // A group of tuning items
        const managed_items = response.get_managed_items(target, scope);

        // Logging
        console.info(`\n====== Start the tuning process with scope: ${scope} ======`);
        for (const [mkey, tune_entry] of Object.entries(category)) {
            // Perform tuning on multi-items that share the same tuning operation
            const keys = mkey.split(MULTI_ITEMS_SPLIT);
            const key = keys[0].trim();

            // Check the profile scope of the tuning item
            const hw_scope_term = tune_entry.hardware_scope || 'overall';
            const hw_scope_value = request.options.translate_hardware_scope(hw_scope_term);

            // Get tuning function and default value
            const [fn, default_value, msg] = _GetFnDefault(key, tune_entry, hw_scope_value);
            const [result, triggering] = _VarTune(request, response, group_cache, global_cache, fn, default_value);
            const itm = _MakeItm(key, null, result || tune_entry.default, triggering, tune_entry, [hw_scope_term, hw_scope_value]);

            if (!itm || itm.after == null) {
                console.warn(`WARNING: Error in tuning the variable as default value is not found or set to null for '${key}' -> Skipping and not adding to the final result.`);
                continue;
            }

            // Perform post-condition check
            if (!tune_entry['post-condition']?.(itm.after) ?? dummy_fn(itm.after)) {
                console.error(`ERROR: Post-condition self-check of '${key}' failed on new value ${itm.after}. Skipping and not adding to the final result.`);
                continue;
            }

            // Add successful result to the cache
            group_cache[key] = itm.after;
            const post_condition_all_fn = tune_entry['post-condition-all'] || dummy_fn;
            group_itm.push([itm, post_condition_all_fn]);
            console.info(`Variable '${key}' has been tuned from ${itm.before} to ${itm.out_display()}.`);

            // Clone tuning items for the same result
            for (const k of keys.slice(1)) {
                const sub_key = k.trim();
                const cloned_itm = { ...itm, key: sub_key };
                group_cache[sub_key] = cloned_itm.after;
                group_itm.push([cloned_itm, post_condition_all_fn]);
                console.info(`Variable '${sub_key}' has been tuned from ${cloned_itm.before} to ${cloned_itm.out_display()} by copying the tuning result from '${key}'.`);
            }
        }

        // Perform global post-condition check
        for (const [itm, post_func] of group_itm) {
            if (!post_func(itm.after, global_cache, request.options)) {
                console.error(`ERROR: Post-condition total-check of '${itm.key}' failed on new value ${itm.after}. The tuning item is not added to the final result.`);
                continue;
            }

            // Add to the items
            global_cache[itm.key] = itm.after;
            managed_items[itm.key] = itm;
        }
    }
}

// ===================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/stune.py
 * This module is to perform specific tuning on the PostgreSQL database server.
 */
const _MIN_USER_CONN_FOR_ANALYTICS = 4
const _MAX_USER_CONN_FOR_ANALYTICS = 25
const _DEFAULT_WAL_SENDERS = [3, 5, 7]
const _TARGET_SCOPE = PGTUNER_SCOPE.DATABASE_CONFIG

function _trigger_tuning(keys, request, response) {
    const managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    const change_list = []
    for (const [scope, items] of Object.entries(keys)) {
        const managed_items = response.get_managed_items(_TARGET_SCOPE, scope)
        for (const key of items) {
            const t_itm = managed_items[key]
            if (t_itm && t_itm.trigger) {
                const old_result = managed_cache[key]
                t_itm.after = t_itm.trigger(managed_cache, managed_cache, request.options, response)
                managed_cache[key] = t_itm.after
                if (old_result !== t_itm.after) {
                    change_list.push([key, t_itm.out_display()])
                }
            }
        }
    }
    if (change_list.length > 0) {
        console.info(`The following items are updated: ${change_list}`)
    } else {
        console.info('No change is detected in the trigger tuning.')
    }
    return null;
}

function _item_tuning(key, after, scope, response, suffix_text) {
    const items = response.get_managed_items(_TARGET_SCOPE, scope)
    const cache = response.get_managed_cache(_TARGET_SCOPE)

    // Versioning should NOT be acknowledged here by this function
    if (!(key in items) || !(key in cache)) {
        const msg = `WARNING: The ${key} is not found in the managed tuning item list, probably the scope is invalid.`
        console.error(msg)
        throw new Error(msg)
    }

    const before = cache[key]
    console.info(`The ${key} is updated from ${before} (or ${items[key].out_display()}) to ${after} 
        (or ${items[key].out_display(override_value=after)}) ${suffix_text}.`)
    items[key].after = after
    cache[key] = after
    return null
}

// --------------------------------------------------------------------------------
function _conn_cache_query_timeout_tune(request, response) {
    console.info(`===== CPU & Statistics Tuning =====`)
    console.info(`Start tuning the connection, statistic caching, disk cache of the PostgreSQL database server based 
        on the database workload. \nImpacted Attributes: max_connections, temp_buffers, work_mem, effective_cache_size, 
        idle_in_transaction_session_timeout.`)
    const _kwargs = request.options.tuning_kwargs
    const managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    const workload_type = request.options.workload_type

    // ----------------------------------------------------------------------------------------------
    // Optimize the max_connections
    if (_kwargs.user_max_connections > 0) {
        console.info('The user has overridden the max_connections -> Skip the maximum tuning')
    } else if (workload_type === PG_WORKLOAD.OLAP) {
        console.info('The workload type is primarily managed by the application such as full-based analytics or logging/blob storage workload. ')

        // Find the PG_SCOPE.CONNECTION -> max_connections
        const max_connections = 'max_connections'
        const reserved_connections = managed_cache['reserved_connections'] + managed_cache['superuser_reserved_connections']
        const new_result = cap_value(managed_cache[max_connections] - reserved_connections,
            Math.max(_MIN_USER_CONN_FOR_ANALYTICS, reserved_connections),
            Math.max(_MAX_USER_CONN_FOR_ANALYTICS, reserved_connections))
        _item_tuning(max_connections, new_result + reserved_connections, PG_SCOPE.CONNECTION, response)
        const updates = {
            [PG_SCOPE.MEMORY]: ['temp_buffers', 'work_mem'],
            [PG_SCOPE.QUERY_TUNING]: ['effective_cache_size']
        }
        _trigger_tuning(updates, request, response);
    } else {
        console.info('The connection tuning is ignored due to applied workload type does not match expectation.')
    }

    // ----------------------------------------------------------------------------------------------
    // Tune the idle_in_transaction_session_timeout -> Reduce timeout allowance when more connection
    // GitLab: https://gitlab.com/gitlab-com/gl-infra/production/-/issues/1053
    // In this example, they tune to minimize idle-in-transaction state, but we don't know its number of connections
    // so default 5 minutes and reduce 30 seconds for every 25 connections is a great start for most workloads.
    // But you can adjust this based on the workload type independently.
    // My Comment: I don't know put it here is good or not.
    const user_connections = (managed_cache['max_connections'] - managed_cache['reserved_connections']
        - managed_cache['superuser_reserved_connections'])
    if (user_connections > _MAX_USER_CONN_FOR_ANALYTICS) {
        // This should be lowed regardless of workload to prevent the idle-in-transaction state on a lot of active connections
        const tmp_user_conn = (user_connections - _MAX_USER_CONN_FOR_ANALYTICS)
        const after_idle_in_transaction_session_timeout = managed_cache['idle_in_transaction_session_timeout'] - 30 * SECOND * (tmp_user_conn / 25)
        _item_tuning('idle_in_transaction_session_timeout', Math.max(31, after_idle_in_transaction_session_timeout), PG_SCOPE.OTHERS, response)
    }

    // ----------------------------------------------------------------------------------------------
    console.info(`Start tuning the query timeout of the PostgreSQL database server based on the database workload. 
        \nImpacted Attributes: statement_timeout, lock_timeout, cpu_tuple_cost, parallel_tuple_cost, 
        default_statistics_target, commit_delay.`)

    // Tune the cpu_tuple_cost, parallel_tuple_cost, lock_timeout, statement_timeout
    const workload_translations = {
        [PG_WORKLOAD.TSR_IOT]: [0.0075, 5 * MINUTE],
        [PG_WORKLOAD.VECTOR]: [0.025, 10 * MINUTE], // Vector-search
        [PG_WORKLOAD.OLTP]: [0.015, 10 * MINUTE],
        [PG_WORKLOAD.HTAP]: [0.025, 30 * MINUTE],
        [PG_WORKLOAD.OLAP]: [0.03, 60 * MINUTE]
    }
    const suffix_text = `by workload: ${workload_type}`
    if (workload_type in workload_translations) {
        const [new_cpu_tuple_cost, base_timeout] = workload_translations[workload_type]
        _item_tuning('cpu_tuple_cost', new_cpu_tuple_cost, PG_SCOPE.QUERY_TUNING, response, suffix_text)
        const updates = {
            [PG_SCOPE.QUERY_TUNING]: ['parallel_tuple_cost']
        }
        _trigger_tuning(updates, request, response)
        // 3 seconds was added as the reservation for query plan before taking the lock
        _item_tuning('lock_timeout', base_timeout, PG_SCOPE.OTHERS, response, suffix_text)
        _item_tuning('statement_timeout', base_timeout + 3, PG_SCOPE.OTHERS, response, suffix_text)
    }

    // Tune the default_statistics_target
    const default_statistics_target = 'default_statistics_target'
    let managed_items = response.get_managed_items(_TARGET_SCOPE, PG_SCOPE.QUERY_TUNING)
    let after_default_statistics_target = managed_cache[default_statistics_target]
    let default_statistics_target_hw_scope = managed_items[default_statistics_target].hardware_scope[1]
    if (workload_type in [PG_WORKLOAD.OLAP, PG_WORKLOAD.HTAP]) {
        after_default_statistics_target = 200
        if (default_statistics_target_hw_scope === PG_SIZING.MEDIUM) {
            after_default_statistics_target = 350
        } else if (default_statistics_target_hw_scope === PG_SIZING.LARGE) {
            after_default_statistics_target = 500
        } else if (default_statistics_target_hw_scope === PG_SIZING.MALL) {
            after_default_statistics_target = 750
        } else if (default_statistics_target_hw_scope === PG_SIZING.BIGT) {
            after_default_statistics_target = 1000
        }
    } else if (workload_type in [PG_WORKLOAD.OLTP, PG_WORKLOAD.VECTOR]) {
        if (default_statistics_target_hw_scope === PG_SIZING.LARGE) {
            after_default_statistics_target = 250
        } else if (default_statistics_target_hw_scope === PG_SIZING.MALL) {
            after_default_statistics_target = 400
        } else if (default_statistics_target_hw_scope === PG_SIZING.BIGT) {
            after_default_statistics_target = 600
        }
    }
    _item_tuning(default_statistics_target, after_default_statistics_target, PG_SCOPE.QUERY_TUNING,
        response, suffix_text)

    // ----------------------------------------------------------------------------------------------
    // Tune the commit_delay (in micro-second), and commit_siblings.
    // Don't worry about the async behaviour with as these commits are synchronous. Additional delay is added
    // synchronously with the application code is justified for batched commits.
    // The WRITE operation in WAL partition is sequential, but its read (when WAL content is not flushed to the
    // datafiles) is random IOPS. Especially during high-latency replication, unclean/unexpected shutdown, or
    // high-transaction rate, the READ operation on WAL partition is used intensively. Thus, we use the minimum
    // IOPS between the data partition and WAL partition.
    // Now we can calculate the commit_delay (* K10 to convert to millisecond)
    let after_commit_delay = managed_cache['commit_delay']
    let commit_delay_hw_scope = managed_items['commit_delay'].hardware_scope[1]
    if (workload_type in [PG_WORKLOAD.TSR_IOT]) {
        // These workloads are not critical so we can set a high commit_delay. In normal case, the constraint is
        // based on the number of commits and disk size. The server largeness may not impact here
        // The commit_siblings is tuned by sizing at general tuning phase so no actions here.
        // This is made during burst so we combine the calculation here
        const mixed_iops = Math.min(request.options.data_index_spec.perf()[1],
            PG_DISK_PERF.throughput_to_iops(request.options.wal_spec.perf()[0]))

        // This is just the rough estimation so don't fall for it.
        if (PG_DISK_SIZING.matchDiskSeries(mixed_iops, RANDOM_IOPS, 'hdd', 'weak')) {
            after_commit_delay = 3 * K10
        } else if (PG_DISK_SIZING.matchDiskSeries(mixed_iops, RANDOM_IOPS, 'hdd', 'strong')) {
            after_commit_delay = Math.floor(2.5 * K10)
        } else if (PG_DISK_SIZING.matchDiskSeries(mixed_iops, RANDOM_IOPS, 'san')) {
            after_commit_delay = 2 * K10
        } else {
            after_commit_delay = 1 * K10
        }
    } else if (workload_type in [PG_WORKLOAD.VECTOR]) {
        // Workload: VECTOR (Search, RAG, Geospatial)
        // The workload pattern of this is usually READ, the indexing is added incrementally if user make new
        // or updated resources. Since update patterns are rarely done, the commit_delay still not have much
        // impact.
        after_commit_delay = Math.floor(K10 / 10 * 2.5 * (commit_delay_hw_scope.num() + 1))
    } else if (workload_type in [PG_WORKLOAD.HTAP, PG_WORKLOAD.OLTP, PG_WORKLOAD.OLAP]) {
        // Workload: HTAP and OLTP
        // These workloads have highest and require the data integrity. Thus, the commit_delay should be set to the
        // minimum value. The higher data rate change, the burden caused on the disk is large, so we want to minimize
        // the disk impact, but hopefully we got UPS or BBU for the disk.
        // Workload: OLAP and Data Warehouse
        // These workloads are critical but not require end-user and internally managed and transformed by the
        // application side so a high commit_delay is allowed, but it does not bring large impact since commit_delay
        // affected group/batched commit of small transactions.
        after_commit_delay = K10
    }
    _item_tuning('commit_delay', after_commit_delay, PG_SCOPE.QUERY_TUNING, response, suffix_text)
    _item_tuning('commit_siblings', 5 + 3 * managed_items['commit_siblings'].hardware_scope[1].num(),
        PG_SCOPE.QUERY_TUNING, response, suffix_text)
    return null;
}

function _generic_disk_bgwriter_vacuum_wraparound_vacuum_tune(request, response) {
    console.info(`\n ===== Disk-based Tuning =====`)
    console.info(`Start tuning the disk-based I/O, background writer, and vacuuming of the PostgreSQL database 
    server based on the database workload. \nImpacted Attributes: effective_io_concurrency, bgwriter_lru_maxpages, 
    bgwriter_delay, autovacuum_vacuum_cost_limit, autovacuum_vacuum_cost_delay, autovacuum_vacuum_scale_factor, 
    autovacuum_vacuum_threshold.`)
    const managed_cache = response.get_managed_cache(_TARGET_SCOPE)

    // The WRITE operation in WAL partition is sequential, but its read (when WAL content is not flushed to the
    // datafiles) is random IOPS. Especially during high-latency replication, unclean/unexpected shutdown, or
    // high-transaction rate, the READ operation on WAL partition is used intensively. Thus, we use the minimum
    // IOPS between the data partition and WAL partition.
    const data_iops = Math.min(request.options.data_index_spec.perf()[1],
        PG_DISK_PERF.throughput_to_iops(request.options.wal_spec.perf()[0]))

    // Tune the random_page_cost by converting to disk throughput, then compute its minimum
    let after_random_page_cost = 1.01
    if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, `hdd`, `weak`)) {
        after_random_page_cost = 3.25
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, `hdd`, `strong`)) {
        after_random_page_cost = 2.60
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, `san`, `weak`)) {
        after_random_page_cost = 2.00
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, `san`, `strong`)) {
        after_random_page_cost = 1.50
    } else if (PG_DISK_SIZING.matchOneDisk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv1)) {
        after_random_page_cost = 1.25
    } else if (PG_DISK_SIZING.matchOneDisk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv2)) {
        after_random_page_cost = 1.20
    } else if (PG_DISK_SIZING.matchOneDisk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv3)) {
        after_random_page_cost = 1.15
    } else if (PG_DISK_SIZING.matchOneDisk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv4)) {
        after_random_page_cost = 1.10
    } else if (PG_DISK_SIZING.matchOneDisk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv5)) {
        after_random_page_cost = 1.05
    }
    _item_tuning('random_page_cost', after_random_page_cost, PG_SCOPE.QUERY_TUNING, response)

    // ----------------------------------------------------------------------------------------------
    // Tune the effective_io_concurrency and maintenance_io_concurrency
    let after_effective_io_concurrency = managed_cache['effective_io_concurrency']
    if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'nvmepciev5')) {
        after_effective_io_concurrency = 512
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'nvmepciev4')) {
        after_effective_io_concurrency = 384
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'nvmepciev3')) {
        after_effective_io_concurrency = 256
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'ssd', 'strong') || PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'nvmebox')) {
        after_effective_io_concurrency = 224
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'ssd', 'weak')) {
        after_effective_io_concurrency = 192
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'san', 'strong')) {
        after_effective_io_concurrency = 160
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'san', 'weak')) {
        after_effective_io_concurrency = 128
    } else if (PG_DISK_SIZING.matchOneDisk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.HDDv3)) {
        after_effective_io_concurrency = 64
    } else if (PG_DISK_SIZING.matchOneDisk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.HDDv2)) {
        after_effective_io_concurrency = 32
    }
    let after_maintenance_io_concurrency = Math.max(16, after_effective_io_concurrency / 2)
    after_effective_io_concurrency = cap_value(after_effective_io_concurrency, 16, K10)
    after_maintenance_io_concurrency = cap_value(after_maintenance_io_concurrency, 16, K10)
    _item_tuning('effective_io_concurrency', after_effective_io_concurrency, PG_SCOPE.OTHERS, response)
    _item_tuning('maintenance_io_concurrency', after_maintenance_io_concurrency, PG_SCOPE.OTHERS, response)

    // ----------------------------------------------------------------------------------------------
    // Tune the *_flush_after. For a strong disk with change applied within neighboring pages, 256 KiB and 1 MiB
    // seems a bit small.
    // Follow this: https://www.cybertec-postgresql.com/en/the-mysterious-backend_flush_after-configuration-setting/
    if (request.options.operating_system !== 'windows') {
        // This requires a Linux-based kernel to operate. See line 152 at src/include/pg_config_manual.h;
        // but weirdly, this is not required for WAL Writer

        // A double or quadruple value helps to reduce the disk performance noise during write, hoping to fill the
        // 32-64 queues on the SSD. Also, a 2x higher value (for bgwriter) meant that between two writes (write1-delay-
        // -write2), if a page is updated twice or more in the same or consecutive writes, PostgreSQL can skip those
        // pages in the `ahead` loop in IssuePendingWritebacks() in the same file (line 5954) due to the help of
        // sorting sort_pending_writebacks() at line 5917. Also if many neighbor pages get updated (usually on newly-
        // inserted data), the benefit of sequential IOPs could improve performance.

        // This effect scales to four-fold if new value is 4x larger; however, we must consider the strength of the data
        // volume and type of data; but in general, the benefits are not that large
        // How we decide to tune it? --> We based on the PostgreSQL default value and IOPS behaviour to optimize.
        // - backend_*: I don't know much about it, but it seems to control the generic so I used the minimum between
        // checkpoint and bgwriter. From the
        // - bgwriter_*: Since it only writes a small amount at random IOPS (shared_buffers with forced writeback),
        // thus having 512 KiB
        // - checkpoint_*: Since it writes a large amount of data in a time in random IOPs for most of its time
        // (flushing at 5% - 30% on average, could largely scale beyond shared_buffers and effective_cache_size in bulk
        // load, but not cause by backup/restore), thus having 256 KiB by default. But the checkpoint has its own
        // sorting to leverage partial sequential IOPS
        // - wal_writer_*: Since it writes a large amount of data in a time in sequential IOPs for most of its time,
        // thus, having 1 MiB of flushing data; but on Windows, it have a separate management
        // Another point you may consider is that having too large value could lead to a large data loss up to
        // the *_flush_after when database is powered down. But loss is maximum from wal_buffers and 3x wal_writer_delay
        // not from these setting, since under the OS crash (with synchronous_commit=ON or LOCAL, it still can allow
        // a REDO to update into data files)
        // Note that these are not related to the io_combine_limit in PostgreSQL v17 as they only vectorized the
        // READ operation only (if not believe, check three patches in release notes). At least the FlushBuffer()
        // is still work-in-place (WIP)
        // TODO: Preview patches later in version 18+
        let after_checkpoint_flush_after = managed_cache['checkpoint_flush_after']
        let after_wal_writer_flush_after = managed_cache['wal_writer_flush_after']
        let after_bgwriter_flush_after = managed_cache['bgwriter_flush_after']
        if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'san', 'strong')) {
            after_checkpoint_flush_after = 512 * Ki
            after_bgwriter_flush_after = 512 * Ki
        } else if (PG_DISK_SIZING.matchDiskSeriesInRange(data_iops, RANDOM_IOPS, 'ssd', 'nvme')) {
            after_checkpoint_flush_after = 1 * Mi
            after_bgwriter_flush_after = 1 * Mi
        }
        _item_tuning('bgwriter_flush_after', after_bgwriter_flush_after, PG_SCOPE.OTHERS, response)
        _item_tuning('checkpoint_flush_after', after_checkpoint_flush_after, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)

        let wal_tput = request.options.wal_spec.perf()[0]
        if (PG_DISK_SIZING.matchDiskSeries(wal_tput, THROUGHPUT, 'san', 'strong') ||
            PG_DISK_SIZING.matchDiskSeriesInRange(wal_tput, THROUGHPUT, 'ssd', 'nvme')) {
            after_wal_writer_flush_after = 2 * Mi
        }
        if (request.options.workload_profile >= PG_SIZING.LARGE) {
            after_wal_writer_flush_after *= 2
        }
        _item_tuning('wal_writer_flush_after', after_wal_writer_flush_after, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
        let after_backend_flush_after = Math.min(managed_cache['checkpoint_flush_after'], managed_cache['bgwriter_flush_after'])
        _item_tuning('backend_flush_after', after_backend_flush_after, PG_SCOPE.OTHERS, response)
    } else {
        // Default by Windows --> See line 152 at src/include/pg_config_manual.h;
        _item_tuning('checkpoint_flush_after', 0, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
        _item_tuning('bgwriter_flush_after', 0, PG_SCOPE.OTHERS, response)
        _item_tuning('wal_writer_flush_after', 0, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
    }

    // ----------------------------------------------------------------------------------------------
    console.info(`Start tuning the autovacuum of the PostgreSQL database server based on the database workload.`)
    console.info(`Impacted Attributes: bgwriter_lru_maxpages, bgwriter_delay.`)
    let _data_iops = request.options.data_index_spec.perf()[1]

    // Tune the bgwriter_delay (8 ms per 1K iops, starting at 300ms). At 25K IOPS, the delay is 100 ms -->
    // --> Equivalent of 3000 pages per second or 23.4 MiB/s (at 8 KiB/page)
    let after_bgwriter_delay = Math.floor(Math.max(100, managed_cache['bgwriter_delay'] - 8 * _data_iops / K10))
    _item_tuning('bgwriter_delay', after_bgwriter_delay, PG_SCOPE.OTHERS, response)

    // Tune the bgwriter_lru_maxpages. We only tune under assumption that strong disk corresponding to high
    // workload, hopefully dirty buffers can get flushed at large amount of data. We are aiming at possible
    // workload required WRITE-intensive operation during daily.
    if ((request.options.workload_type === PG_WORKLOAD.VECTOR && request.options.workload_profile >= PG_SIZING.MALL) || request.options.workload_type !== PG_WORKLOAD.VECTOR) {
        let after_bgwriter_lru_maxpages = Math.floor(managed_cache['bgwriter_lru_maxpages']) // Make a copy
        if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'ssd', 'weak')) {
            after_bgwriter_lru_maxpages += 100
        } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'ssd', 'strong')) {
            after_bgwriter_lru_maxpages += 100 + 150
        } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'nvme')) {
            after_bgwriter_lru_maxpages += 100 + 150 + 200
        }
        _item_tuning('bgwriter_lru_maxpages', after_bgwriter_lru_maxpages, PG_SCOPE.OTHERS, response)
    }

    // ----------------------------------------------------------------------------------------------
    // This docstring aims to describe how we tune the autovacuum. Basically, we run autovacuum more frequently, the ratio
    // of dirty pages compared to total is minimized (usually between 1/8 - 1/16, average at 1/12). But if the autovacuum
    // or vacuum is run rarely, the ratio becomes 1/3 or higher, and the missed page is always higher than the dirty page.
    // So the page sourced from disk usually around 65-75% (average at 70%) or higher. Since PostgreSQL 12, the MISS page
    // cost is set to 2, making the dominant cost of IO is at WRITE on DIRTY page.
    //
    // In the official PostgreSQL documentation, the autovacuum (or normal VACUUM) "normally only scans pages that have
    // been modified since the last vacuum" due to the use of visibility map. The visibility map is a bitmap that to
    // keep track of which pages contain only tuples that are known to be visible to all active transactions (and
    // all future transactions, until the page is again modified). This has two purposes. First, vacuum itself can
    // skip such pages on the next run. Second, it allows PostgreSQL to answer some queries using only the index,
    // without reference to the underlying table --> Based on this information, the VACUUM used the random IOPS
    //
    // But here is the things I found (which you can analyze from my Excel file):
    // - Frequent autovacuum has DIRTY page of 1/12 on total. DIRTY:MISS ratio is around 1/4 - 1/8
    // - The DIRTY page since PostgreSQL 12 (MISS=2 for page in RAM) becomes the dominant point of cost estimation if doing
    // less frequently
    //
    // Here is my disk benchmark with CrystalDiskMark 8.0.5 on 8 KiB NTFS page on Windows 10 at i7-8700H, 32GB RAM DDR4,
    // 1GB test file 3 runs (don't focus on the raw number, but more on ratio and disk type). I just let the number only
    // and scrubbed the disk name for you to feel the value rather than reproduce your benchmark, also the number are
    // relative (I have rounded some for simplicity):
    //
    // Disk Type: HDD 5400 RPM 1 TB (34% full)
    // -> In HDD, large page size (randomly) can bring higher throughput but the IOPS is maintained. Queue depth or
    // IO thread does not affect the story.
    // -> Here the ratio is 1:40 (synthetically) so the autovacuum seems right.
    // | Benchmark | READ (MiB/s -- IOPS) | WRITE (MiB/s -- IOPS) |
    // | --------- | -------------------- | --------------------- |
    // | Seq (1M)  | 80  -- 77            | 80 -- 75              |
    // | Rand (8K) | 1.7 -- 206           | 1.9 -- 250            |
    // | --------- | -------------------- | --------------------- |
    //
    // Disk Type: NVME PCIe v3x4 1 TB (10 % full, locally) HP FX900 PRO
    // -> In NVME, the IOPS is high but the throughput is maintained.
    // -> The ratio now is 1:2 (synthetically)
    // | Benchmark         | READ (MiB/s -- IOPS) | WRITE (MiB/s -- IOPS) |
    // | ----------------- | -------------------- | --------------------- |
    // | Seq (1M Q8T1)     | 3,380 -- 3228.5      | 3,360 -- 3205.0       |
    // | Seq (128K Q32T1)  | 3,400 -- 25983       | 3,360 -- 25671        |
    // | Rand (8K Q32T16)  | 2,000 -- 244431      | 1,700 -- 207566       |
    // | Rand (8K Q1T1)    | 97.60 -- 11914       | 218.9 -- 26717        |
    // | ----------------- | -------------------- | --------------------- |
    //
    // Our goal are well aligned with PostgreSQL ideology: "moderately-frequent standard VACUUM runs are a better
    // approach than infrequent VACUUM FULL runs for maintaining heavily-updated tables." And the autovacuum (normal
    // VACUUM) or manual vacuum (which can have ANALYZE or VACUUM FULL) can hold SHARE UPDATE EXCLUSIVE lock or
    // even ACCESS EXCLUSIVE lock when VACUUM FULL so we want to have SHARE UPDATE EXCLUSIVE lock more than ACCESS
    // EXCLUSIVE lock (see line 2041 in src/backend/commands/vacuum.c).
    //
    // Its source code can be found at
    // - Cost Determination: relation_needs_vacanalyze in src/backend/commands/autovacuum.c
    // - Action Triggering for Autovacuum: autovacuum_do_vac_analyze in src/backend/commands/autovacuum.c
    // - Vacuum Action: vacuum, vacuum_rel in src/backend/commands/vacuum.c
    // - Vacuum Delay: vacuum_delay_point in src/backend/commands/vacuum.c
    // - Table Vacuum: table_relation_vacuum in src/include/access/tableam.h --> heap_vacuum_rel in src/backend/access/heap
    // /vacuumlazy.c and in here we coud see it doing the statistic report
    console.log(`Start tuning the autovacuum of the PostgreSQL database server based on the database workload.`)
    console.log(`Impacted Attributes: autovacuum_vacuum_cost_delay, vacuum_cost_page_dirty, *_vacuum_cost_limit, 
        *_freeze_min_age, *_failsafe_age, *_table_age`)
    let _kwargs = request.options.tuning_kwargs

    // Since we are leveraging the cost-based tuning, and the *_cost_limit we have derived from the data disk IOPs, thus
    // the high value of dirty pages seems use-less and make other value difficult as based on the below thread, those
    // pages are extracted from shared_buffers (HIT) and RAM/effective_cache_size (MISS). Whilst technically, the idea
    // is to tell that dirtying the pages (DIRTY -> WRITE) is 10x dangerous. The main reason is that PostgreSQL don't
    // know about your disk hardware or capacity, so it is better to have a high cost for the dirty page. But now, we
    // acknowledge that our cost is managed under control by the data disk IOPS, we could revise the cost of dirty page
    // so as it can be running more frequently.
    //
    // On this algorithm, increase either MISS cost or DIRTY cost would allow more pages as HIT but from our perspective,
    // it is mostly useless, even the RAM is not the best as bare metal, usually at around 10 GiB/s (same as low-end
    // DDR3 or DDR2, 20x times stronger than SeqIO of SSD) (DB server are mostly virtualized or containerized),
    // but our real-world usually don't have NVME SSD for data volume due to the network bandwidth on SSD, and in the
    // database, performance can be easily improved by adding more RAM on most cases (hopefully more cache hit due to
    // RAM lacking) rather focusing on increasing the disk strength solely which is costly and not always have high
    // cost per performance improvement.
    //
    // Thereby, we want to increase the MISS cost (as compared to HIT cost) to scale our budget, and close the gap between
    // the MISS and DIRTY cost. This is the best way to improve the autovacuum performance. Meanwhile, a high cost delay
    // would allow lower budget, and let the IO controller have time to "breathe" and flush data in a timely interval,
    // without overflowing the disk queue.
    const autovacuum_vacuum_cost_delay = 'autovacuum_vacuum_cost_delay'
    const vacuum_cost_page_dirty = 'vacuum_cost_page_dirty'
    let after_vacuum_cost_page_miss = 3
    let after_autovacuum_vacuum_cost_delay = 12
    let after_vacuum_cost_page_dirty = 15

    if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'hdd', 'weak')) {
        after_autovacuum_vacuum_cost_delay = 15
        after_vacuum_cost_page_dirty = 15
    } else if (PG_DISK_SIZING.matchOneDisk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.HDDv3) || PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'san')) {
        after_autovacuum_vacuum_cost_delay = 12
        after_vacuum_cost_page_dirty = 15
    } else if (PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'ssd') || PG_DISK_SIZING.matchDiskSeries(data_iops, RANDOM_IOPS, 'nvme')) {
        after_autovacuum_vacuum_cost_delay = 5
        after_vacuum_cost_page_dirty = 10
    }
    _item_tuning('vacuum_cost_page_miss', after_vacuum_cost_page_miss, PG_SCOPE.MAINTENANCE, response)
    _item_tuning(autovacuum_vacuum_cost_delay, after_autovacuum_vacuum_cost_delay, PG_SCOPE.MAINTENANCE, response)
    _item_tuning(vacuum_cost_page_dirty, after_vacuum_cost_page_dirty, PG_SCOPE.MAINTENANCE, response)

    // Now we tune the vacuum_cost_limit. Don;t worry about this decay, it is just the estimation
    // P/s: If autovacuum frequently, the number of pages when MISS:DIRTY is around 4:1 to 6:1. If not, the ratio is
    // around 1.3:1 to 1:1.3.
    const autovacuum_max_page_per_sec = Math.floor(data_iops * _kwargs.autovacuum_utilization_ratio)
    let _delay;
    if (request.options.operating_system === 'windows') {
        // On Windows, PostgreSQL has writes its own pg_usleep emulator, in which you can track it at
        // src/backend/port/win32/signal.c and src/port/pgsleep.c. Whilst the default is on Win32 API is 15.6 ms,
        // some older hardware and old Windows kernel observed minimally 20ms or more. But since our target database is
        // PostgreSQL 13 or later, we believe that we can have better time resolution.
        // The timing here based on emulator code is 1 ms minimum or 500 us addition
        _delay = Math.max(1.0, after_autovacuum_vacuum_cost_delay + 0.5)
    } else {
        // On Linux this seems to be smaller (10 - 50 us), when it used the nanosleep() of C functions, which
        // used this interrupt of timer_slop 50 us by default (found in src/port/pgsleep.c).
        // The time resolution is 10 - 50 us on Linux (too small value could take a lot of CPU interrupts)
        // 10 us added here to prevent some CPU fluctuation could be observed in real-life
        _delay = Math.max(0.05, after_autovacuum_vacuum_cost_delay + 0.02)
    }
    _delay += 0.005  // Adding 5us for the CPU interrupt and context switch
    _delay *= 1.025  // Adding 2.5% of the delay to safely reduce the number of maximum page per cycle by 2.43%
    // _delay *= 1.05      // Adding 5% of the delay to safely reduce the number of maximum page per cycle by 4.76%
    const autovacuum_max_page_per_cycle = Math.floor(autovacuum_max_page_per_sec / K10 * _delay)

    // Since I tune for auto-vacuum, it is best to stick with MISS:DIRTY ratio is 5:5:1 (5 pages reads, 1 page writes,
    // assume with even distribution). This is the best ratio for the autovacuum. If the normal vacuum is run manually,
    // usually during idle or administrative tasks, the MISS:DIRTY ratio becomes 1.3:1 ~ 1:1.3 --> 1:1
    // For manual vacuum, the MISS:DIRTY ratio becomes 1.3:1 ~ 1:1.3 --> 1:1
    // Worst Case: The database is autovacuum without cache or cold start.
    // Worst Case: Every page requires WRITE on DISK rather than fetch on disk or OS page cache
    const miss = 12 - _kwargs.vacuum_safety_level
    const dirty = _kwargs.vacuum_safety_level
    const vacuum_cost_model = (managed_cache['vacuum_cost_page_miss'] * miss +
        managed_cache['vacuum_cost_page_dirty'] * dirty) / (miss + dirty)

    // For manual VACUUM, usually only a minor of tables gets bloated, and we assume you don't do that stupid to DDoS
    // your database to overflow your disk, but we met
    const after_vacuum_cost_limit = realign_value(
        Math.floor(autovacuum_max_page_per_cycle * vacuum_cost_model),
        after_vacuum_cost_page_dirty + after_vacuum_cost_page_miss
    )[request.options.align_index]
    _item_tuning('vacuum_cost_limit', after_vacuum_cost_limit, PG_SCOPE.MAINTENANCE, response)

    // ----------------------------------------------------------------------------------------------
    // The dependency here is related to workload (amount of transaction), disk strength (to run wrap-around), the
    // largest table size (the amount of data to be vacuumed), and especially if the user can predict correctly
    console.info(`Start tuning the autovacuum of the PostgreSQL database server based on the database workload.`)
    console.info(`Impacted Attributes: *_freeze_min_age, *_failsafe_age, *_table_age`)

    // Use-case: We extracted the TXID use-case from the GitLab PostgreSQL database, which has the TXID of 55M per day
    // or 2.3M per hour, at some point, it has 1.4K/s on weekday (5M/h) and 600/s (2M/h) on weekend.
    // Since GitLab is a substantial large use-case, we can exploit this information to tune the autovacuum. Whilst
    // its average is 1.4K/s on weekday, but with 2.3M/h, its average WRITE time is 10.9h per day, which is 45.4% of
    // of the day, seems valid compared to 8 hours of working time in human life.
    const _transaction_rate = request.options.num_write_transaction_per_hour_on_workload
    const _transaction_coef = request.options.workload_profile.num()

    // This variable is used so that even when we have a suboptimal performance, the estimation could still handle
    // in worst case scenario
    const _future_data_scaler = 2.5 + (0.5 * request.options.workload_profile.num())

    // Tuning ideology for extreme anti-wraparound vacuum: Whilst the internal algorithm can have some optimization or
    // skipping non-critical workloads, we can't completely rely on it to have a good future-proof estimation
    //
    // Based on this PR: https://git.postgresql.org/gitweb/?p=postgresql.git;a=commitdiff;h=1e55e7d17
    // At failsafe, the index vacuuming is executed only if it more than 1 index (usually the primary key holds one)
    // and PostgreSQL does not have cross-table index, thus the index vacuum and pruning is bypassed, unless it is
    // index vacuum from the current vacuum then PostgreSQL would complete that index vacuum but stop all other index
    // vacuuming (could be at the page or index level).
    // --> See function lazy_check_wraparound_failsafe in /src/backend/access/heap/vacuumlazy.c
    //
    // Generally a good-designed database would have good index with approximately 20 - 1/3 of the whole database size.
    // During the failsafe, whilst the database can still perform the WRITE operation on non too-old table, in practice,
    // it is not practical as user in normal only access several 'hottest' large table, thus maintaining its impact.
    // However, during the failsafe, cost-based vacuuming limit is removed and only SHARE UPDATE EXCLUSIVE lock is held
    // that is there to prevent DDL command (schema change, index alteration, table structure change, ...).  Also, since
    // the free-space map (1/256 of pages) and visibility map (2b/pages) could be updated, so we must take those
    // into consideration, so guessing we could have around 50-70 % of the random I/O during the failsafe.
    //
    // Unfortunately, the amount of data review could be twice as much as the normal vacuum so we should consider it into
    // our internal algorithm (as during aggressive anti-wraparound vacuum, those pages are mostly on disk, but not on
    // dirty buffers in shared_buffers region).
    const _data_tput = request.options.data_index_spec.perf()[0]
    const _wraparound_effective_io = 0.80  // Assume during aggressive anti-wraparound vacuum the effective IO is 80%
    const _data_tran_tput = PG_DISK_PERF.iops_to_throughput(_data_iops)
    const _data_avg_tput = generalized_mean(_data_tran_tput, _data_tput, 0.85)

    const _data_size = 0.75 * request.options.database_size_in_gib * Ki  // Measured in MiB
    const _index_size = 0.25 * request.options.database_size_in_gib * Ki  // Measured in MiB
    const _fsm_vm_size = Math.floor(_data_size / 256)  // + 2 * _data_size // int(DB_PAGE_SIZE * 8 // 2)

    const _failsafe_data_size = (2 * _fsm_vm_size + 2 * _data_size)
    let _failsafe_hour = (2 * _fsm_vm_size / (_data_tput * _wraparound_effective_io)) / HOUR
    _failsafe_hour += (_failsafe_data_size / (_data_tput * _wraparound_effective_io)) / HOUR
    console.log(`In the worst-case scenario (where failsafe triggered and cost-based vacuum is disabled), the amount 
        of data read and write is usually twice the data files, resulting in ${_failsafe_data_size} MiB with effective 
        throughput of ${(_wraparound_effective_io * 100).toFixed(1)}% or 
        ${(_data_tput * _wraparound_effective_io).toFixed(1)} MiB/s; Thereby having a theoretical 
        worst-case of ${_failsafe_hour.toFixed(1)} hours for failsafe vacuuming, and a safety scale factor 
        of ${_future_data_scaler.toFixed(1)} times the worst-case scenario.`)

    let _norm_hour = (2 * _fsm_vm_size / (_data_tput * _wraparound_effective_io)) / HOUR
    _norm_hour += ((_data_size + _index_size) / (_data_tput * _wraparound_effective_io)) / HOUR
    _norm_hour += ((0.35 * (_data_size + _index_size)) / (_data_avg_tput * _wraparound_effective_io)) / HOUR
    const _data_vacuum_time = Math.max(_norm_hour, _failsafe_hour)
    const _worst_data_vacuum_time = _data_vacuum_time * _future_data_scaler

    console.info(
        `WARNING: The anti-wraparound vacuuming time is estimated to be ${_data_vacuum_time.toFixed(1)} hours and scaled 
        time of ${_worst_data_vacuum_time.toFixed(1)} hours, either you should (1) upgrade the data volume to have a 
        better performance with higher IOPS and throughput, or (2) leverage pg_cron, pg_timetable, or any cron-scheduled 
        alternative to schedule manual vacuuming when age is coming to normal vacuuming threshold.`
    )

    // Our wish is to have a better estimation of how anti-wraparound vacuum works with good enough analysis, so that we
    // can either delay or fasten the VACUUM process as our wish. Since the maximum safe cutoff point from PostgreSQL is
    // 2.0B (100M less than the theory), we would like to take our value a bit less than that (1.9B), so we can have a
    // safe margin for the future.
    //
    // Our tuning direction is to do useful work with minimal IO and less disruptive as possible, either doing frequently
    // with minimal IO (and probably useless work, if not optimize), or doing high IO workload at stable rate during
    // emergency (but leaving headroom for the future).
    //
    // Tune the vacuum_failsafe_age for relfrozenid, and vacuum_multixact_failsafe_age
    // Ref: https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/413
    // Ref: https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/12630
    //
    // Whilst this seems to be a good estimation, encourage the use of strong SSD drive (I know it is costly), but we need
    // to forecast the workload scaling and data scaling. In general, the data scaling is varied across application. For
    // example in 2019, the relational database in Notion is double every 18 months, but the Stackoverflow has around
    // 2.8 TiB in 2013, so whilst the data scaling is varied, we can do a good estimation based on the current number of
    // WRITE transaction per hour, and the data scaling (plus the future scaling).
    //
    // Normal anti-wraparound is not aggressive as it still applied the cost-based vacuuming limit, but the index vacuum
    // is still OK. Our algorithm format allows you to deal with worst case (that you can deal with *current* full table
    // scan), but we can also deal with low amount of data on WRITE but extremely high concurrency such as 1M
    // attempted-WRITE transactions per hour. From Cybertec *, you could set autovacuum_freeze_max_age to 1.000.000.000,
    // making the full scans happen 5x less often. More adventurous souls may want to go even closer to the limit,
    // although the incremental gains are much smaller. If you do increase the value, monitor that autovacuum is actually
    // keeping up so you don’t end up with downtime when your transaction rate outpaces autovacuum’s ability to freeze.
    // Ref: https://www.cybertec-postgresql.com/en/autovacuum-wraparound-protection-in-postgresql/
    //
    // Maximum time of un-vacuumed table is 2B - *_min_age (by last vacuum) --> PostgreSQL introduce the *_failsafe_age
    // which is by default 80% of 2B (1.6B) to prevent the overflow of the XID. However, when overflowed at xmin or
    // xmax, only a subset of the WRITE is blocked compared to xid exhaustion which blocks all WRITE transaction.
    //
    // See Section 24.1.5.1: Multixacts and Wraparound in PostgreSQL documentation.
    // Our perspective is that we either need to set our failsafe as low as possible (ranging as 1.4B to 1.9B), for
    // xid failsafe, and a bit higher for xmin/xmax failsafe.

    const _decre_xid = generalized_mean(24 + (18 - _transaction_coef) * _transaction_coef, _worst_data_vacuum_time, 0.5)
    const _decre_mxid = generalized_mean(24 + (12 - _transaction_coef) * _transaction_coef, _worst_data_vacuum_time, 0.5)
    let xid_failsafe_age = Math.max(1_900_000_000 - _transaction_rate * _decre_xid, 1_400_000_000)
    xid_failsafe_age = realign_value(xid_failsafe_age, 500 * K10)[request.options.align_index]
    let mxid_failsafe_age = Math.max(1_900_000_000 - _transaction_rate * _decre_mxid, 1_400_000_000)
    mxid_failsafe_age = realign_value(mxid_failsafe_age, 500 * K10)[request.options.align_index]
    if ('vacuum_failsafe_age' in managed_cache) {  // Supported since PostgreSQL v14+
        _item_tuning('vacuum_failsafe_age', xid_failsafe_age, PG_SCOPE.MAINTENANCE, response)
    }
    if ('vacuum_multixact_failsafe_age' in managed_cache) {  // Supported since PostgreSQL v14+
        _item_tuning('vacuum_multixact_failsafe_age', mxid_failsafe_age, PG_SCOPE.MAINTENANCE, response)
    }

    let _decre_max_xid = Math.max(1.25 * _worst_data_vacuum_time, generalized_mean(36 + (24 - _transaction_coef) * _transaction_coef,
        1.5 * _worst_data_vacuum_time, 0.5))
    let _decre_max_mxid = Math.max(1.25 * _worst_data_vacuum_time, generalized_mean(24 + (20 - _transaction_coef) * _transaction_coef,
        1.25 *  _worst_data_vacuum_time, 0.5))

    let xid_max_age = Math.max(Math.floor(0.95 * managed_cache['autovacuum_freeze_max_age']),
        0.85 * xid_failsafe_age - _transaction_rate * _decre_max_xid)
    xid_max_age = realign_value(xid_max_age, 250 * K10)[request.options.align_index]
    let mxid_max_age = Math.max(Math.floor(0.95 * managed_cache['autovacuum_multixact_freeze_max_age']),
        0.85 * mxid_failsafe_age - _transaction_rate * _decre_max_mxid)
    mxid_max_age = realign_value(mxid_max_age, 250 * K10)[request.options.align_index]
    if (xid_max_age <= Math.floor(1.15 * managed_cache['autovacuum_freeze_max_age']) ||
        mxid_max_age <= Math.floor(1.05 * managed_cache['autovacuum_multixact_freeze_max_age'])) {
        console.warning(
            `WARNING: The autovacuum freeze max age is already at the minimum value. Please check if you can have a 
            better SSD for data volume or apply sharding or partitioned to distribute data across servers or tables.`
        )
    }
    _item_tuning('autovacuum_freeze_max_age', xid_max_age, PG_SCOPE.MAINTENANCE, response)
    _item_tuning('autovacuum_multixact_freeze_max_age', mxid_max_age, PG_SCOPE.MAINTENANCE, response)
    const updates = {
        [PG_SCOPE.MAINTENANCE]: ['vacuum_freeze_table_age', 'vacuum_multixact_freeze_table_age']
    }
    _trigger_tuning(updates, request, response, _log_pool)

    // ----------------------------------------------------------------------------------------------
    // Tune the *_freeze_min_age high enough so that it can be stable, and allowing some newer rows to remain unfrozen.
    // These rows can be frozen later when the database is stable and operating normally. One disadvantage of decreasing
    // vacuum_freeze_min_age is that it might cause VACUUM to do useless work: freezing a row version is a waste of time
    // if the row is modified soon thereafter (causing it to acquire a new XID). So the setting should be large enough
    // that rows are not frozen until they are unlikely to change anymore. We silently capped the value to be in
    // between of 20M and 1/4 of the maximum value.
    let xid_min_age = cap_value(_transaction_rate * 24, 20 * M10, managed_cache['autovacuum_freeze_max_age'] * 0.25)
    xid_min_age = realign_value(xid_min_age, 250 * K10)[request.options.align_index]
    _item_tuning('vacuum_freeze_min_age', xid_min_age, PG_SCOPE.MAINTENANCE, response)

    // For the MXID min_age, this support the row locking which is rarely met in the real-world (unless concurrent
    // analytics/warehouse workload). But usually only one instance of WRITE connection is done gracefully (except
    // concurrent Kafka stream, etc are writing during incident). Usually, unless you need the row visibility on
    // long time for transaction, this could be low (5M of xmin/xmax vs 50M of xid by default).
    // Tune the *_freeze_min_age
    let multixact_min_age = cap_value(_transaction_rate * 18, 2 * M10, managed_cache['autovacuum_multixact_freeze_max_age'] * 0.25)
    multixact_min_age = realign_value(multixact_min_age, 250 * K10)[request.options.align_index]
    _item_tuning('vacuum_multixact_freeze_min_age', multixact_min_age, PG_SCOPE.MAINTENANCE, response)
    return null;
}

// Write-Ahead Logging (WAL)
function wal_integrity_buffer_size_tune(request, response) {
    console.info(`===== Data Integrity and Write-Ahead Log Tuning =====`)
    console.info(`Start tuning the WAL of the PostgreSQL database server based on the data integrity and HA requirements.`)
    console.info(`Impacted Attributes: wal_level, max_wal_senders, max_replication_slots, wal_sender_timeout,
        log_replication_commands, synchronous_commit, full_page_writes, fsync, logical_decoding_work_mem`)
    const replication_level = request.options.max_backup_replication_tool
    const num_replicas = request.options.max_num_logical_replicas_on_primary +
        request.options.max_num_stream_replicas_on_primary
    const managed_cache = response.get_managed_cache(_TARGET_SCOPE)

    // --------------------------------------------------------------------------
    // Tune the wal_level
    const wal_level = 'wal_level'
    let after_wal_level = managed_cache[wal_level]
    if (replication_level === PG_BACKUP_TOOL.PG_LOGICAL || request.options.max_num_logical_replicas_on_primary > 0) {
        // Logical replication (highest)
        after_wal_level = 'logical'
    } else if (replication_level === PG_BACKUP_TOOL.PG_BASEBACKUP ||
        request.options.max_num_stream_replicas_on_primary > 0 || num_replicas > 0) {
        // Streaming replication (medium level)
        // The condition of num_replicas > 0 is to ensure that the user has set the replication slots
        after_wal_level = 'replica'
    } else if (replication_level in [PG_BACKUP_TOOL.PG_DUMP, PG_BACKUP_TOOL.DISK_SNAPSHOT] && num_replicas === 0) {
        after_wal_level = 'minimal'
    }
    _item_tuning(wal_level, after_wal_level, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
    // Disable since it is not used
    _item_tuning('log_replication_commands', after_wal_level !== 'minimal' ? 'on' : 'off', PG_SCOPE.LOGGING, response)

    // --------------------------------------------------------------------------
    // Tune the max_wal_senders, max_replication_slots, and wal_sender_timeout
    // We can use request.options.max_num_logical_replicas_on_primary for max_replication_slots, but the user could
    // forget to update this value so it is best to update it to be identical. Also, this value meant differently on
    // sending servers and subscriber, so it is best to keep it identical.
    // At PostgreSQL 11 or previously, the max_wal_senders is counted in max_connections
    const max_wal_senders = 'max_wal_senders'
    let reserved_wal_senders = _DEFAULT_WAL_SENDERS[0]
    if (managed_cache[wal_level] !== 'minimal') {
        if (num_replicas >= 8) {
            reserved_wal_senders = _DEFAULT_WAL_SENDERS[1]
        } else if (num_replicas >= 16) {
            reserved_wal_senders = _DEFAULT_WAL_SENDERS[2]
        }
    }
    let after_max_wal_senders = reserved_wal_senders + (managed_cache[wal_level] !== 'minimal' ? num_replicas : 0)
    _item_tuning(max_wal_senders, after_max_wal_senders, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
    _item_tuning('max_replication_slots', after_max_wal_senders, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)

    // Tune the wal_sender_timeout
    if (request.options.offshore_replication && managed_cache[wal_level] !== 'minimal') {
        const after_wal_sender_timeout = Math.max(10 * MINUTE, Math.ceil(MINUTE * (2 + (num_replicas / 4))))
        _item_tuning('wal_sender_timeout', after_wal_sender_timeout, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
    }
    // Tune the logical_decoding_work_mem
    if (managed_cache[wal_level] !== 'logical') {
        _item_tuning('logical_decoding_work_mem', 64 * Mi, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
    }

    // Tune the synchronous_commit, full_page_writes, fsync
    const _profile_optmode_level = PG_PROFILE_OPTMODE.profile_ordering()
    const synchronous_commit = 'synchronous_commit'
    if (request.options.opt_transaction_lost in _profile_optmode_level.slice(1)) {
        let after_synchronous_commit = managed_cache[synchronous_commit]
        if (managed_cache[wal_level] === 'minimal') {
            after_synchronous_commit = 'off'
            console.warn(`
                WARNING: The synchronous_commit is off -> If data integrity is less important to you than response times
                (for example, if you are running a social networking application or processing logs) you can turn this off,
                making your transaction logs asynchronous. This can result in up to wal_buffers or wal_writer_delay * 2
                (3 times on worst case) worth of data in an unexpected shutdown, but your database will not be corrupted.
                Note that you can also set this on a per-session basis, allowing you to mix “lossy” and “safe” transactions,
                which is a better approach for most applications. It is recommended to set it to local or remote_write if
                you do not prefer lossy transactions.
            `)
        } else if (num_replicas === 0) {
            after_synchronous_commit = 'local'
        } else {
            // We don't reach to 'on' here: See https://postgresqlco.nf/doc/en/param/synchronous_commit/
            after_synchronous_commit = 'remote_write'
        }
        console.warn(`
                WARNING: User allows the lost transaction during crash but with ${managed_cache[wal_level]} wal_level at
                profile ${request.options.opt_transaction_lost} but data loss could be there. Only enable this during
                testing only.
            `)
        _item_tuning(synchronous_commit, after_synchronous_commit, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
        if (request.options.opt_transaction_lost in _profile_optmode_level.slice(2)) {
            _item_tuning('full_page_writes', 'off', PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
            if (request.options.opt_transaction_lost in _profile_optmode_level.slice(3) && request.options.operating_system === 'linux') {
                _item_tuning('fsync', 'off', PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
            }
        }
    }

    // -------------------------------------------------------------------------
    console.info(`Start tuning the WAL size of the PostgreSQL database server based on the WAL disk sizing`)
    console.info(`Impacted Attributes: min_wal_size, max_wal_size, wal_keep_size, archive_timeout,
        checkpoint_timeout, checkpoint_warning`)

    const _wal_disk_size = request.options.wal_spec.disk_usable_size
    const _kwargs = request.options.tuning_kwargs
    const _scope = PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE

    // Tune the max_wal_size (This is easy to tune as it is based on the maximum WAL disk total size) to trigger
    // the CHECKPOINT process. It is usually used to handle spikes in WAL usage (when the interval between two
    // checkpoints is not met soon, and data integrity is highly preferred).
    // Ref: https://www.cybertec-postgresql.com/en/checkpoint-distance-and-amount-of-wal/
    // Two strategies:
    // 1) Tune by ratio of WAL disk size
    // 2) Tune by number of WAL files
    // Also, see the https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/11070 for the
    // tuning of max WAL size, the impact of wal_log_hints and wal_compression at
    // https://portavita.github.io/2019-06-14-blog_PostgreSQL_wal_log_hints_benchmarked/
    // https://portavita.github.io/2019-05-13-blog_about_wal_compression/
    // Whilst the benchmark is in PG9.5, it still brings some thinking into the table
    // including at large system with lower replication lag
    // https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/11070
    let after_max_wal_size = cap_value(
        Math.floor(_wal_disk_size * _kwargs.max_wal_size_ratio),
        Math.min(64 * _kwargs.wal_segment_size, 4 * Gi),
        64 * Gi
    )
    after_max_wal_size = realign_value(after_max_wal_size, 16 * _kwargs.wal_segment_size)[request.options.align_index]
    _item_tuning('max_wal_size', after_max_wal_size, _scope, response)

    // Tune the min_wal_size as these are not specifically related to the max_wal_size. This is the top limit of the
    // WAL partition so that if the disk usage beyond the threshold (disk capacity - min_wal_size), the WAL file
    // is removed. Otherwise, the WAL file is being recycled. This is to prevent the disk full issue, but allow
    // at least a small portion to handle burst large data WRITE job(s) between CHECKPOINT interval and other unusual
    // circumstances.
    let after_min_wal_size = cap_value(
        Math.floor(_wal_disk_size * _kwargs.min_wal_size_ratio),
        Math.min(32 * _kwargs.wal_segment_size, 2 * Gi),
        Math.floor(1.05 * after_max_wal_size)
    )
    after_min_wal_size = realign_value(after_min_wal_size, 8 * _kwargs.wal_segment_size)[request.options.align_index]
    _item_tuning('min_wal_size', after_min_wal_size, _scope, response)

    // 95% here to ensure you don't make mistake from your tuning guideline
    // 2x here is for SYNC phase during checkpoint, or in archive recovery or standby mode
    // See here: https://www.postgresql.org/docs/current/wal-configuration.html

    // Tune the wal_keep_size. This parameter is there to prevent the WAL file from being removed by pg_archivecleanup
    // before the replica (for DR server, not HA server or offload READ queries purpose as it used replication slots
    // by max_slot_wal_keep_size) to catch up the data during DR server downtime, network intermittent, or other issues.
    // or proper production standard, this setup required you have a proper DBA with reliable monitoring tools to keep
    // track DR server lag time.
    // Also, keeping this value too high can cause disk to be easily full and unable to run any user transaction; and
    // if you use the DR server, this is the worst indicator
    let after_wal_keep_size = cap_value(
        Math.floor(_wal_disk_size * _kwargs.wal_keep_size_ratio),
        Math.min(32 * _kwargs.wal_segment_size, 2 * Gi),
        64 * Gi
    )
    after_wal_keep_size = realign_value(after_wal_keep_size, 16 * _kwargs.wal_segment_size)[request.options.align_index]
    _item_tuning('wal_keep_size', after_wal_keep_size, _scope, response)

    // -------------------------------------------------------------------------
    // Tune the archive_timeout based on the WAL segment size. This is easy because we want to flush the WAL
    // segment to make it have better database health. We increased it when we have larger WAL segment, but decrease
    // when we have more replicas, but capping between 30 minutes and 2 hours.
    // archive_timeout: Force a switch to next WAL file after the timeout is reached. On the READ replicas
    // or during idle time, the LSN or XID don't increase so no WAL file is switched unless manually forced
    // See CheckArchiveTimeout() at line 679 of postgres/src/backend/postmaster/checkpoint.c
    // For the tuning guideline, it is recommended to have a large enough value, but not too large to
    // force the streaming replication (copying **ready** WAL files)
    // In general, this is more on the DBA and business strategies. So I think the general tuning phase is good enough
    const _wal_scale_factor = Math.floor(Math.log2(_kwargs.wal_segment_size / BASE_WAL_SEGMENT_SIZE))
    const after_archive_timeout = realign_value(
        cap_value(managed_cache['archive_timeout'] + Math.floor(MINUTE * (_wal_scale_factor * 10 - num_replicas / 2 * 5)),
                  30 * MINUTE, 2 * HOUR), Math.floor(MINUTE / 4)
    )[request.options.align_index]
    _item_tuning('archive_timeout', after_archive_timeout, _scope, response)

    // -------------------------------------------------------------------------
    console.info(`Start tuning the WAL integrity of the PostgreSQL database server based on the data integrity 
    and provided allowed time of data transaction loss.`)
    console.info(`Impacted Attributes: wal_buffers, wal_writer_delay`)

    // Apply tune the wal_writer_delay here regardless of the synchronous_commit so that we can ensure
    // no mixed of lossy and safe transactions
    const after_wal_writer_delay = Math.floor(request.options.max_time_transaction_loss_allow_in_millisecond / 3.25)
    _item_tuning('wal_writer_delay', after_wal_writer_delay, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)

    // -------------------------------------------------------------------------
    // Now we need to estimate how much time required to flush the full WAL buffers to disk (assuming we
    // have no write after the flush or wal_writer_delay is being waken up or 2x of wal_buffers are synced)
    // No low scale factor because the WAL disk is always active with one purpose only (sequential write)
    // Force enable the WAL buffers adjustment minimally to SPIDEY when the WAL disk throughput is too weak and
    // non-critical workload.
    if (request.options.opt_wal_buffers === PG_PROFILE_OPTMODE.NONE) {
        request.options.opt_wal_buffers = PG_PROFILE_OPTMODE.SPIDEY
        console.warn(`WARNING: The WAL disk throughput is enforced from NONE to SPIDEY due to important workload.`)
    }
    const wal_tput = request.options.wal_spec.perf()[0]

    // Just some useful information
    const best_wal_time = wal_time(Math.floor(managed_cache['wal_buffers']), 1.0, _kwargs.wal_segment_size, after_wal_writer_delay, wal_tput)['total_time']
    const worst_wal_time = wal_time(Math.floor(managed_cache['wal_buffers']), 2.0, _kwargs.wal_segment_size, after_wal_writer_delay, wal_tput)['total_time']
    console.info(`The WAL buffer (at full) flush time is estimated to be ${best_wal_time.toFixed(2)} ms and 
        ${worst_wal_time.toFixed(2)} ms between cycle.`)
    if (best_wal_time > after_wal_writer_delay ||
        worst_wal_time > request.options.max_time_transaction_loss_allow_in_millisecond) {
        console.warn(`WARNING: The WAL buffers flush time is greater than the wal_writer_delay or the maximum time of 
            transaction loss allowed. It is better to reduce the WAL buffers or increase your WAL file size (to optimize 
            clean throughput).`)
    }

    let data_amount_ratio_input = 1
    let transaction_loss_ratio = 2 / 3.25  // Not 2x of delay at 1 full WAL buffers
    if (request.options.opt_wal_buffers === PG_PROFILE_OPTMODE.OPTIMUS_PRIME) {
        data_amount_ratio_input = 1.5
        transaction_loss_ratio = 3 / 3.25
    } else if (request.options.opt_wal_buffers === PG_PROFILE_OPTMODE.PRIMORDIAL) {
        data_amount_ratio_input = 2
        transaction_loss_ratio = 3 / 3.25
    }

    const decay_rate = 16 * DB_PAGE_SIZE
    let current_wal_buffers = realign_value(
        managed_cache['wal_buffers'],
        Math.min(_kwargs.wal_segment_size, 64 * Mi)
    )[1]  // Bump to higher WAL buffers
    let transaction_loss_time = request.options.max_time_transaction_loss_allow_in_millisecond * transaction_loss_ratio
    while (transaction_loss_time <= wal_time(current_wal_buffers, data_amount_ratio_input, _kwargs.wal_segment_size,
                                            after_wal_writer_delay, wal_tput)['total_time']) {
        current_wal_buffers -= decay_rate
    }

    _item_tuning('wal_buffers', current_wal_buffers, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
    const wal_time_report = wal_time(current_wal_buffers, data_amount_ratio_input, _kwargs.wal_segment_size, after_wal_writer_delay, wal_tput)['msg']
    console.info(`The wal_buffers is set to ${bytesize_to_hr(current_wal_buffers)} flush time is estimated to be ${wal_time_report} ms.`)
    return null
}

// ----------------------------------------------------------------------------
// Tune the memory usage based on specific workload
function _get_wrk_mem_func() {
    let result = {
        [PG_PROFILE_OPTMODE.SPIDEY]: (options, response) => response.report(options, true, true)[1],
        [PG_PROFILE_OPTMODE.OPTIMUS_PRIME]: (options, response) => response.report(options, false, true)[1]
    }
    result[PG_PROFILE_OPTMODE.PRIMORDIAL] = (options, response) => {
        return (result[PG_PROFILE_OPTMODE.SPIDEY](options, response) + result[PG_PROFILE_OPTMODE.OPTIMUS_PRIME](options, response)) / 2
    }
    return result
}

function _get_wrk_mem(optmode, options, response) {
    return _get_wrk_mem_func()[optmode](options, response)
}

function _hash_mem_adjust(request, response) {
    // -------------------------------------------------------------------------
    // Tune the hash_mem_multiplier to use more memory when work_mem become large enough. Integrate between the
    // iterative tuning.
    const managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    const current_work_mem = managed_cache['work_mem']
    let after_hash_mem_multiplier = 2.0
    if (request.options.workload_type in [PG_WORKLOAD.HTAP, PG_WORKLOAD.OLTP, PG_WORKLOAD.VECTOR]) {
        after_hash_mem_multiplier = Math.min(2.0 + 0.125 * (current_work_mem / (40 * Mi)), 3.0)
    } else if (request.options.workload_type in [PG_WORKLOAD.OLAP]) {
        after_hash_mem_multiplier = Math.min(2.0 + 0.150 * (current_work_mem / (40 * Mi)), 3.0)
    }
    _item_tuning('hash_mem_multiplier', after_hash_mem_multiplier, PG_SCOPE.MEMORY, response,
        `by workload: ${request.options.workload_type} and working memory ${current_work_mem}`)
    return null;
}

function _wrk_mem_tune_oneshot(request, response, shared_buffers_ratio_increment, max_work_buffer_ratio_increment,
                               tuning_items) {
    // Trigger the increment / decrement
    const _kwargs = request.options.tuning_kwargs
    let sbuf_ok = false
    let wbuf_ok = false
    if (_kwargs.shared_buffers_ratio + shared_buffers_ratio_increment <= 1.0) {
        _kwargs.shared_buffers_ratio += shared_buffers_ratio_increment
        sbuf_ok = true
    }
    if (_kwargs.max_work_buffer_ratio + max_work_buffer_ratio_increment <= 1.0) {
        _kwargs.max_work_buffer_ratio += max_work_buffer_ratio_increment
        wbuf_ok = true
    }
    if (!sbuf_ok && !wbuf_ok) {
        console.warn(`WARNING: The shared_buffers and work_mem are not increased as the condition is met 
            or being unchanged, or converged -> Stop ...`)
    }
    _trigger_tuning(tuning_items, request, response)
    _hash_mem_adjust(request, response)
    return sbuf_ok, wbuf_ok
}

function _wrk_mem_tune(request, response) {
    // Tune the shared_buffers and work_mem by boost the scale factor (we don't change heuristic connection
    // as it represented their real-world workload). Similarly, with the ratio between temp_buffers and work_mem
    // Enable extra tuning to increase the memory usage if not meet the expectation.
    // Note that at this phase, we don't trigger auto-tuning from other function

    // Additional workload for specific workload
    console.info(`===== Memory Usage Tuning =====`)
    _hash_mem_adjust(request, response)
    if (request.options.opt_mem_pool === PG_PROFILE_OPTMODE.NONE ) {
        // Disable the additional memory tuning as these workload does not make benefits when increase the memory
        console.warn(`WARNING: The memory pool tuning is disabled by the user -> Skip the extra tuning.`)
        return null;
    }
    console.info(`Start tuning the memory usage based on the specific workload profile. \nImpacted attributes: 
        shared_buffers, temp_buffers, work_mem, vacuum_buffer_usage_limit, effective_cache_size`)
    const _kwargs = request.options.tuning_kwargs
    let ram = request.options.usable_ram
    let srv_mem_str = bytesize_to_hr(ram)

    let stop_point = _kwargs.max_normal_memory_usage
    let rollback_point = Math.min(stop_point + 0.0075, 1.0)  // Small epsilon to rollback
    let boost_ratio = 1 / 560  // Any small arbitrary number is OK (< 0.005), but not too small or too large
    const keys = {
        [PG_SCOPE.MEMORY]: ['shared_buffers', 'temp_buffers', 'work_mem'],
        [PG_SCOPE.QUERY_TUNING]: ['effective_cache_size',],
        [PG_SCOPE.MAINTENANCE]: ['vacuum_buffer_usage_limit',]
    }

    function _show_tuning_result(first_text) {
        console.info(first_text);
        for (const [scope, key_itm_list] of Object.entries(keys)) {
            let m_items = response.get_managed_items(_TARGET_SCOPE, scope)
            for (const key_itm of key_itm_list) {
                if (!(key_itm in m_items)) {
                    continue
                }
                console.info(`\n\t - ${m_items[key_itm].transform_keyname()}: ${m_items[key_itm].out_display()} 
                    (in postgresql.conf) or detailed: ${m_items[key_itm].after} (in bytes).`)
            }
        }
    }

    _show_tuning_result('Result (before): ')
    let _mem_check_string = Object.entries(_get_wrk_mem_func())
        .map(([scope, func]) => `${scope}=${bytesize_to_hr(func(request.options, response))}`)
        .join('; ');
    console.info(`The working memory usage based on memory profile is ${_mem_check_string} before tuning. 
        NOTICE: Expected maximum memory usage in normal condition: ${(stop_point * 100).toFixed(2)} (%) of
        ${srv_mem_str} or ${bytesize_to_hr(Math.floor(ram * stop_point))}.`)

    // Trigger the tuning
    const shared_buffers_ratio_increment = boost_ratio * 2.0 * _kwargs.mem_pool_tuning_ratio
    const max_work_buffer_ratio_increment = boost_ratio * 2.0 * (1 - _kwargs.mem_pool_tuning_ratio)

    // Use ceil to gain higher bound
    let managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    let num_conn = managed_cache['max_connections'] - managed_cache['superuser_reserved_connections'] - managed_cache['reserved_connections']
    let mem_conn = num_conn * _kwargs.single_memory_connection_overhead * _kwargs.memory_connection_to_dedicated_os_ratio / ram
    let active_connection_ratio = {
        [PG_PROFILE_OPTMODE.SPIDEY]: 1.0 / _kwargs.effective_connection_ratio,
        [PG_PROFILE_OPTMODE.OPTIMUS_PRIME]: (1.0 + _kwargs.effective_connection_ratio) / (2 * _kwargs.effective_connection_ratio),
        [PG_PROFILE_OPTMODE.PRIMORDIAL]: 1.0
    }

    let hash_mem = generalized_mean(1, managed_cache['hash_mem_multiplier'], _kwargs.hash_mem_usage_level)
    let work_mem_single = (1 - _kwargs.temp_buffers_ratio) * hash_mem
    let TBk = _kwargs.temp_buffers_ratio + work_mem_single
    if (_kwargs.mem_pool_parallel_estimate) {
        let parallel_scale_nonfull = response.calc_worker_in_parallel(
            request.options,
           Math.ceil(_kwargs.effective_connection_ratio * num_conn)
        )['work_mem_parallel_scale']
        let parallel_scale_full = response.calc_worker_in_parallel(request.options, num_conn)['work_mem_parallel_scale']
        if (request.options.opt_mem_pool === PG_PROFILE_OPTMODE.SPIDEY) {
            TBk = _kwargs.temp_buffers_ratio + work_mem_single * parallel_scale_full
        } else if (request.options.opt_mem_pool === PG_PROFILE_OPTMODE.OPTIMUS_PRIME) {
            TBk = _kwargs.temp_buffers_ratio + work_mem_single * (parallel_scale_full + parallel_scale_nonfull) / 2
        } else {
            TBk = _kwargs.temp_buffers_ratio + work_mem_single * parallel_scale_nonfull
        }
    }
    TBk *= active_connection_ratio[request.options.opt_mem_pool]

    // Interpret as below:
    const A = _kwargs.shared_buffers_ratio * ram  // The original shared_buffers value
    const B = shared_buffers_ratio_increment * ram  // The increment of shared_buffers
    const C = max_work_buffer_ratio_increment  // The increment of max_work_buffer_ratio
    const D = _kwargs.max_work_buffer_ratio  // The original max_work_buffer_ratio
    const E = ram - mem_conn - A  // The current memory usage (without memory connection and original shared_buffers)
    const F = TBk  // The average working memory usage per connection
    const LIMIT = stop_point * ram - mem_conn  // The limit of memory usage without static memory usage

    // Transform as quadratic function we have:
    const a = C * F * (0 - B)
    const b = B + F * C * E - B * D * F
    const c = A + F * E * D - LIMIT
    const x = ((-b + Math.sqrt(b ** 2 - 4 * a * c)) / (2 * a))
    _wrk_mem_tune_oneshot(request, response, _log_pool, shared_buffers_ratio_increment * x,
                          max_work_buffer_ratio_increment * x, keys)
    let working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)
    _mem_check_string = Object.entries(_get_wrk_mem_func())
        .map(([scope, func]) => `${scope}=${bytesize_to_hr(func(request.options, response))}`)
        .join('; ');
    console.debug(
        `DEBUG: The working memory usage based on memory profile increased to ${bytesize_to_hr(working_memory)} 
        or ${(working_memory / ram * 100).toFixed(2)} (%) of ${srv_mem_str} after ${x.toFixed(2)} steps. This 
        results in memory usage of all profiles are ${_mem_check_string} `
    );

    // Now we trigger our one-step decay until we find the optimal point.
    let bump_step = 0
    while (working_memory < stop_point * ram) {
        _wrk_mem_tune_oneshot(request, response, _log_pool, shared_buffers_ratio_increment,
            max_work_buffer_ratio_increment, tuning_items=keys)
        working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)
        bump_step += 1
    }
    let decay_step = 0
    while (working_memory >= rollback_point * ram) {
        _wrk_mem_tune_oneshot(request, response, _log_pool, 0 - shared_buffers_ratio_increment,
            0 - max_work_buffer_ratio_increment, tuning_items = keys)
        working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)
        decay_step += 1
    }

    // Now we have the optimal point
    console.debug(`DEBUG: The optimal point is found after ${bump_step} bump steps and ${decay_step} decay steps`)
    if (bump_step + decay_step >= 3) {
        console.debug(`DEBUG: The memory pool tuning algorithm is incorrect. Revise algorithm to be more accurate`)
    }
    console.info(`The shared_buffers_ratio is now ${_kwargs.shared_buffers_ratio.toFixed(5)}.`)
    console.info(`The max_work_buffer_ratio is now ${_kwargs.max_work_buffer_ratio.toFixed(5)}.`)
    _show_tuning_result('Result (after): ')
    _mem_check_string = Object.entries(_get_wrk_mem_func())
        .map(([scope, func]) => `${scope}=${bytesize_to_hr(func(request.options, response))}`)
        .join('; ');
    console.info(`The working memory usage based on memory profile on all profiles are ${_mem_check_string}.`);

    // Checkpoint Timeout: Hard to tune as it mostly depends on the amount of data change, disk strength,
    // and expected RTO. For best practice, we must ensure that the checkpoint_timeout must be larger than
    // the time of reading 64 WAL files sequentially by 30% and writing those data randomly by 30%
    // See the method BufferSync() at line 2909 of src/backend/storage/buffer/bufmgr.c; the fsync is happened at
    // method IssuePendingWritebacks() in the same file (line 5971-5972) -> wb_context to store all the writing
    // buffers and the nr_pending linking with checkpoint_flush_after (256 KiB = 32 BLCKSZ)
    // Also, I decide to increase checkpoint time by due to this thread: https://postgrespro.com/list/thread-id/2342450
    // The minimum data amount is under normal condition of working (not initial bulk load)
    const _data_tput = request.options.data_index_spec.perf()[0]
    const _data_iops = request.options.data_index_spec.perf()[1]
    const _data_trans_tput = 0.70 * generalized_mean(PG_DISK_PERF.iops_to_throughput(_data_iops), _data_tput, -2.5)
    let _shared_buffers_ratio = 0.30    // Don't used for tuning, just an estimate of how checkpoint data writes
    if (request.options.workload_type in [PG_WORKLOAD.OLAP, PG_WORKLOAD.VECTOR]) {
        _shared_buffers_ratio = 0.15
    }

    // max_wal_size is added for automatic checkpoint as threshold
    // Technically the upper limit is at 1/2 of available RAM (since shared_buffers + effective_cache_size ~= RAM)
    let _data_amount = Math.min(
        Math.floor(managed_cache['shared_buffers'] * _shared_buffers_ratio / Mi),
        Math.floor(managed_cache['effective_cache_size'] / Ki),
        Math.floor(managed_cache['max_wal_size'] / Ki),
    )  // Measured by MiB.
    let min_ckpt_time = Math.ceil(_data_amount * 1 / _data_trans_tput)
    console.info(`The minimum checkpoint time is estimated to be ${min_ckpt_time.toFixed(1)} seconds under estimation 
        of ${_data_amount} MiB of data amount and ${_data_trans_tput.toFixed(2)} MiB/s of disk throughput.`)
    const after_checkpoint_timeout = realign_value(
        Math.max(managed_cache['checkpoint_timeout'] +
            Math.floor(Math.floor(Math.log2(_kwargs.wal_segment_size / BASE_WAL_SEGMENT_SIZE)) * 7.5 * MINUTE),
            min_ckpt_time / managed_cache['checkpoint_completion_target']), Math.floor(MINUTE / 2)
    )[request.options.align_index]
    _item_tuning('checkpoint_timeout', after_checkpoint_timeout, PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)
    _item_tuning('checkpoint_warning', Math.floor(after_checkpoint_timeout / 10), PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response)

    return null;
}

function _logger_tune(request, response) {
    console.info('===== Logging and Query Statistics Tuning =====')
    console.info(`Start tuning the logging and query statistics on the PostgreSQL database server based on the 
        database workload and production guidelines. Impacted attributes: track_activity_query_size, 
        log_parameter_max_length, log_parameter_max_length_on_error, log_min_duration_statement,
        auto_explain.log_min_duration, track_counts, track_io_timing, track_wal_io_timing, `)
    const _kwargs = request.options.tuning_kwargs;

    // Configure the track_activity_query_size, log_parameter_max_length, log_parameter_max_error_length
    const log_length = realign_value(_kwargs.max_query_length_in_bytes, 64)[request.options.align_index]
    _item_tuning('track_activity_query_size', log_length, PG_SCOPE.QUERY_TUNING, response)
    _item_tuning('log_parameter_max_length', log_length, PG_SCOPE.LOGGING, response)
    _item_tuning('log_parameter_max_length_on_error', log_length, PG_SCOPE.LOGGING, response)

    // Configure the log_min_duration_statement, auto_explain.log_min_duration
    const log_min_duration = realign_value(_kwargs.max_runtime_ms_to_log_slow_query, 20)[request.options.align_index]
    _item_tuning('log_min_duration_statement', log_min_duration, PG_SCOPE.LOGGING, response)
    explain_min_duration = Math.floor(log_min_duration * _kwargs.max_runtime_ratio_to_explain_slow_query)
    explain_min_duration = realign_value(explain_min_duration, 20)[request.options.align_index]
    _item_tuning('auto_explain.log_min_duration', explain_min_duration, PG_SCOPE.EXTRA, response)

    // Tune the IO timing
    _item_tuning('track_counts', 'on', PG_SCOPE.QUERY_TUNING, response)
    _item_tuning('track_io_timing', 'on', PG_SCOPE.QUERY_TUNING, response)
    _item_tuning('track_wal_io_timing', 'on', PG_SCOPE.QUERY_TUNING, response)
    _item_tuning('auto_explain.log_timing', 'on', PG_SCOPE.EXTRA, response)
    return null;
}

function correction_tune(request, response) {
    if (!request.options.enable_database_correction_tuning) {
        console.warn('The database correction tuning is disabled by the user -> Skip the workload tuning')
        return null;
    }


    // -------------------------------------------------------------------------
    // Connection, Disk Cache, Query, and Timeout Tuning
    _conn_cache_query_timeout_tune(request, response)

    // -------------------------------------------------------------------------
    // Disk-based (Performance) Tuning
    _generic_disk_bgwriter_vacuum_wraparound_vacuum_tune(request, response)

    // -------------------------------------------------------------------------
    // Write-Ahead Logging
    _wal_integrity_buffer_size_tune(request, response)

    // Logging Tuning
    _logger_tune(request, response)

    // -------------------------------------------------------------------------
    // Working Memory Tuning
    _wrk_mem_tune(request, response)
    return null;
}










