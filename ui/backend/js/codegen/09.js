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
    'idle_session_timeout': { "default": 0, "partial_func": value => `${value}s`, },
};
// Query profile
const _DB15_QUERY_PROFILE = {
    'track_wal_io_timing': { 'default': 'on', },
};
// Vacuum profile
const _DB15_VACUUM_PROFILE = {
    'vacuum_failsafe_age': { 'default': 1600000000, },
    'vacuum_multixact_failsafe_age': { 'default': 1600000000, }
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