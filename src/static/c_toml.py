""" This contains some utility functions to work with TOML files. """
import logging
import typing
from src.static.vars import APP_NAME_UPPER

try:
    import rich
except ImportError as e:
    rich = None
    print(f"Failed to import rich: {e}")

__all__ = ['TranslateNone']
_logger = logging.getLogger(APP_NAME_UPPER)
_max_depth: int = 6


def _TranslateNone(cfg: dict[str, typing.Any] | list[typing.Any], c_depth: int) -> None:
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


def TranslateNone(cfg: dict[str, typing.Any]) -> None:
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
