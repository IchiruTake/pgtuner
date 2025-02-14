import logging
from copy import deepcopy

from pydantic import ByteSize

from src.static.vars import K10, Mi, Gi, APP_NAME_UPPER, DB_PAGE_SIZE, Ki
from src.tuner.data.scope import PG_SCOPE
from src.tuner.profile.common import merge_extra_info_to_profile, rewrite_items, type_validation
from src.tuner.profile.database.gtune_0 import DB0_CONFIG_PROFILE
from src.utils.dict_deepmerge import deepmerge
from src.utils.pydantic_utils import realign_value, cap_value

__all__ = ['DB16_CONFIG_PROFILE']
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
_DB_LOG_PROFILE = {
    # When to Log
    'log_startup_progress_interval': {
        'default': K10,
        'comment': 'Sets the amount of time after which the startup process will log a message about a long-running '
                   'operation that is still in progress, as well as the interval between further progress messages for '
                   'that operation. The default is 1 seconds.'
    },
}

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
    'vacuum_failsafe_age': {
        'default': 1_600_000_000,
        'comment': "Age at which VACUUM should trigger failsafe to avoid a wraparound outage. Specifies the maximum "
                   "age (in transactions) that a table's pg_class.relfrozenxid field can attain before VACUUM takes "
                   "extraordinary measures to avoid system-wide transaction ID wraparound failure. This is VACUUM's "
                   "strategy of last resort. The failsafe typically triggers when an autovacuum to prevent transaction "
                   "ID wraparound has already been running for some time, though it's possible for the failsafe to "
                   "trigger during any VACUUM. When the failsafe is triggered, any cost-based delay that is in effect "
                   "will no longer be applied, further non-essential maintenance tasks (such as index vacuuming) are "
                   "bypassed, and any Buffer Access Strategy in use will be disabled resulting in VACUUM being free to "
                   "make use of all of shared buffers.",
    },
    'vacuum_multixact_failsafe_age': {
        'default': 1_600_000_000,
        'comment': "Multixact age at which VACUUM should trigger failsafe to avoid a wraparound outage. Specifies the "
                   "maximum age (in multixacts) that a table's pg_class.relminmxid field can attain before VACUUM takes "
                   "extraordinary measures to avoid system-wide multixact ID wraparound failure. This is VACUUM's "
                   "strategy of last resort. The failsafe typically triggers when an autovacuum to prevent transaction "
                   "ID wraparound has already been running for some time, though it's possible for the failsafe to "
                   "trigger during any VACUUM. When the failsafe is triggered, any cost-based delay that is in effect "
                   "will no longer be applied, and further non-essential maintenance tasks (such as index "
                   "vacuuming) are bypassed.",
    }
}

_DB_WAL_PROFILE = {
    'wal_compression': {
        'default': 'zstd',
        'comment': 'This parameter enables compression of WAL using the specified compression method. When enabled, '
                   'the PostgreSQL server compresses full page images written to WAL when full_page_writes is on or '
                   'during a base backup. A compressed page image will be decompressed during WAL replay.'
    },
}

_DB_TIMEOUT_PROFILE = {
    'idle_session_timeout': {
        'default': 0,
        'comment': 'Terminate any session that has been idle (that is, waiting for a client query), but not within an '
                   'open transaction, for longer than the specified amount of time. A value of zero (default by '
                   'official PostgreSQL documentation) disables the timeout. Unlike the case with an open transaction, '
                   'an idle session without a transaction imposes no large costs on the server, so there is less need '
                   'to enable this timeout than idle_in_transaction_session_timeout. Be wary of enforcing this timeout '
                   'on connections made through connection-pooling software or other middleware, as such a layer may '
                   'not react well to unexpected connection closure. It may be helpful to enable this timeout only for '
                   'interactive sessions, perhaps by applying it only to particular users. Default to 0 seconds '
                   '(disabled).',
        'partial_func': lambda value: f'{value}s',
    },
}

_DB_QUERY_PROFILE = {
    'track_wal_io_timing': {
        'default': 'on',
        'comment': 'Enables timing of WAL I/O calls. This parameter is off (by official PostgreSQL default, but on '
                   'in our tuning guideline), as it will repeatedly query the operating system for the current time, '
                   'which may cause significant overhead on some platforms. You can use the pg_test_timing tool to '
                   'measure the overhead of timing on your system. I/O timing is displayed in pg_stat_wal. ',
    },
}

# =============================================================================
# Trigger the merge
DB16_CONFIG_MAPPING = {
    'log': (PG_SCOPE.LOGGING, _DB_LOG_PROFILE, {'hardware_scope': 'disk'}),
    'maintenance': (PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, {'hardware_scope': 'disk'}),
    'wal': (PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_WAL_PROFILE, {'hardware_scope': 'overall'}),
    'timeout': (PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, {'hardware_scope': 'overall'}),
    'query': (PG_SCOPE.QUERY_TUNING, _DB_QUERY_PROFILE, {'hardware_scope': 'overall'}),
}
type_validation(DB16_CONFIG_MAPPING)
merge_extra_info_to_profile(DB16_CONFIG_MAPPING)
DB16_CONFIG_PROFILE = deepcopy(DB0_CONFIG_PROFILE)
if DB16_CONFIG_MAPPING:
    for k, v in DB16_CONFIG_MAPPING.items():
        if k in DB16_CONFIG_PROFILE:
            deepmerge(DB16_CONFIG_PROFILE[k][1], v[1], inline_source=True, inline_target=True)
    rewrite_items(DB16_CONFIG_PROFILE)
