"""
This contains some common functions during the general tuning

"""
import logging
from typing import Callable

from src.static.vars import MULTI_ITEMS_SPLIT, APP_NAME_UPPER
from src.tuner.data.scope import PG_SCOPE

__all__ = ['merge_extra_info_to_profile', 'type_validation', 'rewrite_items']
_logger = logging.getLogger(APP_NAME_UPPER)


def merge_extra_info_to_profile(profiles: dict[str, tuple[PG_SCOPE, dict, dict]]):
    """
    Merge the profile data into a single file.
    """
    for _, (_, items, extra_default) in profiles.items():
        for default_key, default_value in extra_default.items():
            for itm_name, itm_value in items.items():
                if default_key not in itm_value:
                    itm_value[default_key] = default_value
    return None


def type_validation(profiles: dict[str, tuple[PG_SCOPE, dict, dict]]) -> dict[str, tuple[PG_SCOPE, dict, dict]]:
    """ Type validation for the profile data. """
    for _, (scope, category_profile, _) in profiles.items():
        for mkey, tune_entry in category_profile.items():
            # Narrow check
            assert isinstance(tune_entry, dict), f'The tuning key body of {mkey} is not a dictionary.'
            assert isinstance(mkey, str), f'The key {mkey} is not a string.'
            keys: list[str] = [k.strip() for k in mkey.split(MULTI_ITEMS_SPLIT)]
            assert all(
                k and ' ' not in k for k in keys), f'The key representation {mkey} is empty or contain whitespace.'

            # Body check
            assert 'default' in tune_entry, (f'The default value is not found in the tuning key body of {mkey} '
                                             f'this could leads to no result of tuning')
            assert not isinstance(tune_entry['default'], Callable) and tune_entry['default'] is not None, \
                f'{mkey}: The default value must be a non-null static value.'
            if 'tune_op' in tune_entry:
                assert isinstance(tune_entry['tune_op'], Callable), \
                    f'{mkey}: The generic tuning operation must be a function.'

            if 'instructions' in tune_entry:
                assert isinstance(tune_entry['instructions'], dict), \
                    (f'{mkey}: The profile-based instructions must be a dictionary of mixed instructions '
                     f'and static value.')
                for pr_key, pr_value in tune_entry['instructions'].items():
                    assert not isinstance(pr_key, Callable) and pr_key is not None, \
                        f'{mkey}-ins-{pr_key}: The profile key must be a non-null, non-empty static value.'
                    if pr_key.endswith('_default'):
                        assert not isinstance(pr_value, Callable) and pr_value is not None, \
                            f'{mkey}-ins-{pr_key}: The profile default value must be a non-null static value.'
                    else:
                        assert isinstance(pr_value, Callable), \
                            f'{mkey}-ins-{pr_key}: The profile tuning guideline must be a function.'

    return profiles


def rewrite_items(profiles: dict[str, tuple[PG_SCOPE, dict, dict]]) -> dict[str, tuple[PG_SCOPE, dict, dict]]:
    """ Drop the deprecated items from the profile data. """
    for _, (_, items, _) in profiles.items():
        remove_keys = []
        for mkey, _ in items.items():
            if mkey.startswith('-'):
                remove_keys.append(mkey[1:])
        for rm_key in remove_keys:
            if rm_key in items:
                assert MULTI_ITEMS_SPLIT not in rm_key, f'Only a single tuning key is allowed for deletion: {rm_key}'
                items.pop(rm_key)
            else:
                _logger.warning(f'The tuning key {rm_key} is expected to be removed but not found in its scope or '
                                f'tuning result.')
            items.pop(f'-{rm_key}')
    return profiles
