import logging
from typing import Any, Callable

from pydantic import Field, BaseModel, model_validator

from src.static.vars import APP_NAME_UPPER, MULTI_ITEMS_SPLIT, WEB_MODE
from src.tuner.data.items import PG_TUNE_ITEM
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.pg_dataclass import PG_TUNE_REQUEST, PG_TUNE_RESPONSE
from src.utils.timing import time_decorator

__all__ = ['GeneralTuner']
_logger = logging.getLogger(APP_NAME_UPPER)


class GeneralTuner(BaseModel):
    """
    This file introduces the base class for the tuner. Current support is worked on these pairs: (kernel, sysctl),
    (database, config).

    Parameters:
    ----------

    target: PGTUNER_SCOPE
        The target scope of the tuning. The supported values are PG_SCOPE.KERNEL_SYSCTL and PG_SCOPE.DATABASE_CONFIG.

    tune_type: Literal['sysctl', 'boot', 'config', ...]
        The type of tuning. It can be either 'sysctl', 'boot', 'config', etc.

    items: list[tuple[PG_SCOPE, dict]]
        The tuning items. It is a list of tuples, where the first element is the scope of the tuning, and the second
        element is the dictionary of the tuning items.

    """
    target: PGTUNER_SCOPE = (
        Field(..., description='Target of the tuning', frozen=True)
    )
    items: dict[str, tuple[PG_SCOPE, dict, dict]] = (
        Field(description='The tuning items', frozen=True)
    )

    # Add post-init on support here
    @model_validator(mode='after')
    def check_support(self):
        if self.target not in (PGTUNER_SCOPE.KERNEL_SYSCTL, PGTUNER_SCOPE.DATABASE_CONFIG):
            raise ValueError(f'The target scoping is not supported in this class: {self.target}')
        return self

    @staticmethod
    def _VarTune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE,
                 group_cache: dict[str, Any], global_cache: dict[str, Any],
                 tune_op: Callable[[dict[str, Any], dict[str, Any], PG_TUNE_USR_OPTIONS, PG_TUNE_RESPONSE], Any] = None,
                 default: Any = None) -> Any:
        if tune_op is not None:
            try:
                return tune_op(group_cache, global_cache, request.options, response), tune_op
            except TypeError as e:
                _logger.error(f'Error in tuning the variable: {e} --> Returning the default value.')
        return default, default

    @staticmethod
    def _make_itm(key: str, before: Any, after: Any, trigger: Any, tune_entry,
                  hardware_scope: tuple[str, str]) -> PG_TUNE_ITEM:
        return PG_TUNE_ITEM(key=key, before=before, after=after, trigger=trigger, hardware_scope=hardware_scope,
                            comment=tune_entry.get('comment', None), style=tune_entry.get('style', None),
                            partial_func=tune_entry.get('partial_func', None))

    @staticmethod
    def _get_fn_default(key: str, tune_entry: dict, hw_scope: str):
        _msg: str = ''
        if 'instructions' not in tune_entry:  # No profile-based tuning
            _msg = f'DEBUG: Profile-based tuning is not found for this item {key} -> Use the general tuning instead.'
            fn = tune_entry.get('tune_op', None)
            default = tune_entry['default']
            return fn, default, _msg

        # Profile-based Tuning
        profile_fn = tune_entry['instructions'].get(hw_scope, None)
        profile_default = tune_entry['instructions'].get(f'{hw_scope}_default', None)

        if profile_default is None:
            profile_default = tune_entry['default']
            if profile_fn is None or not isinstance(profile_fn, Callable):
                _msg = (f"WARNING: Profile-based tuning function collection is not found for this item {key} but the "
                        f"associated hardware scope '{hw_scope}' is NOT found")
        return profile_fn, profile_default, _msg

    @time_decorator
    def optimize(self, request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE) -> None:
        # Now write into the sys_shared.outcome_cache
        post_condition_check = not WEB_MODE
        _logger.warning(f'The post-condition check is enabled? {post_condition_check}')
        global_cache: dict[str, Any] = response.outcome_cache[self.target]
        _dummy_fn = lambda *args, **kwargs: True

        for _, (scope, category, _) in self.items.items():
            group_cache: dict[str, Any] = {}
            group_itm: list[tuple[PG_TUNE_ITEM, Callable | None]] = []  # A group of tuning items
            managed_items = response.get_managed_items(self.target, scope)

            # Batched Logging
            _info_log = [f"\n====== Start the tuning process with scope: {scope} ======"]
            _warn_error_log = []
            for mkey, tune_entry in category.items():
                # Perform tuning on multi-items that shared same tuning operation (rare case, but possible)
                keys = mkey.split(MULTI_ITEMS_SPLIT)
                key = keys[0].strip()

                # Check the profile scope of the tuning item, if not found, fallback to the workload_profile;
                # If found then we use specific scope to choose the profile-based tuning operation.
                hw_scope_term: str = tune_entry.get('hw_scope_term', 'overall')
                hw_scope_value: str = request.options.translate_hardware_scope(term=hw_scope_term)

                # We don't want to apply safeguard here to deal with non-sanitized profile from custom user input.
                # If they need custom change on the tuning after the profile is applied, they can do it manually
                # after our tuning is applied.
                fn, default, _msg = GeneralTuner._get_fn_default(key, tune_entry, hw_scope_value)
                if _msg:
                    if _msg.startswith('DEBUG'):
                        # _info_log.append(_msg)
                        pass
                    elif _msg.startswith('WARNING'):
                        _warn_error_log.append(_msg)
                result, triggering = GeneralTuner._VarTune(request, response, group_cache, global_cache,
                                                           tune_op=fn, default=default)
                itm = self._make_itm(key, None, after=result or tune_entry['default'], trigger=triggering,
                                     tune_entry=tune_entry, hardware_scope=(hw_scope_term, hw_scope_value))

                if itm is None or itm.after is None:  # A must-have condition. DO NOT remove
                    _warn_error_log.append(f"WARNING: Error in tuning the variable as default value is not found or "
                                           f"set to None for '{key}' -> Skipping and not adding to the final result.")
                    continue

                # Perform post-condition check:
                if post_condition_check:
                    if not tune_entry.get('post-condition', _dummy_fn)(itm.after):
                        _warn_error_log.append(f"ERROR: Post-condition self-check of '{key}' failed on new value "
                                               f"{itm.after}. Skipping and not adding to the final result.")
                        continue
                    if not tune_entry.get('post-condition-group', _dummy_fn)(itm.after, group_cache, request.options):
                        _warn_error_log.append(f"ERROR: Post-condition group-check of '{key}' failed on new value "
                                               f"{itm.after}. Skipping and not adding to the final result.")
                        continue

                # We don't add failing validation result to the cache, which is used for instruction-based tuning
                # and result validation. We only add the successful result to the cache.
                group_cache[key] = itm.after
                _post_condition_all_fn = tune_entry.get('post-condition-all', _dummy_fn)
                group_itm.append((itm, _post_condition_all_fn))
                _info_log.append(f"Variable '{key}' has been tuned from {itm.before} to {itm.out_display()}.")

                # Perform the cloning of tuning items for same result
                for k in keys[1:]:
                    sub_key = k.strip()
                    _itm = itm.model_copy(update={'key': sub_key}, deep=False)
                    group_cache[sub_key] = _itm.after
                    group_itm.append((_itm, _post_condition_all_fn))
                    _info_log.append(f"Variable '{sub_key}' has been tuned from {_itm.before} to {_itm.out_display()} "
                                     f"by copying the tuning result from '{key}'.")

            # Perform global post-condition check
            for itm, post_func in group_itm:
                if post_condition_check and not post_func(itm.after, global_cache, request.options):
                    _warn_error_log.append(f"ERROR: Post-condition total-check of '{itm.key}' failed on new value "
                                           f"{itm.after}. The tuning item is not added to the final result.")
                    continue

                # Since this item has passed all the checks, we add it to the items
                global_cache[itm.key] = itm.after
                managed_items[itm.key] = itm

            # Batched Logging Display
            if _info_log:
                _logger.info('\n'.join(_info_log))
            if _warn_error_log:
                _logger.warning('\n'.join(_warn_error_log))

        return None
