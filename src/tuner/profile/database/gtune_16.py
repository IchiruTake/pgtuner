import logging
from copy import deepcopy

from pydantic import ByteSize

from src.tuner.data.scope import PG_SCOPE
from src.tuner.profile.common import merge_extra_info_to_profile, rewrite_items, type_validation
from src.tuner.profile.database.gtune_15 import DB15_CONFIG_PROFILE
from src.utils.pydantic_utils import realign_value, cap_value
from src.utils.static import Mi, Gi, APP_NAME_UPPER, DB_PAGE_SIZE

__all__ = ['DB16_CONFIG_PROFILE']
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
_DB_VACUUM_PROFILE = {
    'vacuum_buffer_usage_limit': {
        'tune_op': lambda group_cache, global_cache, options, response:
        realign_value(cap_value(global_cache['shared_buffers'] // 16, 2 * Mi, 16 * Gi),
                      DB_PAGE_SIZE)[options.align_index],
        'default': 2 * Mi,
        'hardware_scope': 'mem',
        'comment': 'Specifies the size of the Buffer Access Strategy used by the VACUUM and ANALYZE commands. A '
                   'setting of 0 will allow the operation to use any number of shared_buffers. Otherwise valid sizes '
                   'range from 128 kB to 16 GB. If the specified size would exceed 1/8 the size of shared_buffers, '
                   'the size is silently capped to that value. The default value is 2MB. Our result is based on the '
                   'memory profile which can be ranged from 1/16 to 1/64 of shared buffers',
        'partial_func': lambda value: f"{value // Mi}MB",
    },
}

_DB_WAL_PROFILE = {
    'wal_compression': {
        'default': 'zstd',
        'comment': 'This parameter enables compression of WAL using the specified compression method. When enabled, '
                   'the PostgreSQL server compresses full page images written to WAL when full_page_writes is on or '
                   'during a base backup. A compressed page image will be decompressed during WAL replay.'
    },
}

# =============================================================================
# Trigger the merge
DB16_CONFIG_MAPPING = {
    'maintenance': (PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, {'hardware_scope': 'disk'}),
    'wal': (PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_WAL_PROFILE, {'hardware_scope': 'overall'}),
}
type_validation(DB16_CONFIG_MAPPING)
merge_extra_info_to_profile(DB16_CONFIG_MAPPING)
DB16_CONFIG_PROFILE = deepcopy(DB15_CONFIG_PROFILE)
if DB16_CONFIG_MAPPING:
    for k, v in DB16_CONFIG_MAPPING.items():
        if k in DB16_CONFIG_PROFILE:
            # deepmerge(DB16_CONFIG_PROFILE[k][1], v[1], inline_source=True, inline_target=True)
            src_conf = DB16_CONFIG_PROFILE[k][1]
            dst_conf = v[1]
            for k0, v0 in dst_conf.items():
                src_conf[k0] = v0
    rewrite_items(DB16_CONFIG_PROFILE)
