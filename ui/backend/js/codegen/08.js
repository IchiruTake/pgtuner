// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_14.py
 */

// Timeout profile
const _DB14_TIMEOUT_PROFILE = {
    'idle_session_timeout': { "default": 0, "partial_func": value => `${value}s`, },
};
// Query profile
const _DB14_QUERY_PROFILE = {
    'track_wal_io_timing': { "default": 'on', },
};
// Vacuum profile
const _DB14_VACUUM_PROFILE = {
    'vacuum_failsafe_age': { "default": 1600000000, },
    'vacuum_multixact_failsafe_age': { "default": 1600000000, }
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
            // deepmerge(DB14_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
            let src = DB14_CONFIG_PROFILE[key][1];
            let dst = value[1];
            for (const [k, v] of Object.entries(dst)) {
                src[k] = v;
            }
        }
    }
    rewrite_items(DB14_CONFIG_PROFILE);
}
// console.debug(`DB14_CONFIG_PROFILE`);
// show_profile(DB14_CONFIG_PROFILE);