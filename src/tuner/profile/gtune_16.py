import logging
from copy import deepcopy
from pydantic import ByteSize
from src.tuner.profile.gtune_common_db_config import cap_value, realign_value_to_unit, bytesize_to_postgres_unit
from src.tuner.profile.gtune_common_db_config import DB_CONFIG_PROFILE as DB16_CONFIG_PROFILE
from src.static.vars import Ki, K10, Mi, Gi, APP_NAME_UPPER, DB_PAGE_SIZE
from src.utils.dict_deepmerge import deepmerge


__all__ = ["DB_CONFIG_PROFILE"]
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
_DB_LOG_PROFILE = {
    # When to Log
    'log_startup_progress_interval': {
        "default": K10,
        "comment": 'Sets the amount of time after which the startup process will log a message about a long-running '
                   'operation that is still in progress, as well as the interval between further progress messages for '
                   'that operation. The default is 1 seconds.'
    },
}

_DB_VACUUM_PROFILE = {
    'vacuum_buffer_usage_limit': {
        "tune_op": lambda group_cache, global_cache, request, sys_record:
        realign_value_to_unit(cap_value(global_cache['shared_buffers'] // 12, 2 * Mi, 16 * Gi), DB_PAGE_SIZE)[0],
        "default": 2 * Mi,
        "comment": 'Specifies the size of the Buffer Access Strategy used by the VACUUM and ANALYZE commands. A '
                   'setting of 0 will allow the operation to use any number of shared_buffers. Otherwise valid sizes '
                   'range from 128 kB to 16 GB. If the specified size would exceed 1/8 the size of shared_buffers, '
                   'the size is silently capped to that value. The default value is 2 MiB.',
        "partial_func": lambda value: f"{bytesize_to_postgres_unit(value, Mi)}MB",
    }
}

_DB_WAL_PROFILE = {
    'wal_compression': {
        "default": 'zstd-3',
        "comment": 'This parameter enables compression of WAL using the specified compression method. When enabled, '
                   'the PostgreSQL server compresses full page images written to WAL when full_page_writes is on or '
                   'during a base backup. A compressed page image will be decompressed during WAL replay.'
    },
}

DB16_CONFIG_MAPPING = {
    'log': _DB_LOG_PROFILE,
    'maintenance': _DB_VACUUM_PROFILE,
    'wal': _DB_WAL_PROFILE,
}
DB_CONFIG_PROFILE = deepcopy(DB16_CONFIG_PROFILE) if DB16_CONFIG_MAPPING else DB16_CONFIG_PROFILE

# =============================================================================
# Trigger the merge
for k, v in DB16_CONFIG_MAPPING.items():
    if k in DB_CONFIG_PROFILE:
        deepmerge(DB_CONFIG_PROFILE[k][1], v, inline_source=True, inline_target=True)