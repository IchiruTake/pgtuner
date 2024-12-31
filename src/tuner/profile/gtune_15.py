import logging
from copy import deepcopy

from pydantic import ByteSize

from src.tuner.profile.gtune_common_db_config import DB_CONFIG_PROFILE as DB15_CONFIG_PROFILE
from src.static.vars import K10, APP_NAME_UPPER
from src.utils.dict_deepmerge import deepmerge


__all__ = ["DB_CONFIG_PROFILE"]
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
        "partial_func": lambda value: f"{value // K10}s"
    },
}

DB15_CONFIG_MAPPING = {
    'log': _DB_LOG_PROFILE
}
DB_CONFIG_PROFILE = deepcopy(DB15_CONFIG_PROFILE) if DB15_CONFIG_MAPPING else DB15_CONFIG_PROFILE

# =============================================================================
# Trigger the merge
for k, v in DB15_CONFIG_MAPPING.items():
    if k in DB_CONFIG_PROFILE:
        deepmerge(DB_CONFIG_PROFILE[k][1], v, inline_source=True, inline_target=True)