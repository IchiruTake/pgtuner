// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_18.py
 */

// AsyncIO profile
const _DB18_ASYNC_DISK_PROFILE = {
    "io_max_combine_limit": { "default": 128 * Ki, "partial_func": value => `${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB`, },
    "io_max_concurrency": { "default": cap_value(-1, -1,1024) },
    "io_method": { "default": "io_uring", },
    "io_workers": { "default": cap_value(3, 1, 32), },
};

// Vacuum profile
const _DB18_VACUUM_PROFILE = {
    "autovacuum_vacuum_max_threshold": { "default": cap_value(100 * M10, -1, 2**31 - 1) },
    "autovacuum_worker_slots": { "default": cap_value(16, -1, 2**18 - 1) },
    "vacuum_max_eager_freeze_failure_rate": { "default": cap_value(0.03, 0.0, 1.0) },
    "vacuum_truncate": { "default": 'on' },
};

// Query profile
const _DB18_QUERY_PROFILE = {
    "track_cost_delay_timing": { "default": 'on', }
};

// Log profile
const _DB18_LOG_PROFILE = {
    "log_lock_failure": { "default": 'on', }
};

// Timeout profile
const _DB18_TIMEOUT_PROFILE = {
    "idle_replication_slot_timeout": { "default": cap_value(0, 0, 35791394) },
};

// Replication profile
const _DB18_REPLICATION_PROFILE = {
    "max_active_replication_origins": { "default": cap_value(10, 0, 2**18 - 1) },
};

// Merge mapping: use tuples as arrays
const DB18_CONFIG_MAPPING = {
    "asynchronous_disk": [PG_SCOPE.OTHERS, _DB18_ASYNC_DISK_PROFILE, { hardware_scope: 'disk' }],
    maintenance: [PG_SCOPE.MAINTENANCE, _DB18_VACUUM_PROFILE, {'hardware_scope': 'overall'}],
    query: [PG_SCOPE.QUERY_TUNING, _DB18_QUERY_PROFILE, { hardware_scope: 'overall' }],
    log: [PG_SCOPE.LOGGING, _DB18_LOG_PROFILE, { hardware_scope: 'disk' }],
    timeout: [PG_SCOPE.OTHERS, _DB18_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    replication: [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB18_REPLICATION_PROFILE, { hardware_scope: 'cpu' }],
};
merge_extra_info_to_profile(DB18_CONFIG_MAPPING);
type_validation(DB18_CONFIG_MAPPING);
// Pseudo Deep Copy
const DB18_CONFIG_PROFILE = { }
for (const [key, value] of Object.entries(DB17_CONFIG_PROFILE)) {
    DB18_CONFIG_PROFILE[key] = [value[0], { ...value[1] }, value[2]];
}
if (Object.keys(DB18_CONFIG_MAPPING).length > 0) {
    for (const [key, value] of Object.entries(DB18_CONFIG_MAPPING)) {
        if (key in DB18_CONFIG_PROFILE) {
            // Merge the second element of the tuple (the profile dict)
            // deepmerge(DB18_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
            let src = DB18_CONFIG_PROFILE[key][1];
            let dst = value[1];
            for (const [k, v] of Object.entries(dst)) {
                src[k] = v;
            }
        }
    }
    rewrite_items(DB18_CONFIG_PROFILE);
}
// console.debug(`DB18_CONFIG_PROFILE: `);
// show_profile(DB18_CONFIG_PROFILE);