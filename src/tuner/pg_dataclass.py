from collections import defaultdict
from math import ceil
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.items import PG_TUNE_ITEM
import logging
from src.static.vars import APP_NAME_UPPER

__all__ = ['PG_TUNE_REQUEST', 'PG_TUNE_RESPONSE']

from src.utils.pydantic_utils import bytesize_to_hr

_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
class PG_TUNE_REQUEST(BaseModel):
    """ The PostgreSQL tuning request, initiated by the user's request for tuning up """
    options: PG_TUNE_USR_OPTIONS
    output_if_difference_only: bool = False
    include_comment: bool = False
    custom_style: str | None = None


# This section is managed by the application
class PG_TUNE_RESPONSE(BaseModel):
    """
    This class is to store the tuning result of the PostgreSQL system per each request
    """
    # Don't change the whole variable here
    outcome: dict[
        PGTUNER_SCOPE,
        dict[
            PG_SCOPE,
            dict[str, PG_TUNE_ITEM]
        ]
    ] = (
        Field(default=defaultdict(lambda: defaultdict(dict)), frozen=True,
              description="The full outcome of the tuning process. Please refer to :cls:`BaseTuner` for more details.")
    )
    outcome_cache: dict[
        PGTUNER_SCOPE,
        dict[str, Any]
    ] = (
        Field(default=defaultdict(dict), frozen=True,
              description='The full outcome of the tuning process. Please refer to :cls:`BaseTuner` for more details.')
    )

    def get_managed_items(self, target: PGTUNER_SCOPE, scope: PG_SCOPE) -> dict[str, PG_TUNE_ITEM]:
        return self.outcome[target][scope]

    def get_managed_cache(self, target: PGTUNER_SCOPE) -> dict[str, Any]:
        return self.outcome_cache[target]

    def get_managed_item_and_cache(self, target: PGTUNER_SCOPE, scope: PG_SCOPE) -> tuple[dict[str, PG_TUNE_ITEM], dict[str, Any]]:
        return self.get_managed_items(target, scope), self.get_managed_cache(target)

    def sync_cache_from_items(self, target: PGTUNER_SCOPE) -> dict:
        divergent = {}
        managed_cache = self.get_managed_cache(target)
        for scope, items in self.outcome[target].items():
            for item_name, item in items.items():
                current = managed_cache.get(item_name)
                if current != item.after:
                    divergent[item_name] = item.after
                    managed_cache = item.after
        return divergent

    def _generate_content_as_file(self, target: PGTUNER_SCOPE, request: PG_TUNE_REQUEST, backup_settings: bool = True,
                                  exclude_names: list[str] | set[str] = None) -> str:
        content: list[str] = [target.disclaimer(), '\n']
        if backup_settings:
            content.append(f"# User Options: {request.options.model_dump()}\n")
        for idx, (scope, items) in enumerate(self.outcome[target].items()):
            content.append(f'## ============================== SCOPE: {scope} ============================== \n')
            for item_name, item in items.items():
                if exclude_names is None or item_name not in exclude_names:
                    content.append(item.out(request.output_if_difference_only, request.include_comment,
                                            request.custom_style))
                    content.append('\n' * (2 if request.include_comment else 1))
            # Separate for better view
            if request.include_comment:
                content.append('\n\n\n')
            else:
                content.append('\n')
        return ''.join(content)

    def _generate_content_as_response(self, target: PGTUNER_SCOPE, exclude_names: list[str] | set[str] = None,
                                      output_format = 'conf') -> str | dict[str, Any]:
        content = {
            item_name: item.out_display(override_value=None)
            for _, items in self.outcome[target].items() for item_name, item in items.items()
            if exclude_names is None or item_name not in exclude_names
        }
        if output_format == 'text':
            content = ';\n'.join(f'{k} = {v}' for k, v in content.items())
        elif output_format == 'conf':
            content = '\n'.join(f'{k} = {v}' for k, v in content.items())
        return content

    def generate_content(self, target: PGTUNER_SCOPE, request: PG_TUNE_REQUEST,
                         exclude_names: list[str] | set[str] = None, backup_settings: bool = True,
                         output_format: Literal['json', 'text', 'conf', 'file'] = 'conf') -> str:
        if exclude_names is not None and isinstance(exclude_names, list):
            exclude_names = set(exclude_names)
        if output_format == 'file':
            return self._generate_content_as_file(target, request, backup_settings, exclude_names)
        elif output_format in ('json', 'text', 'conf'):
            return self._generate_content_as_response(target, exclude_names, output_format)

        msg: str = f'Invalid output format: {output_format}. Expected one of "json", "text", "conf", "file".'
        _logger.error(msg)
        raise ValueError(msg)

    def mem_test(self, options: PG_TUNE_USR_OPTIONS, use_full_connection: bool = False,
                 ignore_report: bool = True) -> tuple[str, int | float]:
        # Cache result first
        _kwargs = options.tuning_kwargs
        usable_ram_noswap = options.usable_ram_noswap
        usable_ram_noswap_hr = bytesize_to_hr(usable_ram_noswap)
        ram_noswap = options.ram_noswap
        ram_noswap_hr = bytesize_to_hr(ram_noswap)
        usable_ram_noswap_ratio = usable_ram_noswap / ram_noswap
        managed_cache = self.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG)

        # Number of Connections
        max_user_conns = (managed_cache['max_connections'] - managed_cache['superuser_reserved_connections'] -
                          managed_cache['reserved_connections'])
        active_user_conns = ceil(max_user_conns * _kwargs.effective_connection_ratio)
        num_user_conns = (max_user_conns if use_full_connection else active_user_conns)
        os_conn_overhead = (num_user_conns * _kwargs.single_memory_connection_overhead *
                            _kwargs.memory_connection_to_dedicated_os_ratio)

        # Shared Buffers and WAL buffers
        shared_buffers = managed_cache['shared_buffers'] * _kwargs.shared_buffers_fill_ratio
        wal_buffers = managed_cache['wal_buffers']

        # Temp Buffers and Work Mem
        temp_buffers = managed_cache['temp_buffers']
        work_mem = managed_cache['work_mem'] * managed_cache['hash_mem_multiplier']
        total_working_memory = (temp_buffers + work_mem) # * (1 + managed_cache['max_parallel_workers_per_gather'])
        total_working_memory_hr = bytesize_to_hr(total_working_memory)

        max_total_memory_used = shared_buffers + wal_buffers + os_conn_overhead
        max_total_memory_used += total_working_memory * num_user_conns
        max_total_memory_used_hr = bytesize_to_hr(max_total_memory_used)

        _report = f'''
# ===========================================================================================================
# Memory Estimation Test by **TRUE**
From server-side, the PostgreSQL memory usable arena is at most {usable_ram_noswap_hr} or {usable_ram_noswap_ratio * 100:.2f} (%) of the total RAM ({bytesize_to_hr(ram_noswap)}).
All other variables must be bounded and computed within the available memory. 
Arguments: use_full_connection={use_full_connection}

Reports (over usable RAM capacity {usable_ram_noswap_hr} or {usable_ram_noswap_ratio * 100:.2f} (%) of total):
-------
* PostgreSQL memory (estimate): {max_total_memory_used_hr} or {max_total_memory_used / usable_ram_noswap * 100:.2f} (%) over usable RAM.
    - The shared_buffers ratio is {shared_buffers / usable_ram_noswap * 100:.2f} (%) or {bytesize_to_hr(shared_buffers)}
    - The wal_buffers is {bytesize_to_hr(wal_buffers)} 
    - The total connections overhead ratio is {bytesize_to_hr(os_conn_overhead)} with {num_user_conns} user connections.
    - The total maximum working memory (assuming with one maximum work_mem and peak temporary buffers) is as 
        + SINGLE: {total_working_memory_hr} per user connections or {total_working_memory / usable_ram_noswap * 100:.2f} (%)
            -> Temp Buffers: {bytesize_to_hr(temp_buffers)}
            -> Work Mem: {bytesize_to_hr(work_mem / managed_cache['hash_mem_multiplier'])}
            -> Hash Mem Multiplier: {managed_cache['hash_mem_multiplier']}
        + ALL: {total_working_memory * num_user_conns / usable_ram_noswap * 100:.2f} (%)
        + Parallel Workers: 
            -> Gather Workers: {managed_cache['max_parallel_workers_per_gather']}
            -> Worker in Pool: {managed_cache['max_parallel_workers']}
    - Work mem Scale Factor: {_kwargs.work_mem_scale_factor} -> Followed the normal calculation: {_kwargs.work_mem_scale_factor == 1.0}

OK STATUS: {max_total_memory_used <= usable_ram_noswap}
WARNING: These calculations could be incorrect due to capping, precision adjustment, rounding.
# ===========================================================================================================
'''
        if not ignore_report:
            _logger.info(_report)
        return _report, max_total_memory_used





