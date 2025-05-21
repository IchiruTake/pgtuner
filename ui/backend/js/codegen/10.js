// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/gtune_16.py
 */
// Vacuum profile
const _DB16_VACUUM_PROFILE = {
    'vacuum_buffer_usage_limit': {
        "tune_op": (group_cache, global_cache, options, response) =>
            realign_value(cap_value(Math.floor(group_cache['shared_buffers'] / 16), 2 * Mi, 16 * Gi), DB_PAGE_SIZE)[options.align_index],
        "default": 2 * Mi,
        "hardware_scope": "mem",
        "partial_func": value => `${Math.floor(value / Mi)}MB`,
    },
};
// WAL profile
const _DB16_WAL_PROFILE = {
    "wal_compression": { "default": "zstd", },
};


// Merge mapping: use tuples as arrays
const DB16_CONFIG_MAPPING = {
    maintenance: [PG_SCOPE.MAINTENANCE, _DB16_VACUUM_PROFILE, { hardware_scope: 'overall' }],
    wal: [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB16_WAL_PROFILE, { hardware_scope: 'disk' }],
};
merge_extra_info_to_profile(DB16_CONFIG_MAPPING);
type_validation(DB16_CONFIG_MAPPING);
let DB16_CONFIG_PROFILE = { ...DB15_CONFIG_PROFILE}
if (Object.keys(DB16_CONFIG_MAPPING).length > 0) {
    for (const [key, value] of Object.entries(DB16_CONFIG_MAPPING)) {
        if (key in DB16_CONFIG_PROFILE) {
            // Merge the second element of the tuple (the profile dict)
            // deepmerge(DB16_CONFIG_PROFILE[key][1], value[1], { inlineSource: true, inlineTarget: true });
            let src = DB16_CONFIG_PROFILE[key][1];
            let dst = value[1];
            for (const [k, v] of Object.entries(dst)) {
                src[k] = v;
            }
        }
    }
    rewrite_items(DB16_CONFIG_PROFILE);
}
// console.debug(`DB16_CONFIG_PROFILE`);
// show_profile(DB17_CONFIG_PROFILE);