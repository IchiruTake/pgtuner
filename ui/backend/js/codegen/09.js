// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_15.py
 */

// Log profile
const _DB15_LOG_PROFILE = {
    "log_startup_progress_interval": { "default": K10, "partial_func": value => `${value}s`, },
};

// Merge mapping: use tuples as arrays
const DB15_CONFIG_MAPPING = {
    log: [PG_SCOPE.LOGGING, _DB15_LOG_PROFILE, { hardware_scope: 'disk' }],
};

merge_extra_info_to_profile(DB15_CONFIG_MAPPING);
type_validation(DB15_CONFIG_MAPPING);
// Pseudo Deep Copy
const DB15_CONFIG_PROFILE = { };
for (const [key, value] of Object.entries(DB14_CONFIG_PROFILE)) {
    DB15_CONFIG_PROFILE[key] = [value[0], { ...value[1] }, value[2]];
}
if (Object.keys(DB15_CONFIG_MAPPING).length > 0) {
    for (const [key, value] of Object.entries(DB15_CONFIG_MAPPING)) {
        if (key in DB15_CONFIG_PROFILE) {
            // Merge the second element of the tuple (the profile dict)
            // deepmerge(DB15_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
            let src = DB15_CONFIG_PROFILE[key][1];
            let dst = value[1];
            for (const [k, v] of Object.entries(dst)) {
                src[k] = v;
            }
        }
    }
    rewrite_items(DB15_CONFIG_PROFILE);
}
// console.debug(`DB15_CONFIG_PROFILE`);
// show_profile(DB15_CONFIG_PROFILE);