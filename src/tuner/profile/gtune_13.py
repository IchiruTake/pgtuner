import logging

from pydantic import ByteSize

from src.static.vars import APP_NAME_UPPER
from src.tuner.profile.gtune_common_db_config import DB_CONFIG_PROFILE as DB13_CONFIG_PROFILE

__all__ = ["DB_CONFIG_PROFILE"]
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
DB13_CONFIG_MAPPING = {

}
DB_CONFIG_PROFILE = DB13_CONFIG_PROFILE.copy() if DB13_CONFIG_MAPPING else DB13_CONFIG_PROFILE
