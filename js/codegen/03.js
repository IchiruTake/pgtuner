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