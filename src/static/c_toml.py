"""
This contains some utility functions to work with TOML files.

"""

import typing
import logging
from datetime import datetime, timedelta
import json

import toml
import os

from src.static.vars import APP_NAME_UPPER, PRESET_PROFILE_CHECKSUM, PGTUNER_PROFILE_FILE_PATH, APP_NAME_LOWER
from src.utils.dict_deepmerge import deepmerge
from src.static.c_timezone import GetTimezone
from src.utils.checksum import checksum
from rich import print_json
try:
    import rich
except ImportError as e:
    rich = None
    print(f"Failed to import rich: {e}")


__all__ = ['TranslateNone', 'LoadAppToml']
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

# =============================================================================
__APP_CACHE: dict[str, tuple[datetime, dict[str, typing.Any]]] = {

}
def LoadAppToml(force: bool = False, expiry_seconds: int = 0, perform_checksum: bool = True,
                skip_checksum_verification: bool = True, verbose: bool = False) -> dict:
    """
    This function would load all the TOML files used for this application and saved it into our internal cache.
    If the :arg:`force` is set to True, the cache would be ignored and the TOML files would be reloaded. The
    datetime in the cache is set for future reservation whereas live change can be applied within a timely
    manner. Note that only the registered TOML filepath would be loaded to prevent issue.

    Arguments:
    ----------

    force : bool
        The flag to force reload the TOML files.

    expiry_seconds : int | timedelta
        The expiry time for the cache. If the earliest cache is older than this value, the cache would be reloaded.
        Default to 0 means ignore the cache lifetime. For example, if at least one of the TOML cache is 5 minutes old,
        and the :var:`expiry_seconds` is 3 minutes (180 seconds), the cache would be flushed and retried.

    perform_checksum : bool
        The flag to perform the checksum verification. Default to True. If set to False, the checksum calculation
        and verification would be skipped.

    skip_checksum_verification : bool
        The flag to skip the checksum verification. This is useful when the TOML files are not modified and the
        checksum is not needed to be verified. Default to False. If set to True and checksum verification failed,
        the ValueError would be raised. Note that this flag is only effective when :arg:`perform_checksum` is set
        to True.

    Returns:
    -------
        The dictionary of the TOML files.

    """
    dt = datetime.now(tz=GetTimezone()[0])
    if __APP_CACHE and not force:
        if expiry_seconds == 0:
            return __APP_CACHE[APP_NAME_LOWER + '-final'][1]
        if expiry_seconds < 0:
            message = f'Invalid expiry_seconds value: {expiry_seconds}, expected a positive integer.'
            _logger.error(message)
            raise ValueError(message)
        for _, (cache_dt, _) in __APP_CACHE.items():
            if dt - cache_dt > timedelta(seconds=expiry_seconds):
                break
        else:
            return __APP_CACHE[APP_NAME_LOWER + '-final'][1]

    # Clear all application cache, then reload all valid TOML files
    __APP_CACHE.clear()
    for filepath, algorithm, preset_checksum in PRESET_PROFILE_CHECKSUM:
        if not os.path.exists(filepath):
            _logger.error(f"{filepath} is not found.")
            raise FileNotFoundError(f"{filepath} is not found.")

        if perform_checksum:
            current_checksum = checksum(filepath, alg=algorithm)
            _logger.debug(f'Checksum of {filepath} with algorithm {algorithm.upper()}: '
                          f'\n-> Preset  : {preset_checksum} '
                          f'\n-> Current : {current_checksum}'
                          f'\n-> Matched : {current_checksum == preset_checksum}')
            if current_checksum != preset_checksum and not skip_checksum_verification:
                message = (f"\nThe expected TOML file {filepath} has been modified as the checksum is not matched. "
                           f"\n-> Expected: {preset_checksum}"
                           f"\n-> Current : {current_checksum}")
                _logger.warning(message)
                raise ValueError(message)

        with open(filepath, 'r') as f:
            content = toml.load(f)[APP_NAME_LOWER]  # Only load our application's content signature
            TranslateNone(content)
            __APP_CACHE[filepath] = (datetime.now(tz=GetTimezone()[0]), content)

    # Merge all result together
    main_content = __APP_CACHE[PGTUNER_PROFILE_FILE_PATH][1]
    sub_contents = [content for filepath, (_, content) in __APP_CACHE.items() if filepath != PGTUNER_PROFILE_FILE_PATH]
    result = deepmerge(main_content, *sub_contents)
    __APP_CACHE[APP_NAME_LOWER + '-final'] = (datetime.now(tz=GetTimezone()[0]), result)
    _logger.info(f"Successfully loaded the TOML files for application {APP_NAME_LOWER}. Result as follows:"
                 f"\nJSON: {json.dumps(result, allow_nan=False, sort_keys=True)}")
    if rich is not None and verbose:
        print_json(data=result)

    return result
