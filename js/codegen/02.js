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

function checkVariableType(variable) {
    if (Array.isArray(variable)) {
        return "list";
    } else if (variable instanceof Map) {
        return "map";
    } else if (typeof variable === 'object' &&
        variable !== null &&
        variable.constructor === Object) {
        return "hashmap";
    } else {
        return "other";
    }
}


function _max_num_items_in_depth(depth = Math.floor(_max_depth / 2 + 1)) {
    return Math.max(_min_num_base_item_in_layer, Math.floor(_max_num_base_item_in_layer / (4 ** depth)));
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
