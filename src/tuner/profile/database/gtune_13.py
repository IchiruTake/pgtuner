from src.tuner.profile.database.gtune_0 import DB0_CONFIG_PROFILE

__all__ = ['DB13_CONFIG_PROFILE']

# =============================================================================
DB13_CONFIG_MAPPING = {

}
# Don't need deepcopy here
DB13_CONFIG_PROFILE = DB0_CONFIG_PROFILE.copy() if DB13_CONFIG_MAPPING else DB0_CONFIG_PROFILE
