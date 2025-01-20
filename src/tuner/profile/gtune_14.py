import logging

from pydantic import ByteSize

from src.static.vars import APP_NAME_UPPER
from src.tuner.data.scope import PG_SCOPE
from src.tuner.profile.gtune_common import merge_extra_info_to_profile, type_validation, rewrite_items
from src.tuner.profile.gtune_common_db_config import DB_CONFIG_PROFILE as DB14_CONFIG_PROFILE
from src.utils.dict_deepmerge import deepmerge

__all__ = ['DB_CONFIG_PROFILE']
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

DB14_CONFIG_MAPPING = {
    'timeout': (PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, {'hardware_scope': 'overall'}),
    'query': (PG_SCOPE.QUERY_TUNING, _DB_QUERY_PROFILE, {'hardware_scope': 'overall'}),
}
DB_CONFIG_PROFILE = DB14_CONFIG_PROFILE.copy() if DB14_CONFIG_MAPPING else DB14_CONFIG_PROFILE

# =============================================================================
# Trigger the merge
type_validation(DB14_CONFIG_MAPPING)
merge_extra_info_to_profile(DB14_CONFIG_MAPPING)
for k, v in DB14_CONFIG_MAPPING.items():
    if k in DB_CONFIG_PROFILE:
        deepmerge(DB_CONFIG_PROFILE[k][1], v[1], inline_source=True, inline_target=True)
rewrite_items(DB_CONFIG_PROFILE)