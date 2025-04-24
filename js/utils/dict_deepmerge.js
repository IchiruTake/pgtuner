/* 
This module provides a deepMerge function that deeply merges two or more objects.
It is adapted from dict_deepmerge.py.
*/

const _max_depth = 6;
const _min_num_base_item_in_layer = 12;
const _max_num_base_item_in_layer = 768;
const _max_num_conf = 100;

function _maxNumItemsInDepth(depth) {
    // return maximum allowed number of items for a given depth
    return Math.max(_min_num_base_item_in_layer, Math.floor(_max_num_base_item_in_layer / (4 ** depth)));
}

function _depthCount(a) {
    if (a && typeof a === 'object') {
        if (Array.isArray(a)) {
            return a.length ? 1 + Math.max(...a.map(_depthCount)) : 0;
        } else {
            const values = Object.values(a);
            return values.length ? 1 + Math.max(...values.map(_depthCount)) : 0;
        }
    }
    return 0;
}

function _itemTotalCount(a) {
    if (a && typeof a === 'object') {
        if (Array.isArray(a)) {
            return a.length + a.reduce((s, item) => s + _itemTotalCount(item), 0);
        } else {
            const values = Object.values(a);
            return Object.keys(a).length + values.reduce((s, item) => s + _itemTotalCount(item), 0);
        }
    }
    return 0;
}

function shallowCopy(value) {
    if (Array.isArray(value)) {
        return value.slice();
    } else if (value && typeof value === 'object') {
        return { ...value };
    }
    return value;
}

function deepCopy(value) {
    // This simple deep copy uses JSON serialization.
    // For non-JSON-safe objects, consider using a library.
    return JSON.parse(JSON.stringify(value));
}

function isImmutable(value) {
    // primitives and symbols are considered immutable
    return (value === null ||
        ['number', 'string', 'boolean', 'undefined', 'symbol'].includes(typeof value));
}

function isMutable(value) {
    return (value && typeof value === 'object');
}

function _triggerUpdate(result, key, value, trigger) {
    switch(trigger) {
        case 'override':
            result[key] = value;
            break;
        case 'bypass':
            // do nothing
            break;
        case 'terminate':
            delete result[key];
            break;
        case 'copy':
            result[key] = shallowCopy(value);
            break;
        case 'deepcopy':
            result[key] = deepCopy(value);
            break;
        case 'extend':
            if (Array.isArray(result[key]) && Array.isArray(value)) {
                result[key].push(...value);
            }
            break;
        case 'extend-copy':
            if (Array.isArray(result[key]) && Array.isArray(value)) {
                result[key].push(...shallowCopy(value));
            }
            break;
        case 'extend-deepcopy':
            if (Array.isArray(result[key]) && Array.isArray(value)) {
                result[key].push(...deepCopy(value));
            }
            break;
        default:
            // unknown trigger: do nothing
            break;
    }
}

function _deepMerge(a, b, result, path, mergedIndexItem, curDepth, maxDepth, options) {
    if (curDepth >= maxDepth) {
        throw new Error(`The depth of the object (= ${curDepth}) exceeds the maximum depth (= ${maxDepth}).`);
    }
    curDepth += 1;
    const maxNumItemsAllowed = _maxNumItemsInDepth(curDepth);
    if (Object.keys(a).length + Object.keys(b).length > 2 * maxNumItemsAllowed) {
        throw new Error(`The number of items in the object exceeds twice the maximum limit (=${maxNumItemsAllowed}).`);
    }
    
    for (const [bkey, bvalue] of Object.entries(b)) {
        path.push(bkey);

        if (!(bkey in a)) {
            if (isImmutable(bvalue)) {
                _triggerUpdate(result, bkey, bvalue, options.notAvailableImmutableAction);
            } else if (isMutable(bvalue)) {
                _triggerUpdate(result, bkey, bvalue, options.notAvailableMutableAction);
            } else if (!options.skiperror) {
                throw new TypeError(`Conflict at ${path.slice(0, curDepth).join('->')} in configuration #${mergedIndexItem}.`);
            }
        } else {
            const aValue = a[bkey];
            if (isImmutable(aValue) && isImmutable(bvalue)) {
                _triggerUpdate(result, bkey, bvalue, options.availableImmutableAction);
            } else if (isImmutable(aValue) && isMutable(bvalue)) {
                if (!options.skiperror) {
                    throw new TypeError(`Conflict at ${path.slice(0, curDepth).join('->')} in configuration #${mergedIndexItem} due to heterogeneous types.`);
                }
            } else if (isMutable(aValue) && isImmutable(bvalue)) {
                if (!options.skiperror) {
                    throw new TypeError(`Conflict at ${path.slice(0, curDepth).join('->')} in configuration #${mergedIndexItem} due to heterogeneous types.`);
                }
            } else if (isMutable(aValue) && isMutable(bvalue)) {
                const bothAreObjects = (aValue.constructor === Object && bvalue.constructor === Object);
                const bothAreArrays = Array.isArray(aValue) && Array.isArray(bvalue);
                if (bothAreObjects) {
                    _deepMerge(aValue, bvalue, result[bkey], [...path], mergedIndexItem, curDepth, maxDepth, options);
                } else if (bothAreArrays) {
                    _triggerUpdate(result, bkey, bvalue, options.listConflictAction);
                } else if (!options.skiperror) {
                    throw new TypeError(`Conflict at ${path.slice(0, curDepth).join('->')} in configuration #${mergedIndexItem} due to unsupported type combination.`);
                }
            } else if (aValue === bvalue) {
                // values are the same, do nothing
            } else if (!options.skiperror) {
                throw new Error(`Conflict at ${path.slice(0, curDepth).join('->')} in configuration #${mergedIndexItem}.`);
            }
        }
        path.pop();
    }
    return result;
}

