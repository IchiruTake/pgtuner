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
            realign_value(cap_value(Math.floor(group_cache['maintenance_work_mem'] / 16), 2 * Mi, 16 * Gi), DB_PAGE_SIZE)[options.align_index],
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
// console.debug(`DB17_CONFIG_PROFILE: ${JSON.stringify(DB17_CONFIG_PROFILE, null, 2)}`);