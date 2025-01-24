import logging
from collections import defaultdict
from math import ceil
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.static.vars import APP_NAME_UPPER, Gi, Mi, Ki, K10
from src.tuner.data.items import PG_TUNE_ITEM
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.profile.database.shared import wal_time
from src.utils.pydantic_utils import bytesize_to_hr

__all__ = ['PG_TUNE_REQUEST', 'PG_TUNE_RESPONSE']
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

    def get_managed_items_and_cache(self, target: PGTUNER_SCOPE, scope: PG_SCOPE) -> tuple[
        dict[str, PG_TUNE_ITEM], dict[str, Any]]:
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
            content.append(f'## =============== SCOPE: {scope} =============== \n')
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
                                      output_format='conf') -> str | dict[str, Any]:
        content = {
            item_name: item.out_display(override_value=None)
            for _, items in self.outcome[target].items() for item_name, item in items.items()
            if exclude_names is None or item_name not in exclude_names
        }
        if output_format == 'conf':
            content = '\n'.join(f'{k} = {v}' for k, v in content.items())
        return content

    def generate_content(self, target: PGTUNER_SCOPE, request: PG_TUNE_REQUEST,
                         exclude_names: list[str] | set[str] = None, backup_settings: bool = True,
                         output_format: Literal['json', 'conf', 'file'] = 'conf') -> str:
        if exclude_names is not None and isinstance(exclude_names, list):
            exclude_names = set(exclude_names)
        if output_format == 'file':
            return self._generate_content_as_file(target, request, backup_settings, exclude_names)
        elif output_format in ('json', 'conf'):
            return self._generate_content_as_response(target, exclude_names, output_format)

        msg: str = f'Invalid output format: {output_format}. Expected one of "json", "conf", "file".'
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
        total_working_memory = (temp_buffers + work_mem)  # * (1 + managed_cache['max_parallel_workers_per_gather'])
        total_working_memory_hr = bytesize_to_hr(total_working_memory)

        max_total_memory_used = shared_buffers + wal_buffers + os_conn_overhead
        max_total_memory_used += total_working_memory * num_user_conns
        max_total_memory_used_hr = bytesize_to_hr(max_total_memory_used)

        # Effective Cache Size
        effective_cache_size = managed_cache['effective_cache_size']

        # WAL Times
        wal_throughput = options.wal_spec.raid_perf()[0]
        wal10 = wal_time(managed_cache['wal_buffers'], 1.0, _kwargs.wal_segment_size,
                         managed_cache['wal_writer_delay'], wal_throughput)
        wal15 = wal_time(managed_cache['wal_buffers'], 1.5, _kwargs.wal_segment_size,
                         managed_cache['wal_writer_delay'], wal_throughput)
        wal20 = wal_time(managed_cache['wal_buffers'], 2.0, _kwargs.wal_segment_size,
                         managed_cache['wal_writer_delay'], wal_throughput)

        _report = f'''
# ============================================================================================
# Memory Estimation Test by {APP_NAME_UPPER}
From server-side, the PostgreSQL memory usable arena is at most {usable_ram_noswap_hr} or {usable_ram_noswap_ratio * 100:.2f} (%) of the total RAM ({bytesize_to_hr(ram_noswap)}).
All other variables must be bounded and computed within the available memory. 
CPU: {options.vcpu} logical cores
RAM: {ram_noswap_hr} or ratio: ({(ram_noswap / options.vcpu / Gi):.1f}).

Arguments: use_full_connection={use_full_connection}
Reports Summary (over usable RAM capacity):
------------------------------------------
* PostgreSQL memory (estimate): {max_total_memory_used_hr} or {max_total_memory_used / usable_ram_noswap * 100:.2f} (%) over usable RAM.
    - The Shared Buffers is {bytesize_to_hr(shared_buffers)} or {shared_buffers / usable_ram_noswap * 100:.2f} (%)
    - The Wal Buffers is {bytesize_to_hr(wal_buffers)} or {wal_buffers / usable_ram_noswap * 100:.2f} (%)
    - The total connections overhead ratio is {bytesize_to_hr(os_conn_overhead)} with {num_user_conns} idle user connections 
        + Peak assumption is at {bytesize_to_hr(os_conn_overhead / _kwargs.memory_connection_to_dedicated_os_ratio)}
        + Reserved & Superuser Reserved Connections: {managed_cache['max_connections'] - max_user_conns}
        + Need Connection Pool such as PgBouncer: {num_user_conns >= options.vcpu * 8}
    - The total maximum working memory (assuming with one full use of work_mem and temp_buffers):
        + SINGLE: {total_working_memory_hr} per user connections or {total_working_memory / usable_ram_noswap * 100:.2f} (%)
            -> Temp Buffers: {bytesize_to_hr(temp_buffers)}
            -> Work Mem: {bytesize_to_hr(work_mem / managed_cache['hash_mem_multiplier'])}
            -> Hash Mem Multiplier: {managed_cache['hash_mem_multiplier']}
        + ALL: {total_working_memory * num_user_conns / usable_ram_noswap * 100:.2f} (%)
        + Parallel Workers: 
            -> Gather Workers: {managed_cache['max_parallel_workers_per_gather']}
            -> Worker in Pool: {managed_cache['max_parallel_workers']}
            -> Workers Process: {managed_cache['max_worker_processes']}
    - Work mem Scale Factor: {_kwargs.work_mem_scale_factor} -> Followed the normal calculation: {_kwargs.work_mem_scale_factor == 1.0}
    - Effective Cache Size: {bytesize_to_hr(effective_cache_size)} or {effective_cache_size / usable_ram_noswap * 100:.2f} (%)
 
Reports Summary (others):
------------------------------------------ 
    - Maintenance and (Auto-)Vacuum:
        + Autovacuum Work Mem: {managed_cache['autovacuum_work_mem']} --> Maintenance Work Mem: {bytesize_to_hr(managed_cache['maintenance_work_mem'])}
        + Autovacuum Max Workers: {managed_cache['autovacuum_max_workers']}
        + Threshold and Scale Factor:
            -> Vacuum: {managed_cache['autovacuum_vacuum_scale_factor'] * 100} (%) and {managed_cache['autovacuum_vacuum_threshold']} changed tuples
            -> Analyze: {managed_cache['autovacuum_analyze_scale_factor'] * 100} (%) and {managed_cache['autovacuum_analyze_threshold']} changed tuples
            -> Insert: {managed_cache['autovacuum_vacuum_insert_scale_factor'] * 100} (%) and {managed_cache['autovacuum_vacuum_insert_threshold']} changed tuples
        + Parallelism:
            -> Maintenance Workers: {managed_cache['max_parallel_maintenance_workers']}
            -> Table Scan Size: {bytesize_to_hr(managed_cache['min_parallel_table_scan_size'])}
            -> Index Scan Size: {bytesize_to_hr(managed_cache['min_parallel_index_scan_size'])}
        + Autovacuum Cost and Delay: {managed_cache['autovacuum_vacuum_cost_limit']} and {managed_cache['autovacuum_vacuum_cost_delay']}
        + Vacuum Cost and Delay: {managed_cache['vacuum_cost_limit']} and {managed_cache['vacuum_cost_delay']} 
        + Page Cost Relative Factor :: Hit={managed_cache['vacuum_cost_page_hit']} :: Miss={managed_cache['vacuum_cost_page_miss']} :: Dirty/Disk={managed_cache['vacuum_cost_page_dirty']}
    - Background Writers:
        + Delay in Milli-seconds (ms): {managed_cache['bgwriter_delay']} with {managed_cache['bgwriter_lru_maxpages']} max pages
        -> Throughput (MB/s) in Random IOPs of Data Disk Required: {bytesize_to_hr(managed_cache['bgwriter_lru_maxpages'] * (Mi // (8 * Ki)) * (K10 / managed_cache['bgwriter_lru_multiplier']))}
    - Query Planning and Optimization:
        + Page Cost :: Sequential={managed_cache['seq_page_cost']:.2f} :: Random={managed_cache['random_page_cost']:.2f}
        + CPU Cost :: Tuple={managed_cache['cpu_tuple_cost']:.4f} :: Index={managed_cache['cpu_index_tuple_cost']:.4f} :: Operator={managed_cache['cpu_operator_cost']:.4f}
        + Bitmap Heap :: Workload={managed_cache['effective_io_concurrency']:} :: Maintenance={managed_cache['maintenance_io_concurrency']:}
        + Parallelism :: Setup={managed_cache['parallel_setup_cost']} :: Tuple={managed_cache['parallel_tuple_cost']:.2f}
    - Checkpoint Timeout: {managed_cache['checkpoint_timeout']} seconds with Checkpoint Completion Target: {managed_cache['checkpoint_completion_target']}    
    - Commit Delay: {managed_cache['commit_delay']}
    - Write-Ahead Logging and Data Integrity:
        + WAL Level: {managed_cache['wal_level']} with {managed_cache['wal_compression']} compression algorithm 
        + WAL Segment Size (1 file): {bytesize_to_hr(_kwargs.wal_segment_size)}
        + Integrity: 
            * Synchronous Commit: {managed_cache['synchronous_commit']}
            * Full Page Writes: {managed_cache['full_page_writes']}
            * Fsync: {managed_cache['fsync']}
        + Buffers Write Cycle within Data Loss Time: {options.max_time_transaction_loss_allow_in_millisecond} ms (depend on WAL volume throughput)
            * 1.0x when opt_wal_buffers={PG_PROFILE_OPTMODE.SPIDEY}:
                -> Elapsed Time :: Rotate: {wal10['rotate_time']:.2f} ms :: Write: {wal10['write_time']:.2f} ms :: Delay: {wal10['delay_time']:.2f} ms
                -> Total Time :: {wal10['total_time']:.2f} ms during {wal10['num_wal_files']} WAL files
            * 1.5x when opt_wal_buffers={PG_PROFILE_OPTMODE.OPTIMUS_PRIME}:
                -> Elapsed Time :: Rotate {wal15['rotate_time']:.2f} ms :: Write: {wal15['write_time']:.2f} ms :: Delay: {wal15['delay_time']:.2f} ms
                -> Total Time :: {wal15['total_time']:.2f} ms during {wal15['num_wal_files']} WAL files
            * 2.0x when opt_wal_buffers={PG_PROFILE_OPTMODE.PRIMORDIAL}:
                -> Elapsed Time :: Rotate {wal20['rotate_time']:.2f} ms :: Write: {wal20['write_time']:.2f} ms :: Delay: {wal20['delay_time']:.2f} ms
                -> Total Time :: {wal20['total_time']:.2f} ms during {wal20['num_wal_files']} WAL files
        + WAL Sizing: 
            * Max WAL Size for Automatic Checkpoint: {bytesize_to_hr(managed_cache['max_wal_size'])} or {managed_cache['max_wal_size'] / options.wal_spec.disk_usable_size * 100:.2f} (%)
            * Min WAL Size for WAL recycle instead of removal: {bytesize_to_hr(managed_cache['min_wal_size'])} 
                -> Disk usage must below {(1 - managed_cache['min_wal_size'] / options.wal_spec.disk_usable_size) * 100:.1f} (%)
            * WAL Keep Size for PITR/Replication: {bytesize_to_hr(managed_cache['wal_keep_size'])} or minimum {managed_cache['wal_keep_size'] / options.wal_spec.disk_usable_size * 100:.2f} (%)  
    - Timeout:
        + Idle-in-Transaction Session Timeout: {managed_cache['idle_in_transaction_session_timeout']} seconds
        + Statement Timeout: {managed_cache['statement_timeout']} seconds
        + Lock Timeout: {managed_cache['lock_timeout']} seconds
        + Deadlock Timeout: {managed_cache['deadlock_timeout']} seconds

Sufficiently Safe for Production: {max_total_memory_used / usable_ram_noswap <= 0.85} (85 % memory usage is threshold)
Optimized Safe for Production: {max_total_memory_used / usable_ram_noswap <= 0.75} (75 % memory usage is threshold)
Normal Memory Usage: {max_total_memory_used / usable_ram_noswap <= _kwargs.max_normal_memory_usage + 2 * _kwargs.mem_pool_epsilon_to_rollback} ({_kwargs.max_normal_memory_usage * 100:.1f} % memory usage is threshold)

WARNING: These calculations could be incorrect due to capping, precision adjustment, rounding.
# ============================================================================================
'''
        if not ignore_report:
            _logger.info(_report)
        return _report, max_total_memory_used
