"""
This module contains only one utility function to deep-merge two or more dictionaries. The idea is to greatly
merge two or more dictionaries together (usually performed as the configuration files) where some custom configuration
can override the default configuration. The solution is honored to diogo's answer on StackOverflow [1] on Mar 31, 2022,
but we added some custom changes to the function.

References:
[1]: https://stackoverflow.com/questions/7204805/deep-merge-dictionaries-of-dictionaries-in-python/71700270#71700270

"""
from copy import deepcopy, copy
from functools import lru_cache
from typing import Annotated, Literal, Any, Callable

from pydantic import PositiveInt, Field

__all__ = ['deepmerge']

_immutable_types = (int, float, str, bool, type(None), tuple)
_mutable_types = (list, dict)  # Maybe to add set/frozenset in the future

_actions_l1 = Literal['override', 'bypass', 'terminate']
_copy_actions = Literal['override', 'copy', 'deepcopy']
_actions_l2 = Literal[_actions_l1, _copy_actions]
_actions_l3 = Literal[_actions_l2, 'extend', 'extend-copy', 'extend-deepcopy']

# Security Limit
_max_depth: int = 6
_min_num_base_item_in_layer: int = 12
_max_num_base_item_in_layer: int = 768


@lru_cache(maxsize=_max_depth + 1)
def _max_num_items_in_depth(depth: Annotated[PositiveInt, Field(default=_max_depth // 2 + 1, le=_max_depth)]) -> int:
    return max(_min_num_base_item_in_layer, _max_num_base_item_in_layer // (4 ** depth))


# Heuristically determined maximum number of items in the dictionary
_max_num_conf: int = 100
_max_total_items_per_default_conf: int = sum(map(_max_num_items_in_depth, range(1, _max_depth + 1)))
_max_total_items_per_addition_conf: Callable[[int], int] = lambda num_args: 32 * max(num_args, _max_num_conf)


def _depth_count(a: _mutable_types) -> int:
    if isinstance(a, dict):
        return 1 + (max(map(_depth_count, a.values())) if a else 0)
    elif isinstance(a, (list, tuple, set)):
        return 1 + (max(map(_depth_count, a)) if a else 0)
    return 0


def _item_total_count(a: dict) -> int:
    if isinstance(a, dict):
        return len(a) + sum(map(_item_total_count, a.values()))
    elif isinstance(a, (list, tuple, set)):
        return len(a) + sum(map(_item_total_count, a))
    return 0


def _trigger_update(result: dict, key: Any, value: Any, trigger: _actions_l3) -> None:
    match trigger:
        case 'override':
            result[key] = value
        case 'bypass':
            pass
        case 'terminate':
            result.pop(key)
        case 'copy':
            result[key] = copy(value)
        case 'deepcopy':
            result[key] = deepcopy(value)
        case 'extend':
            result[key].extend(value)
        case 'extend-copy':
            result[key].extend(copy(value))
        case 'extend-deepcopy':
            result[key].extend(deepcopy(value))
    return None


# =============================================================================
def _deepmerge(a: dict, b: dict, result: dict, path: list[str], /, merged_index_item: int, curdepth: int, maxdepth: int,
               not_available_immutable_action: _actions_l1, available_immutable_action: _actions_l1,
               not_available_immutable_tuple_action: _copy_actions, available_immutable_tuple_action: _copy_actions,
               not_available_mutable_action: _actions_l2, list_conflict_action: _actions_l3,
               skiperror: bool = False, ) -> dict:
    # This serves as the second layer of protection to prevent we are actually going too deep.
    if curdepth >= maxdepth:
        raise RecursionError(f"The depth of the dictionary (={curdepth}) exceeds the maximum depth (={maxdepth}).")
    curdepth += 1
    max_num_items_allowed = _max_num_items_in_depth(curdepth)
    if len(a) + len(b) > 2 * max_num_items_allowed:  # This is to prevent a subset having too many items
        raise RecursionError(f"The number of items in the dictionary exceeds twice maximum limit "
                             f"(={max_num_items_allowed}).")

    for bkey, bvalue in b.items():
        # Enforce the key to be a string. This is expected to be value on all types but if we used on TOML,
        # this could be skipped
        # bkey = str(bkey)
        path.append(bkey)

        # If the key doesn't exist in A, add the B element to A. This means that all values in B are not existed in A
        if bkey not in a:
            if isinstance(bvalue, _immutable_types):
                _trigger_update(result, bkey, bvalue, not_available_immutable_action)
            elif isinstance(bvalue, _mutable_types):
                _trigger_update(result, bkey, bvalue, not_available_mutable_action)

            elif not skiperror:
                raise TypeError(f"Conflict at {'->'.join(path[0:curdepth])} in the #{merged_index_item} configuration.")

        # We don't care scenario where A have value but B doesn't have it.
        else:
            abkey_value = a[bkey]

            # If both are immutable types, perform the action of :var:`immutable_action` on result with the value in B
            if isinstance(abkey_value, _immutable_types) and isinstance(bvalue, _immutable_types):
                _trigger_update(result, bkey, bvalue, available_immutable_action)

            elif isinstance(abkey_value, _immutable_types) and isinstance(bvalue, _mutable_types):
                # I am not sure if we have JSON reference here
                if not skiperror:
                    raise TypeError(f"Conflict at {'->'.join(path[0:curdepth])} in the #{merged_index_item} "
                                    f"configuration as value in both side are heterogeneous of type")
                else:
                    # result[bkey] = deepcopy(bvalue)
                    pass

            elif isinstance(abkey_value, _mutable_types) and isinstance(bvalue, _immutable_types):
                if not skiperror:
                    raise TypeError(f"Conflict at {'->'.join(path[0:curdepth])} in the #{merged_index_item} "
                                    f"configuration as value in both side are heterogeneous of type")
                else:
                    # result[bkey] = deepcopy(bvalue)
                    pass

            elif isinstance(abkey_value, _mutable_types) and isinstance(bvalue, _mutable_types):
                # If the key value is a dict, both in A and in B, merge the dicts
                if isinstance(abkey_value, dict) and isinstance(bvalue, dict):
                    _deepmerge(abkey_value, bvalue, result[bkey], path.copy(), merged_index_item=merged_index_item,
                               curdepth=curdepth, maxdepth=maxdepth, skiperror=skiperror,
                               not_available_immutable_action=not_available_immutable_action,
                               available_immutable_action=available_immutable_action,
                               not_available_immutable_tuple_action=not_available_immutable_tuple_action,
                               available_immutable_tuple_action=available_immutable_tuple_action,
                               not_available_mutable_action=not_available_mutable_action,
                               list_conflict_action=list_conflict_action)
                elif isinstance(abkey_value, list) and isinstance(bvalue, list):
                    _trigger_update(result, bkey, bvalue, list_conflict_action)

                elif not skiperror:
                    raise TypeError(f"Conflict at {'->'.join(path[0:curdepth])} in the #{merged_index_item} "
                                    f"configuration as value in both side are heterogeneous or unsupported of type(s)")

            # If the key value is the same in A and in B, but this can ends up with [1, 2] = [1, 2]
            elif abkey_value == bvalue:
                pass

            # This is the edge-case where the value in A and B are not the same
            elif not skiperror:
                raise Exception(f"Conflict at {'->'.join(path[0:curdepth])} in the #{merged_index_item} configuration."
                                f" It can be the result of edge-case or non-supported type")

        # Pop the last value in the path
        path.pop()

    return result


def deepmerge(a: dict, *args: dict, inline_source: bool = True, inline_target: bool = False,
              maxdepth: Annotated[PositiveInt, Field(default=_max_depth // 2 + 1, le=_max_depth)] = _max_depth // 2 + 1,
              not_available_immutable_action: _actions_l1 = 'override',
              available_immutable_action: _actions_l1 = 'override',
              not_available_immutable_tuple_action: _copy_actions = 'copy',
              available_immutable_tuple_action: _copy_actions = 'copy',
              not_available_mutable_action: _actions_l2 = 'copy',
              list_conflict_action: _actions_l3 = 'copy',
              skiperror: bool = False, ) -> dict:
    """
    Recursively merges and update two dictionaries. The result is always a new deepcopy of the dictionaries. Note
    that the function is not designed to handle circular references, and unable to prevent memory overflow when
    meeting unexpected large dictionaries.

    Parameters:
    ----------

    a: dict
        The first dictionary to be merged. This dictionary is (usually) the default configuration.

    *args: dict
        The other dictionaries to be merged. These dictionaries are (usually) the custom configuration that overrides
        the default configuration. If there are more than one custom configuration, they will be merged in order thus
        if there are conflicts, the last custom configuration will override the previous custom configuration.

        a (dict): The first dictionary.
        b (dict): The second dictionary.

    Keyword Parameters:
    ------------------

    maxdepth: PositiveInt
        The maximum depth of the dictionary to be merged. The default value is 4 and the maximum value is 6. We don't
        recommend to set the value to 8 since it may cause a stack overflow error. Also, setting max depth make it
        easier to have non-regression performance of path traversal

    skiperror: bool
        If True, the function will skip the error when it encounters a conflict. The default value is False means
        that no action is taken when a conflict is encountered, unsupported/heterogeneous type is found, or the
        dictionary is too deep.

    not_available_immutable_action: Literal['override', 'bypass', 'terminate']
        The action to be taken when the key is NOT available in the base/prior configuration and action is performed
        on immutable types.
        - 'override' (default): The value in the custom configuration will override the default configuration.
        - 'bypass': The value in the custom configuration will be ignored.
        - 'terminate': The key will be removed from the default configuration.

    available_immutable_action: Literal['override', 'bypass', 'terminate']
        The action to be taken when the key is available in the base/prior configuration and action is performed
        on immutable types.
        - 'override' (default): The value in the custom configuration will override the default configuration.
        - 'bypass': The value in the custom configuration will be ignored.
        - 'terminate': The key will be removed from the default configuration.

    not_available_immutable_tuple_action: Literal['copy', 'deepcopy']
        The action to be taken when the key is NOT available in the base/prior configuration and action is performed
        on immutable types.
        - 'copy' (default): The value will be copied.
        - 'deepcopy': The value will be deep copied.

    available_immutable_tuple_action: Literal['copy', 'deepcopy']
        The action to be taken when the key is available in the base/prior configuration and action is performed
        on tuple datatype.
        - 'copy' (default): The value will be copied.
        - 'deepcopy': The value will be deep copied.

    not_available_mutable_action: Literal['override', 'copy', 'deepcopy', 'bypass', 'terminate']
        The action to be taken when the key is NOT available in the base/prior configuration and action is performed
        on mutable types.
        - 'copy' (default): The value will be copied.
        - 'deepcopy': The value will be deep copied.
        - 'bypass': The value in the custom configuration will be ignored.
        - 'terminate': The key will be removed from the default configuration.

    list_conflict_action: Literal['extend-copy', 'extend-deepcopy', 'override-copy', 'override-deepcopy', 'terminate', 'bypass']
        The action to be taken when the key is available in the base/prior configuration and action is performed
        on list datatype.
        - 'extend-copy': The value in the custom configuration will be extended and copied.
        - 'extend-deepcopy': The value in the custom configuration will be extended and deep copied.
        - 'override-copy': The value in the custom configuration will override and copied.
        - 'override-deepcopy': The value in the custom configuration will override and deep copied.
        - 'terminate': The key will be removed from the default configuration.
        - 'bypass': The value in the custom configuration will be ignored.

    Conflict's Resolve:
    ------------------

    - 'override' (default): The value in the second dictionary will override the object in the first dictionary
        (address or pointer of the object is maintained).
    - 'bypass': The value in the second dictionary will be ignored and don't apply update
    - 'terminate': The key item in the first dictionary will be removed.
    - 'copy' (default): The value in the second dictionary will be copied and override on the object in the
        first dictionary (address or pointer of the object is renewed on the first layer).
    - 'deepcopy': The value in the second dictionary will be deep copied (a freshly new object with new memory allocation)
    - 'extend': The value in the second dictionary will be extended to the object in the first dictionary if the object
        on the first dictionary is a list. The object is maintained (no new memory allocation beside list re-allocation).
    - 'extend-copy' (default): The value in the second dictionary will be extended to the object in the first
        dictionary if the object on the first dictionary is a list. The object is copied (new memory allocation of
        the first layer).
    - 'extend-deepcopy': The value in the second dictionary will be extended to the object in the first dictionary if the
        object on the first dictionary is a list. The object is deep copied (new memory allocation of new object).

    Returns:
    -------
        dict: The merged dictionary.


    Errors:
    ------
    RecursionError: The depth of the dictionary exceeds the maximum depth.
    TypeError: The value in both side are heterogeneous or unsupported of type(s).

    We don't support available_mutable_action since it conflicts the idea of dictionary merging. Also the deepcopy
    of the content is extremely expensive.

    """
    if not args:
        return deepcopy(a) if not inline_source else a

    if not (1 <= maxdepth <= _max_depth):
        raise ValueError(f"The depth of the dictionary exceeds the maximum depth allowed (={_max_depth}).")

    if (num_args := len(args)) > _max_num_conf:
        raise ValueError(f"The number of dictionaries to be merged exceeds the maximum limit (={_max_num_conf}).")

    if (a_maxdepth := _depth_count(a)) > maxdepth:
        raise RecursionError(f"The depth of the first map (={a_maxdepth}) exceeds the maximum depth (={maxdepth})")
    if (a_maxitem := _item_total_count(a)) > _max_total_items_per_default_conf:
        raise RecursionError(f"The number of items in the first map (={a_maxitem}) exceeds the maximum "
                             f"limit (={_max_total_items_per_default_conf}).")
    arg_maxitem: int = 0
    for arg in args:
        if (arg_maxdepth := _depth_count(arg)) > maxdepth:
            raise RecursionError(f"The depth of the map (={arg_maxdepth}) exceeds the maximum depth (={maxdepth}).")
        arg_maxitem += _item_total_count(arg)
    else:
        if arg_maxitem > _max_total_items_per_addition_conf(num_args):
            raise RecursionError(f"The number of items in the map (={arg_maxitem}) exceeds the maximum "
                                 f"limit (={_max_total_items_per_addition_conf(num_args)}).")
    result = deepcopy(a) if not inline_source else a
    for idx, arg in enumerate(args):
        # We not set :arg:`a` is for checking and :arg:`result` is for the result
        # Although they both point to the same object.
        result = _deepmerge(result, arg if inline_target else deepcopy(arg), result, [],
                            merged_index_item=idx, curdepth=0, maxdepth=maxdepth,
                            skiperror=skiperror, not_available_immutable_action=not_available_immutable_action,
                            available_immutable_action=available_immutable_action,
                            not_available_immutable_tuple_action=not_available_immutable_tuple_action,
                            available_immutable_tuple_action=available_immutable_tuple_action,
                            not_available_mutable_action=not_available_mutable_action,
                            list_conflict_action=list_conflict_action)
    return result
