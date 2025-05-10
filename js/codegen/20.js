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
        comment: tuneEntry.hasOwnProperty('comment') ? tuneEntry['comment'] : null,
        style: tuneEntry.hasOwnProperty('style') ? tuneEntry['style'] : null,
        partial_func: tuneEntry.hasOwnProperty('partial_func') ? tuneEntry['partial_func'] : null
    });
}

function _GetFnDefault(key, tune_entry, hw_scope) {
    let msg = '';
    console.log(tune_entry);
    if (!(tune_entry.hasOwnProperty('instructions'))) { // No profile-based tuning
        msg = `DEBUG: Profile-based tuning is not found for this item ${key} -> Use the general tuning instead.`;
        console.debug(msg);
        const fn = tune_entry.hasOwnProperty('tune_op') ? tune_entry['tune_op'] : null;
        const default_value = tune_entry['default'];
        return [fn, default_value, msg];
    }

    // Profile-based Tuning
    let profile_fn = null;
    if (tune_entry['instructions'].hasOwnProperty(`${hw_scope.value}`)) {
        profile_fn = tune_entry['instructions'][`${hw_scope.value}`];
    } else if (tune_entry.hasOwnProperty('tune_op')) {
        profile_fn = tune_entry['tune_op'];
    }
    let profile_default = null;
    if (tune_entry['instructions'].hasOwnProperty(`${hw_scope.value}_default`)) {
        profile_default = tune_entry['instructions'][`${hw_scope.value}_default`];
    }
    if (profile_default === null) {
        profile_default = tune_entry['default'];
        if (profile_fn === null || typeof profile_fn !== 'function') {
            msg = `WARNING: Profile-based tuning function collection is not found for this item ${key} and the associated hardware scope '${hw_scope.value}' is NOT found, pushing to use the generic default.`;
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
            const hw_scope_term = tune_entry.hasOwnProperty('hardware_scope') ? tune_entry['hardware_scope'] : 'overall';
            const hw_scope_value = request.options.translate_hardware_scope(hw_scope_term);

            // Get tuning function and default value
            const [fn, default_value, msg] = _GetFnDefault(key, tune_entry, hw_scope_value);
            const [result, triggering] = _VarTune(request, response, group_cache, global_cache, fn, default_value);
            const itm = _MakeItm(key, null, result !== null ? result : tune_entry['default'], triggering, tune_entry, [hw_scope_term, hw_scope_value]);
            console.log(fn, default_value, result, triggering);
            if (itm === null || itm.after === null) {
                console.warn(`WARNING: Error in tuning the variable as default value is not found or set to null for '${key}' -> Skipping and not adding to the final result.`);
                continue;
            }
            console.log(itm);

            // Perform post-condition check
            if (tune_entry.hasOwnProperty('post-condition') && typeof tune_entry['post-condition'] === 'function') {
                if (tune_entry['post-condition'](itm.after) === false) {
                    console.error(`ERROR: Post-condition self-check of '${key}' failed on new value ${itm.after}. Skipping and not adding to the final result.`);
                    continue;
                }
            }

            if (tune_entry.hasOwnProperty('post-condition-group') && typeof tune_entry['post-condition-group'] === 'function') {
                if (tune_entry['post-condition-group'](itm.after, group_cache, request.options) === false) {
                    console.error(`ERROR: Post-condition group-check of '${key}' failed on new value ${itm.after}. Skipping and not adding to the final result.`);
                    continue;
                }
            }

            // Add successful result to the cache
            group_cache[key] = itm.after;
            const post_condition_all_fn = tune_entry.hasOwnProperty('post-condition-all') ? tune_entry['post-condition-all'] : null;
            group_itm.push([itm, post_condition_all_fn]);
            console.info(`Variable '${key}' has been tuned from ${itm.before} to ${itm.out_display()}.`);

            // Clone tuning items for the same result
            for (const k of keys.slice(1)) {
                const sub_key = k.trim();
                const cloned_itm = _MakeItm(sub_key, null, result || tune_entry.default, triggering, tune_entry, [hw_scope_term, hw_scope_value]);
                group_cache[sub_key] = cloned_itm.after;
                group_itm.push([cloned_itm, post_condition_all_fn]);
                console.info(`Variable '${sub_key}' has been tuned from ${cloned_itm.before} to ${cloned_itm.out_display()} by copying the tuning result from '${key}'.`);
            }
        }

        // Perform global post-condition check
        for (const [itm, post_func] of group_itm) {
            if (post_func !== null && !post_func(itm.after, group_cache, request.options)) {
                console.error(`ERROR: Post-condition total-check of '${itm.key}' failed on new value ${itm.after}. The tuning item is not added to the final result.`);
                continue;
            }

            // Add to the items
            global_cache[itm.key] = itm.after;
            managed_items[itm.key] = itm;
        }
    }
}
