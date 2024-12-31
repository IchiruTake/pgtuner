import logging
from copy import deepcopy
from pydantic import ByteSize
from src.tuner.profile.gtune_common_db_config import DB_CONFIG_PROFILE as DB14_CONFIG_PROFILE
from src.static.vars import APP_NAME_UPPER

__all__ = ["DB_CONFIG_PROFILE"]
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)


# =============================================================================
DB14_CONFIG_MAPPING = {

}
DB_CONFIG_PROFILE = deepcopy(DB14_CONFIG_PROFILE) if DB14_CONFIG_MAPPING else DB14_CONFIG_PROFILE