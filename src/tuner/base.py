from functools import lru_cache

from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.pg_dataclass import PG_TUNE_REQUEST, PG_SYS_SHARED_INFO
from typing import Literal, Any, Callable
from pydantic import Field, BaseModel, ByteSize, model_validator
from src.static.vars import APP_NAME_UPPER, MULTI_ITEMS_SPLIT
import logging
from src.tuner.data.scope import PG_SCOPE
from src.tuner.data.items import PG_TUNE_ITEM

__all__ = ["GeneralTuner", "cast_number_to_pydantic_bytesize"]

_logger = logging.getLogger(APP_NAME_UPPER)


class _ByteSizeCaster(BaseModel):
    size: ByteSize

# Add :type:`int` here to prevent the PyCharm warning
def cast_number_to_pydantic_bytesize(value: str | int | float | ByteSize) -> ByteSize | int:
    return _ByteSizeCaster(size=value).size


class GeneralTuner(BaseModel):
    """
    This file introduces the base class for the tuner. Current support is worked on these pairs: (kernel, sysctl),
    (database, config).

    Parameters:
    ----------

    target: Literal['kernel', 'database']
        The target of the tuning. It can be either 'kernel' or 'database'.

    tune_type: Literal['sysctl', 'boot', 'config', ...]
        The type of tuning. It can be either 'sysctl', 'boot', 'config', etc.

    items: list[tuple[PG_SCOPE, dict]]
        The tuning items. It is a list of tuples, where the first element is the scope of the tuning, and the second
        element is the dictionary of the tuning items.

    ignore_source_result: bool
        If set to True, the comparison between the source and the tuning item would be ignored.

    ignore_optim_if_not_found_in_source: bool
        Ignore the optimization if tuning item in the source is not found. This variable is not effect when you set the
        :attr:`ignore_source_result` to True (default to True).

    """
    target: Literal['kernel', 'database'] = (
        Field(..., description="Target of the tuning", frozen=True)
    )
    tune_type: Literal['sysctl', 'boot', 'config'] = (
        Field(..., description="Type of tuning", frozen=True)
    )
    items: dict[str, tuple[PG_SCOPE, dict, str]] = (
        Field(description="The tuning items", frozen=True)
    )
    ignore_source_result: bool = (
        Field(default=False, frozen=True,
              description="If set to True, the comparison between the source and the tuning item would be ignored. "
                          "This is useful when you want to apply the tuning without comparing the source. Default to "
                          "False.",
              )
    )
    ignore_optim_if_not_found_in_source: bool = (
        Field(default=True, frozen=True,
              description="Ignore the optimization if tuning item in the source is not found. This variable is not "
                          "effect when you set the :attr:`ignore_source_result` to True (default to True).",
              )
    )
    # Add post-init on support here
    @model_validator(mode='after')
    def check_support(self):
        supported_pairs = [('kernel', 'sysctl'), ('database', 'config')]
        if (self.target, self.tune_type) not in supported_pairs:
            raise ValueError(f"The pair ({self.target}, {self.tune_type}) is not supported.")
        return self


    @staticmethod
    def _VarTune(request: PG_TUNE_REQUEST, sys_record: PG_SYS_SHARED_INFO,
                 group_cache: dict[str, Any], global_cache: dict[str, Any],
                 tune_op: Callable[[dict[str, Any], dict[str, Any], PG_TUNE_USR_OPTIONS, PG_SYS_SHARED_INFO], Any] = None,
                 default: Any = None) -> Any:
        if tune_op is not None and isinstance(tune_op, Callable):
            try:
                return tune_op(group_cache, global_cache, request.options, sys_record), tune_op
            except TypeError as e:
                _logger.error(f"Error in tuning the variable: {e} --> Returning the default value.")
        return default, default

    def optimize(self, request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO) -> None:
        backup_snapshot = sys_info.backup.get(f'{self.target}-{self.tune_type}', None)    # Use empty
        is_empty_snapshot: bool = self.ignore_source_result or backup_snapshot is None or len(backup_snapshot) == 0
        if is_empty_snapshot:
            _logger.debug(f"The backup snapshot of {self.target}-{self.tune_type} is not found. Please ensure the "
                          f"backup is happened and loaded to the system information.")
        static_profile_mapper = {
            'cpu': ({'cpu', 'CPU'}, request.options.cpu_profile),
            'mem': ({'memory', 'MEMORY'}, request.options.mem_profile),
            'net': ({'network', 'NET', 'net', 'NETWORK'}, request.options.net_profile),
            'disk': ({'disk', 'io', 'i/o', 'I/O', 'iops', 'IOPS'}, request.options.disk_profile)
        }
        @lru_cache(maxsize=32)
        def _term_to_profile(term: str | None) -> str:
            if term:
                term = term.lower().strip()
                for pkey, (alternative, pvalue) in static_profile_mapper.items():
                    if term == pkey or term in alternative:
                        return pvalue
            return request.options.overall_profile

        # Now write into the sys_shared.outcome_cache
        global_cache: dict[str, Any] = {}
        sys_info.outcome_cache[self.target][self.tune_type] = global_cache  # Setup cache pointer
        for _, (scope, category, default_term) in self.items.items():
            group_cache: dict[str, Any] = {}
            group_itm: list[PG_TUNE_ITEM] = []
            managed_items = sys_info.get_managed_items(self.target, self.tune_type, scope)
            for mkey, tune_entry in category.items():
                # Perform tuning on multi-items that shared same tuning operation (rare case, but possible)
                for key in mkey.split(MULTI_ITEMS_SPLIT):
                    key: str = key.strip()
                    if not key:
                        msg = (f"Invalid key '{key}' is found in the tuning items, as the tuning key should not be "
                               f"empty. Skipping...")
                        _logger.error(msg)
                        raise ValueError(msg)
                    if ' ' in key:
                        msg = (f"Invalid key '{key}' is found in the tuning items, as the tuning key should not "
                               f"contain any whitespace. Skipping...")
                        _logger.error(msg)
                        raise ValueError(msg)

                    cvar = backup_snapshot.get(key, None) if isinstance(backup_snapshot, dict) else None
                    if not is_empty_snapshot and cvar is not None:
                        _logger.debug(f"Tuning item '{key}' is not found in the current configuration. This "
                                      f"implies the server does not support this key. "
                                      f"Continue tuning: ... {self.ignore_optim_if_not_found_in_source} ...")
                        if not self.ignore_optim_if_not_found_in_source:
                            # Some sysctl keys may not available on normal operation, but root user can
                            # see it, or some variables you need to add more.
                            continue

                    # Collect value and determine execution order
                    if 'default' not in tune_entry:
                        raise KeyError(f"Default (:key:`default`) value must be available in the tuning item '{key}'.")

                    # Check the profile scope of the tuning item, if not found, fallback to the overall_profile;
                    # If found then we use specific scope to choose the profile-based tuning operation.
                    tune_entry_profile_mapper: str = _term_to_profile(tune_entry.get("profile", default_term))

                    # We don't want to apply safeguard here to deal with non-sanitized profile from custom user input.
                    # If they need custom change on the tuning after the profile is applied, they can do it manually
                    # after our tuning is applied.
                    profile_based_tune_operation: dict = tune_entry.get("instructions", None)
                    general_based_tune_operation: Callable = tune_entry.get("tune_op", None)
                    _logger.debug(f'Item: {key} with profile: {tune_entry_profile_mapper} started tuning ...')
                    itm: PG_TUNE_ITEM | None = None
                    if profile_based_tune_operation and itm is None:
                        profile_fn = profile_based_tune_operation.get(tune_entry_profile_mapper, None)
                        profile_default = profile_based_tune_operation.get(f"{tune_entry_profile_mapper}_default", None)
                        if not profile_fn or not isinstance(profile_fn, Callable):
                            _logger.warning(f"Profile-based tuning is not found for this item {key}. "
                                            f"Try with default option ...")

                        result, triggering = GeneralTuner._VarTune(request, sys_info, group_cache, global_cache,
                                                                   tune_op=profile_fn, default=profile_default)
                        if result is not None:
                            itm = PG_TUNE_ITEM(key=key, before=cvar, after=result,
                                               comment=tune_entry.get("comment", None),
                                               prefix=tune_entry.get("prefix", None),
                                               style=tune_entry.get('style', None), trigger=triggering,
                                               partial_func=tune_entry.get("partial_func", None))
                    if general_based_tune_operation and itm is None:
                        if not isinstance(general_based_tune_operation, Callable):
                            _logger.warning(f"General-based tuning is not found for this item {key}. "
                                            f"Try with default option ...")

                        result, triggering = GeneralTuner._VarTune(request, sys_info, group_cache, global_cache,
                                                                   tune_op=general_based_tune_operation,
                                                                   default=tune_entry["default"])
                        if result is not None:
                            itm = PG_TUNE_ITEM(key=key, before=cvar, after=result,
                                               comment=tune_entry.get("comment", None),
                                               prefix=tune_entry.get("prefix", None),
                                               style=tune_entry.get('style', None), trigger=triggering,
                                               partial_func=tune_entry.get("partial_func", None))
                    if itm is None:
                        if tune_entry["default"] is None:
                            _logger.warning(f"Error in tuning the variable as default value is not found or set to "
                                            f"None for '{key}'. Skipping...")
                        else:
                            itm = PG_TUNE_ITEM(key=key, before=cvar, after=tune_entry["default"],
                                               comment=tune_entry.get("comment", None),
                                               prefix=tune_entry.get("prefix", None),
                                               style=tune_entry.get('style', None),
                                               trigger=tune_entry["default"],
                                               partial_func=tune_entry.get("partial_func", None))
                    if itm is None:
                        continue

                    # Perform post-condition check:
                    if 'post-condition' in tune_entry and not tune_entry['post-condition'](itm.after):
                        if not tune_entry['post-condition'](itm.after):
                            _logger.error(f"Post-condition self-check of '{key}' failed on new value "
                                          f"{itm.after}. Skipping...")
                            continue
                    if 'post-condition-group' in tune_entry:
                        if not tune_entry['post-condition-group'](itm.after, group_cache, sys_info):
                            _logger.error(f"Post-condition group-check of '{key}' failed on new value "
                                          f"{itm.after}. Skipping...")
                            continue

                    # We don't add failing validation result to the cache, which is used for instruction-based tuning
                    # and result validation. We only add the successful result to the cache.
                    group_cache[key] = itm.after
                    group_itm.append(itm)
                    _logger.info(f"Variable '{key}' has been tuned from {itm.before} to {itm.out_display()}.")

            # Perform global post-condition check
            for itm in group_itm:
                try:
                    if 'post-condition-all' in category[itm.key]:
                        if not category[itm.key]['post-condition-all'](itm.after, global_cache, sys_info):
                            _logger.error(f"Post-condition total-check of '{itm.key}' failed on new value {itm.after}. "
                                          f"Skipping...")
                            continue
                except KeyError:

                    for key in category.keys():
                        if itm.key in key:
                            _logger.info(f'This {itm.key} is part of the group {key}.')
                            if 'post-condition-all' in category[key]:
                                if not category[key]['post-condition-all'](itm.after, global_cache, sys_info):
                                    _logger.error(f"Post-condition total-check of '{itm.key}' failed on new value "
                                                  f"{itm.after}. Skipping...")
                                    continue
                            # First found and break early (not a good method) but it works
                            break

                global_cache[itm.key] = itm.after

                # Since this item has passed all the checks, we add it to the items
                managed_items[itm.key] = itm

        return None