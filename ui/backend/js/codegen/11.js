// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_17.py
 */
// WAL profile
const _DB17_WAL_PROFILE = {
    "summarize_wal": { "default": "on", },
    "wal_summary_keep_time": {
        "default": Math.floor(30 * DAY / MINUTE),
        "partial_func": value => `${Math.floor(value / MINUTE)}min`,
    },
};
// Timeout profile
const _DB17_TIMEOUT_PROFILE = {
    "idle_session_timeout": { "default": 0, "partial_func": value => `${value}s`, },
    "transaction_timeout": { "default": 0, "partial_func": value => `${value}s`, },
};
// AsyncIO profile
const _DB17_ASYNC_DISK_PROFILE = {
    "io_combine_limit": { "default": 128 * Ki, "partial_func": value => `${Math.floor(value / DB_PAGE_SIZE) * Math.floor(DB_PAGE_SIZE / Ki)}kB`, },
};

// Merge mapping: use tuples as arrays
const DB17_CONFIG_MAPPING = {
    timeout: [PG_SCOPE.OTHERS, _DB17_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    wal: [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB17_WAL_PROFILE, { hardware_scope: 'overall' }],
    "asynchronous_disk": [PG_SCOPE.OTHERS, _DB17_ASYNC_DISK_PROFILE, { hardware_scope: 'disk' }],
};
merge_extra_info_to_profile(DB17_CONFIG_MAPPING);
type_validation(DB17_CONFIG_MAPPING);
// Pseudo Deep Copy
const DB17_CONFIG_PROFILE = { }
for (const [key, value] of Object.entries(DB16_CONFIG_PROFILE)) {
    DB17_CONFIG_PROFILE[key] = [value[0], { ...value[1] }, value[2]];
}

if (Object.keys(DB17_CONFIG_MAPPING).length > 0) {
    for (const [key, value] of Object.entries(DB17_CONFIG_MAPPING)) {
        if (key in DB17_CONFIG_PROFILE) {
            // Merge the second element of the tuple (the profile dict)
            // deepmerge(DB17_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
            let src = DB17_CONFIG_PROFILE[key][1];
            let dst = value[1];
            for (const [k, v] of Object.entries(dst)) {
                src[k] = v;
            }
        }
    }
    rewrite_items(DB17_CONFIG_PROFILE);
}
// console.debug(`DB17_CONFIG_PROFILE: `);
// show_profile(DB17_CONFIG_PROFILE);