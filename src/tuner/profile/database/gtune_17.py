import logging
from copy import deepcopy

from pydantic import ByteSize

from src.static.vars import K10, Mi, Gi, APP_NAME_UPPER, DB_PAGE_SIZE, DAY, MINUTE
from src.tuner.data.scope import PG_SCOPE
from src.tuner.profile.common import merge_extra_info_to_profile, rewrite_items, type_validation
from src.tuner.profile.database.gtune_0 import DB0_CONFIG_PROFILE
from src.utils.dict_deepmerge import deepmerge
from src.utils.pydantic_utils import bytesize_to_postgres_unit, realign_value_to_unit, cap_value

__all__ = ["DB17_CONFIG_PROFILE"]
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
# Even the scope is the same here, but different profile would make 'post-condition-group' is not reachable to
# the other profile(s).
_DB_LOG_PROFILE = {
    # When to Log
    'log_startup_progress_interval': {
        'default': K10,
        'comment': 'Sets the amount of time after which the startup process will log a message about a long-running '
                   'operation that is still in progress, as well as the interval between further progress messages for '
                   'that operation. The default is 1 seconds.',
    },
}

_DB_VACUUM_PROFILE = {
    'vacuum_buffer_usage_limit': {
        'tune_op': lambda group_cache, global_cache, options, response:
        realign_value_to_unit(cap_value(global_cache['shared_buffers'] // 16, 2 * Mi, 16 * Gi), DB_PAGE_SIZE)[0],
        'default': 2 * Mi,
        'hardware_scope': 'mem',
        'comment': 'Specifies the size of the Buffer Access Strategy used by the VACUUM and ANALYZE commands. A '
                   'setting of 0 will allow the operation to use any number of shared_buffers. Otherwise valid sizes '
                   'range from 128 kB to 16 GB. If the specified size would exceed 1/8 the size of shared_buffers, '
                   'the size is silently capped to that value. The default value is 2MB. Our result is based on the '
                   'memory profile which can be ranged from 1/16 to 1/64 of shared buffers',
        'partial_func': lambda value: f"{bytesize_to_postgres_unit(value, Mi)}MB",
    }
}

_DB_WAL_PROFILE = {
    'wal_compression': {
        'default': 'zstd-3',
        "comment": 'This parameter enables compression of WAL using the specified compression method. When enabled, '
                   'the PostgreSQL server compresses full page images written to WAL when full_page_writes is on or '
                   'during a base backup. A compressed page image will be decompressed during WAL replay.'
    },
    'summarize_wal': {
        'default': 'on',
        'comment': "Enables the WAL summarizer process. Note that WAL summarization can be enabled either on a "
                   "primary or on a standby."
    },
    'wal_summary_keep_time': {
        'default': 30 * DAY // MINUTE,
        'comment': "Configures the amount of time after which the WAL summarizer automatically removes old WAL "
                   "summaries. The file timestamp is used to determine which files are old enough to remove. "
                   "Typically, you should set this comfortably higher than the time that could pass between a backup "
                   "and a later incremental backup that depends on it. WAL summaries must be available for the entire "
                   "range of WAL records between the preceding backup and the new one being taken; if not, the "
                   "incremental backup will fail. If this parameter is set to zero, WAL summaries will not be "
                   "automatically deleted, but it is safe to manually remove files that you know will not be required "
                   "for future incremental backups. Default to 10 days by official PostgreSQL documentation, and "
                   "30 days by us.",
        "partial_func": lambda value: f"{value}min"
    }
}

_DB_TIMEOUT_PROFILE = {
    # Transaction Timeout should not be moved away from default
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
    'transaction_timeout': {
        'default': 0,
        'comment': 'Terminate any session that spans longer than the specified amount of time in a transaction. The '
                   'limit applies both to explicit transactions (started with BEGIN) and to an implicitly started '
                   'transaction corresponding to a single statement. A value of zero (the default) disables the '
                   'timeout. If transaction_timeout is shorter or equal to idle_in_transaction_session_timeout or '
                   'statement_timeout then the longer timeout is ignored. Setting transaction_timeout in '
                   'postgresql.conf is not recommended because it would affect all sessions. Prepared transactions '
                   'are not subject to this timeout.',
        'partial_func': lambda value: f"{value}s",
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
DB17_CONFIG_MAPPING = {
    'log': (PG_SCOPE.LOGGING, _DB_LOG_PROFILE, {'hardware_scope': 'disk'}),
    'maintenance': (PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, {'hardware_scope': 'disk'}),
    'wal': (PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_WAL_PROFILE, {'hardware_scope': 'disk'}),
    'timeout': (PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, {'hardware_scope': 'overall'}),
    'query': (PG_SCOPE.QUERY_TUNING, _DB_QUERY_PROFILE, {'hardware_scope': 'overall'}),
}
merge_extra_info_to_profile(DB17_CONFIG_MAPPING)
type_validation(DB17_CONFIG_MAPPING)
DB17_CONFIG_PROFILE = deepcopy(DB0_CONFIG_PROFILE)
if DB17_CONFIG_MAPPING:
    for k, v in DB17_CONFIG_MAPPING.items():
        if k in DB17_CONFIG_PROFILE:
            deepmerge(DB17_CONFIG_PROFILE[k][1], v[1], inline_source=True, inline_target=True)
    rewrite_items(DB17_CONFIG_PROFILE)
