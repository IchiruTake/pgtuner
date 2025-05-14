import logging
from copy import deepcopy

from pydantic import ByteSize

from src.tuner.data.scope import PG_SCOPE
from src.tuner.profile.common import merge_extra_info_to_profile, rewrite_items, type_validation
from src.tuner.profile.database.gtune_16 import DB16_CONFIG_PROFILE
from src.utils.static import APP_NAME_UPPER, DAY, MINUTE

__all__ = ['DB17_CONFIG_PROFILE']
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
# Even the scope is the same here, but different profile would make 'post-condition-group' is not reachable to
# the other profile(s).
_DB_WAL_PROFILE = {
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

# =============================================================================
# Trigger the merge
DB17_CONFIG_MAPPING = {
    'wal': (PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_WAL_PROFILE, {'hardware_scope': 'overall'}),
    'timeout': (PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, {'hardware_scope': 'overall'}),
}
merge_extra_info_to_profile(DB17_CONFIG_MAPPING)
type_validation(DB17_CONFIG_MAPPING)
DB17_CONFIG_PROFILE = deepcopy(DB16_CONFIG_PROFILE)
for k, v in DB17_CONFIG_MAPPING.items():
    if k in DB17_CONFIG_PROFILE:
        # deepmerge(DB17_CONFIG_PROFILE[k][1], v[1], inline_source=True, inline_target=True)
        src_conf = DB17_CONFIG_PROFILE[k][1]
        dst_conf = v[1]
        for k0, v0 in dst_conf.items():
            src_conf[k0] = v0
rewrite_items(DB17_CONFIG_PROFILE)
