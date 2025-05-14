import logging
from copy import deepcopy

from pydantic import ByteSize

from src.tuner.data.scope import PG_SCOPE
from src.tuner.profile.common import merge_extra_info_to_profile, type_validation, rewrite_items
from src.tuner.profile.database.gtune_14 import DB14_CONFIG_PROFILE
from src.utils.static import K10, APP_NAME_UPPER

__all__ = ["DB15_CONFIG_PROFILE"]
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
# Even the scope is the same here, but different profile would make 'post-condition-group' is not reachable to
# the other profile(s).
_DB_LOG_PROFILE = {
    # When to Log
    'log_startup_progress_interval': {
        "default": K10,
        "comment": 'Sets the amount of time after which the startup process will log a message about a long-running '
                   'operation that is still in progress, as well as the interval between further progress messages for '
                   'that operation. The default is 1 seconds.',
        'partial_func': lambda value: f"{value // K10}s"
    },
}

# =============================================================================
# Trigger the merge
DB15_CONFIG_MAPPING = {
    'log': (PG_SCOPE.LOGGING, _DB_LOG_PROFILE, {'hardware_scope': 'disk'}),
}
merge_extra_info_to_profile(DB15_CONFIG_MAPPING)
type_validation(DB15_CONFIG_MAPPING)
DB15_CONFIG_PROFILE = deepcopy(DB14_CONFIG_PROFILE)
if DB15_CONFIG_MAPPING:
    for k, v in DB15_CONFIG_MAPPING.items():
        if k in DB15_CONFIG_PROFILE:
            # deepmerge(DB15_CONFIG_PROFILE[k][1], v[1], inline_source=True, inline_target=True)
            src_conf = DB15_CONFIG_PROFILE[k][1]
            dst_conf = v[1]
            for k0, v0 in dst_conf.items():
                src_conf[k0] = v0
    rewrite_items(DB15_CONFIG_PROFILE)
