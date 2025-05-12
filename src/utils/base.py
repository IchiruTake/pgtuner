import gc
import logging
import os
from typing import Any

from src.utils.static import APP_NAME_UPPER

__all__ = ['OsGetEnvBool', 'OptimGC', 'TranslateNone']
_logger = logging.getLogger(APP_NAME_UPPER)

# ==================================================================================================
_max_depth: int = 6  # Change this to make it traverse deeper or shallower


def _TranslateNone(cfg: dict[str, Any] | list[Any], c_depth: int) -> None:
    """
    This function translates the string "None" into python NoneType object in the dictionary (which happens
    during the JSON/YAML/TOML data serialization). The depth is used to prevent the infinite loop when the
    dictionary is too deep, set as constant value in this module (:var:`_max_depth`). If the depth is greater
    than the maximum depth, the function would return None. Note that the input dictionary is modified in place.

    Arguments:
    ---------
    cfg : dict[str, typing.Any]
        The dictionary to be setup.

    depth : int
        The depth of the dictionary. Default to 0.

    """

    if c_depth > _max_depth:
        _logger.warning(f"The dictionary is too deep to be processed (The allowed maximum depth is {_max_depth}. "
                        f"The operation is continue processing at only first {_max_depth} layer.")
        return None

    for key, value in (cfg.items() if isinstance(cfg, dict) else enumerate(cfg)):
        if isinstance(value, (dict, list)):
            _TranslateNone(value, c_depth + 1)
        elif value == "None":
            cfg[key] = None
    return None


def TranslateNone(cfg: dict[str, Any]) -> None:
    """
    This function translates the string "None" into python NoneType object in the dictionary (which happens
    during the JSON/YAML/TOML data serialization). The depth is used to prevent the infinite loop when the
    dictionary is too deep, set as constant value in this module (:var:`_max_depth`). If the depth is greater
    than the maximum depth, the function would return None. Note that the input dictionary is modified in place.

    Arguments:
    ---------
    cfg : dict[str, typing.Any]
        The dictionary to be setup.

    """
    return _TranslateNone(cfg, 0)


# ===================================================================================
def OsGetEnvBool(env_key: str, default_if_not_found: bool = False) -> bool:
    """
    This function is a helper function to get the boolean value of the environment variable.
    The function would return the default value if the environment variable is not set.

    Arguments:
    ---------

    env_key: str
        The environment variable name to be checked.

    default_if_not_found: bool
        The default value if the environment variable is not set.

    Returns:
    -------

    bool
        The boolean value of the environment variable or the default value.

    """
    v: str = os.getenv(env_key)
    if v is None:
        return default_if_not_found
    true_value = v in ('1', 'true', 'True', 'TRUE', 'yes', 'Yes', 'YES', 'y', 'Y', 'on', 'On', 'ON')
    false_value = v in ('0', 'false', 'False', 'FALSE', 'no', 'No', 'NO', 'n', 'N', 'off', 'Off', 'OFF')
    if not true_value and not false_value:
        raise ValueError(f"Invalid boolean value: {v}")
    assert true_value and false_value, 'These two values should not be hold valid at the same time.'
    return true_value


# ===================================================================================
def OptimGC(config: dict[str, Any] | str) -> None:
    """
    This function is used to optimize the garbage collector settings.

    Arguments:
    ---------

    config: dict[str, Any] | str
        The configuration for the garbage collector. It can be a dictionary or a string representing the path
        to the config file. The config file should be in TOML format and should contain the following keys:
        - DISABLED: bool
        - CLEANUP_AND_FREEZE: bool
        - DEBUG: bool
        - GC_LVL0: int
        - GC_LVL1: int
        - GC_LVL2: int

    """
    if isinstance(config, str):  # This is the path to the config file
        import toml
        with open(config, 'r') as gc_file_stream:
            config = toml.load(gc_file_stream)['GC']
            TranslateNone(config)

    if config.get('DISABLED', False):
        gc.disable()
        return None

    # Trigger the initial garbage collection to minimize the memory usage at startup
    gc.collect(2)
    if config.get('CLEANUP_AND_FREEZE', False):
        gc.freeze()
    gc.set_threshold(
        config.get('GC_LVL0', 25000),
        config.get('GC_LVL1', 700),
        config.get('GC_LVL2', 100),
    )
    if config.get('DEBUG', False):
        gc.set_debug(gc.DEBUG_STATS)
    return None
