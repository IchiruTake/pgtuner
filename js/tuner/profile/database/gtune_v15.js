import { deepMerge } from '../../../utils/dictDeepMerge.js';
import { PG_SCOPE } from '../../data/scope.js';
import { merge_extra_info_to_profile, rewrite_items, type_validation } from '../common.js';
import { DB0_CONFIG_PROFILE } from './gtune_0.js';

// -------------------------------------------------------------------
// Log profile
const _DB_LOG_PROFILE = {
    "log_startup_progress_interval": {
        "default": K10,
        "partial_func": value => `${value}s`,
    },
};


// -------------------------------------------------------------------
// Timeout profile
const _DB_TIMEOUT_PROFILE = {
    "idle_session_timeout": {
        "default": 0,
        "partial_func": value => `${value}s`,
    },
};

// -------------------------------------------------------------------
// Query profile
const _DB_QUERY_PROFILE = {
    "track_wal_io_timing": {
        "default": 'on',
    },
};

// -------------------------------------------------------------------
// Vacuum profile
const _DB_VACUUM_PROFILE = {
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
    log: [PG_SCOPE.LOGGING, _DB_LOG_PROFILE, { hardware_scope: 'disk' }],
    timeout: [PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    query: [PG_SCOPE.QUERY_TUNING, _DB_QUERY_PROFILE, { hardware_scope: 'overall' }],
    maintenance: [PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, { hardware_scope: 'overall' }],
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
            deepMerge(DB15_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
        }
    }
    rewrite_items(DB15_CONFIG_PROFILE);
}
console.debug(`DB15_CONFIG_PROFILE: ${JSON.stringify(DB15_CONFIG_PROFILE)}`);
export { DB15_CONFIG_PROFILE };
