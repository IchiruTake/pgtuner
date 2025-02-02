import logging

from pydantic import ByteSize

from src.static.vars import APP_NAME_UPPER
from src.tuner.profile.database.gtune_0 import DB0_CONFIG_PROFILE

__all__ = ['DB13_CONFIG_PROFILE']
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
DB13_CONFIG_MAPPING = {

}
DB13_CONFIG_PROFILE = DB0_CONFIG_PROFILE.copy() if DB13_CONFIG_MAPPING else DB0_CONFIG_PROFILE
