import logging
from copy import deepcopy

from pydantic import ByteSize

from src.tuner.data.scope import PG_SCOPE
from src.tuner.profile.common import merge_extra_info_to_profile, type_validation, rewrite_items
from src.tuner.profile.database.gtune_13 import DB13_CONFIG_PROFILE
from src.utils.static import APP_NAME_UPPER

__all__ = ['DB14_CONFIG_PROFILE']
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
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

_DB_VACUUM_PROFILE = {
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

# =============================================================================
# Trigger the merge
DB14_CONFIG_MAPPING = {
    'timeout': (PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, {'hardware_scope': 'overall'}),
    'query': (PG_SCOPE.QUERY_TUNING, _DB_QUERY_PROFILE, {'hardware_scope': 'overall'}),
    'maintenance': (PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, {'hardware_scope': 'overall'}),
}
merge_extra_info_to_profile(DB14_CONFIG_MAPPING)
type_validation(DB14_CONFIG_MAPPING)
DB14_CONFIG_PROFILE = deepcopy(DB13_CONFIG_PROFILE)
if DB14_CONFIG_MAPPING:
    for k, v in DB14_CONFIG_MAPPING.items():
        if k in DB14_CONFIG_PROFILE:
            # deepmerge(DB14_CONFIG_PROFILE[k][1], v[1], inline_source=True, inline_target=True)
            src_conf = DB14_CONFIG_PROFILE[k][1]
            dst_conf = v[1]
            for k0, v0 in dst_conf.items():
                src_conf[k0] = v0

    rewrite_items(DB14_CONFIG_PROFILE)