/**
 * Recursively deep-merges two or more objects.
 *
 * @param {object} a - The base object (usually the default configuration)
 * @param  {...object} args - Additional objects whose properties will override or be merged into the base.
 * @returns {object} A new merged object.
 *
 * Options (hardcoded defaults):
 *  - inlineSource: (true) use source object directly if true, otherwise deep copy it.
 *  - inlineTarget: (false) if false, each additional object is deep-copied before merging.
 *  - maxDepth: maximum allowed depth (default = Math.floor(_max_depth/2)+1)
 *  - notAvailableImmutableAction: 'override'
 *  - availableImmutableAction: 'override'
 *  - notAvailableMutableAction: 'copy'
 *  - listConflictAction: 'copy'
 *  - skiperror: false (throws on conflict)
 */
function deepMerge(a, ...args) {
    const options = {
        inlineSource: true,
        inlineTarget: false,
        maxDepth: Math.floor(_max_depth / 2) + 1,
        notAvailableImmutableAction: 'override', // options: 'override', 'bypass', 'terminate'
        availableImmutableAction: 'override',
        notAvailableImmutableTupleAction: 'copy',  // 'copy', 'deepcopy' (not used separately in this JS version)
        availableImmutableTupleAction: 'copy',
        notAvailableMutableAction: 'copy',         // options: 'copy', 'deepcopy', 'bypass', 'terminate'
        listConflictAction: 'copy',                // options such as 'extend', 'extend-copy', 'extend-deepcopy'
        skiperror: false,
    };

    if (args.length === 0) {
        return options.inlineSource ? a : deepCopy(a);
    }
    if (options.maxDepth < 1 || options.maxDepth > _max_depth) {
        throw new Error(`The maxDepth (${options.maxDepth}) is not within allowed range (1 to ${_max_depth}).`);
    }
    if (args.length > _max_num_conf) {
        throw new Error(`The number of objects to merge exceeds the maximum limit (${_max_num_conf}).`);
    }
    const aDepth = _depthCount(a);
    if (aDepth > options.maxDepth) {
        throw new Error(`The depth of the first object (=${aDepth}) exceeds the maximum depth (=${options.maxDepth}).`);
    }
    const aItemCount = _itemTotalCount(a);
    let maxTotalItemsDefault = 0;
    for (let i = 1; i <= _max_depth; i++) {
        maxTotalItemsDefault += _maxNumItemsInDepth(i);
    }
    if (aItemCount > maxTotalItemsDefault) {
        throw new Error(`The number of items in the first object (=${aItemCount}) exceeds the maximum allowed (${maxTotalItemsDefault}).`);
    }
    let argTotalItems = 0;
    for (const arg of args) {
        const argDepth = _depthCount(arg);
        if (argDepth > options.maxDepth) {
            throw new Error(`The depth of an object (=${argDepth}) exceeds the maximum depth (=${options.maxDepth}).`);
        }
        argTotalItems += _itemTotalCount(arg);
    }
    const maxTotalItemsAddition = 32 * Math.max(args.length, _max_num_conf);
    if (argTotalItems > maxTotalItemsAddition) {
        throw new Error(`The number of items in the additional object(s) (=${argTotalItems}) exceeds the maximum allowed (${maxTotalItemsAddition}).`);
    }
    
    let result = options.inlineSource ? a : deepCopy(a);
    for (let idx = 0; idx < args.length; idx++) {
        const currArg = options.inlineTarget ? args[idx] : deepCopy(args[idx]);
        result = _deepMerge(result, currArg, result, [], idx, 0, options.maxDepth, options);
    }
    return result;
}

export { deepMerge };