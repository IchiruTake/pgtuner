import logging
from collections import defaultdict
from math import ceil
from typing import Any, Literal
from functools import partial

from pydantic import BaseModel, Field

from src.static.vars import APP_NAME_UPPER, Gi, Mi, Ki, K10
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.items import PG_TUNE_ITEM
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.profile.database.shared import wal_time, checkpoint_time, vacuum_time, vacuum_scale
from src.utils.avg import pow_avg
from src.utils.pydantic_utils import bytesize_to_hr

__all__ = ['PG_TUNE_REQUEST', 'PG_TUNE_RESPONSE']

from src.utils.timing import time_decorator

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
            content.append(f'## ===== SCOPE: {scope} ===== \n')
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

    @time_decorator
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

    # @time_decorator
    def mem_test(self, options: PG_TUNE_USR_OPTIONS, use_full_connection: bool = False,
                 ignore_report: bool = True, skip_logger: bool = False) -> tuple[str, int | float]:
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
        os_conn_overhead = (max_user_conns * _kwargs.single_memory_connection_overhead *
                            _kwargs.memory_connection_to_dedicated_os_ratio)
        num_user_conns = max_user_conns
        if not use_full_connection:
            num_user_conns = ceil(max_user_conns * _kwargs.effective_connection_ratio)

        # Shared Buffers and WAL buffers
        shared_buffers = managed_cache['shared_buffers']
        wal_buffers = managed_cache['wal_buffers']

        # Temp Buffers and Work Mem
        temp_buffers = managed_cache['temp_buffers']
        work_mem = managed_cache['work_mem']
        hash_mem_multiplier = managed_cache['hash_mem_multiplier']

        # Higher level would assume more hash-based operations, which reduce the work_mem in correction-tuning phase
        # Smaller level would assume less hash-based operations, which increase the work_mem in correction-tuning phase
        # real_world_work_mem = work_mem * hash_mem_multiplier
        real_world_mem_scale = pow_avg(1, hash_mem_multiplier, level=_kwargs.hash_mem_usage_level)
        real_world_work_mem = work_mem * real_world_mem_scale
        total_working_memory = (temp_buffers + real_world_work_mem)
        total_working_memory_hr = bytesize_to_hr(total_working_memory)

        max_total_memory_used = shared_buffers + wal_buffers + os_conn_overhead
        max_total_memory_used += total_working_memory * num_user_conns
        max_total_memory_used_ratio = max_total_memory_used / usable_ram_noswap
        max_total_memory_used_hr = bytesize_to_hr(max_total_memory_used)

        if ignore_report and not _kwargs.mem_pool_parallel_estimate:
            return '', max_total_memory_used

        # Work Mem but in Parallel
        num_parallel_workers = min(managed_cache['max_parallel_workers'], managed_cache['max_worker_processes'])
        num_sessions, remain_workers = divmod(num_parallel_workers, managed_cache['max_parallel_workers_per_gather'])
        num_sessions_in_parallel = num_sessions + (1 if remain_workers > 0 else 0)
        parallel_work_mem_total: int = real_world_work_mem * (num_parallel_workers + num_sessions_in_parallel)
        parallel_work_mem_in_session = real_world_work_mem * (1 + managed_cache['max_parallel_workers_per_gather'])

        # Ensure the number of active user connections always larger than the num_sessions
        # The maximum 0 here is meant that all connections can have full parallelism
        num_sessions_not_in_parallel = max(0, num_user_conns - num_sessions_in_parallel)
        single_work_mem_total = real_world_work_mem * num_sessions_not_in_parallel

        max_total_memory_used_with_parallel = shared_buffers + wal_buffers + os_conn_overhead
        max_total_memory_used_with_parallel += (parallel_work_mem_total + single_work_mem_total)
        max_total_memory_used_with_parallel += temp_buffers * (num_sessions_in_parallel + num_sessions_not_in_parallel)
        max_total_memory_used_with_parallel_ratio = max_total_memory_used_with_parallel / usable_ram_noswap
        max_total_memory_used_with_parallel_hr = bytesize_to_hr(max_total_memory_used_with_parallel)
        _epsilon_scale = 4 if use_full_connection else 2

        if ignore_report and _kwargs.mem_pool_parallel_estimate:
            return '', max_total_memory_used_with_parallel

        # Effective Cache Size
        effective_cache_size = managed_cache['effective_cache_size']

        # WAL Times
        wal_throughput = options.wal_spec.raid_perf()[0]
        wal_time_partial = partial(wal_time, wal_buffers=wal_buffers, wal_segment_size=_kwargs.wal_segment_size,
                                   wal_writer_delay_in_ms=managed_cache['wal_writer_delay'],
                                   wal_throughput=wal_throughput)
        wal10 = wal_time_partial(data_amount_ratio=1.0)
        wal15 = wal_time_partial(data_amount_ratio=1.5)
        wal20 = wal_time_partial(data_amount_ratio=2.0)

        # Vacuum and Maintenance
        real_autovacuum_work_mem = managed_cache['autovacuum_work_mem']
        if real_autovacuum_work_mem == -1:
            real_autovacuum_work_mem = managed_cache['maintenance_work_mem']
        if options.versioning()[0] < 17:
            # The VACUUM use adaptive radix tree which performs better and not being silently capped at 1 GiB
            # since PostgreSQL 17+
            # https://www.postgresql.org/docs/17/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM
            # and https://www.postgresql.org/docs/16/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM
            real_autovacuum_work_mem = min(1 * Gi, real_autovacuum_work_mem)

        # Checkpoint Timing
        data_iops = options.data_index_spec.raid_perf()[1]
        checkpoint_timeout = managed_cache['checkpoint_timeout']
        checkpoint_completion_target = managed_cache['checkpoint_completion_target']
        checkpoint_time_partial = partial(checkpoint_time, checkpoint_timeout_second=checkpoint_timeout,
                                          checkpoint_completion_target=checkpoint_completion_target,
                                          wal_disk_tput=options.wal_spec.raid_perf()[0],
                                          data_disk_iops=data_iops, wal_buffers=wal_buffers,
                                          wal_segment_size=_kwargs.wal_segment_size)
        ckpt01 = checkpoint_time_partial(data_amount_ratio=_kwargs.wal_segment_size / wal_buffers)  # 1 WAL buffers
        ckpt50 = checkpoint_time_partial(data_amount_ratio=5.0)
        ckpt500 = checkpoint_time_partial(data_amount_ratio=50.0)
        ckpt2500 = checkpoint_time_partial(data_amount_ratio=250.0)
        ckpt10k = checkpoint_time_partial(data_amount_ratio=1000.0)

        # Background Writers
        bgwriter_page_per_second = ceil(managed_cache['bgwriter_lru_maxpages'] * (K10 / managed_cache['bgwriter_delay']))
        bgwriter_throughput = PG_DISK_PERF.iops_to_throughput(bgwriter_page_per_second)

        # Auto-vacuum and Maintenance Calculator
        vacuum_report = vacuum_time(hit_cost=managed_cache['vacuum_cost_page_hit'],
                                    miss_cost=managed_cache['vacuum_cost_page_miss'],
                                    dirty_cost=managed_cache['vacuum_cost_page_dirty'],
                                    delay_ms=managed_cache['autovacuum_vacuum_cost_delay'],
                                    cost_limit=managed_cache['vacuum_cost_limit'],
                                    data_disk_iops=data_iops)
        normal_vacuum = vacuum_scale(managed_cache['autovacuum_vacuum_threshold'],
                                     managed_cache['autovacuum_vacuum_scale_factor'])
        normal_analyze = vacuum_scale(managed_cache['autovacuum_analyze_threshold'],
                                      managed_cache['autovacuum_analyze_scale_factor'])

        # See the PostgreSQL source code of how they sample randomly to get statistics
        _sampling_rows = 300 * managed_cache['default_statistics_target']

        # Anti-wraparound Vacuum
        # Transaction ID
        min_hr_txid = managed_cache['vacuum_freeze_min_age'] / _kwargs.num_write_transaction_per_hour_on_workload
        norm_hr_txid = managed_cache['vacuum_freeze_table_age'] / _kwargs.num_write_transaction_per_hour_on_workload
        max_hr_txid = managed_cache['autovacuum_freeze_max_age'] / _kwargs.num_write_transaction_per_hour_on_workload

        # Row Locking in Transaction
        min_hr_row_lock = managed_cache['vacuum_multixact_freeze_min_age'] / _kwargs.num_write_transaction_per_hour_on_workload
        norm_hr_row_lock = managed_cache['vacuum_multixact_freeze_table_age'] / _kwargs.num_write_transaction_per_hour_on_workload
        max_hr_row_lock = managed_cache['autovacuum_multixact_freeze_max_age'] / _kwargs.num_write_transaction_per_hour_on_workload

        _report = f'''
# ===============================================================
# Memory Estimation Test by {APP_NAME_UPPER}
From server-side, the PostgreSQL memory usable arena is at most {usable_ram_noswap_hr} or {usable_ram_noswap_ratio * 100:.2f} (%) of the total RAM ({bytesize_to_hr(ram_noswap)}).
All other variables must be bounded and computed within the available memory. 
CPU: {options.vcpu} logical cores
RAM: {ram_noswap_hr} or ratio: ({(ram_noswap / options.vcpu / Gi):.1f}).

Arguments: use_full_connection={use_full_connection}
Report Summary (memory, over usable RAM):
----------------------------------------
* PostgreSQL memory (estimate): {max_total_memory_used_hr} or {max_total_memory_used_ratio * 100:.2f} (%) over usable RAM.
    - The Shared Buffers is {bytesize_to_hr(shared_buffers)} or {shared_buffers / usable_ram_noswap * 100:.2f} (%)
    - The Wal Buffers is {bytesize_to_hr(wal_buffers)} or {wal_buffers / usable_ram_noswap * 100:.2f} (%)
    - The connection overhead is {bytesize_to_hr(os_conn_overhead)} with {num_user_conns} total user connections
        + Active user connections: {max_user_conns}
        + Peak assumption is at {bytesize_to_hr(os_conn_overhead / _kwargs.memory_connection_to_dedicated_os_ratio)}
        + Reserved & Superuser Reserved Connections: {managed_cache['max_connections'] - max_user_conns}
        + Need Connection Pool such as PgBouncer: {num_user_conns >= 100}
    - The total maximum working memory (assuming with one full use of work_mem and temp_buffers):
        + SINGLE: {total_working_memory_hr} per user connections or {total_working_memory / usable_ram_noswap * 100:.2f} (%)
            -> Real-World Mem Scale: {_kwargs.temp_buffers_ratio + (1 - _kwargs.temp_buffers_ratio) * real_world_mem_scale} 
            -> Temp Buffers: {bytesize_to_hr(temp_buffers)} :: Work Mem: {bytesize_to_hr(work_mem)}
            -> Hash Mem Multiplier: {hash_mem_multiplier} ::  Real-World Work Mem: {bytesize_to_hr(real_world_work_mem)}
            -> Total: {total_working_memory * num_user_conns / usable_ram_noswap * 100:.2f} (%)
        + PARALLEL: 
            -> Workers :: Gather Workers={managed_cache['max_parallel_workers_per_gather']} :: Worker in Pool={managed_cache['max_parallel_workers']} << Workers Process={managed_cache['max_worker_processes']} 
            -> Parallelized Session: {num_sessions_in_parallel} :: Non-parallelized Session: {num_sessions_not_in_parallel}
            -> Work memory assuming single query (1x work_mem)
                * Total parallelized sessions = {num_sessions} with {num_sessions_in_parallel - num_sessions} leftover session
                * Maximum work memory in parallelized session(s) without temp_buffers :
                    - 1 parallelized session: {bytesize_to_hr(parallel_work_mem_in_session)} or {parallel_work_mem_in_session / usable_ram_noswap * 100:.2f} (%)
                    - Total (in parallel): {bytesize_to_hr(parallel_work_mem_total)} or {parallel_work_mem_total / usable_ram_noswap * 100:.2f} (%)
                    - Total (in single): {bytesize_to_hr(single_work_mem_total)} or {single_work_mem_total / usable_ram_noswap * 100:.2f} (%)
                * Maximum work memory in parallelized session(s) with temp_buffers:
                    - 1 parallelized session: {bytesize_to_hr(parallel_work_mem_in_session + temp_buffers)} or {(parallel_work_mem_in_session + temp_buffers) / usable_ram_noswap * 100:.2f} (%)
                    - Total (in parallel): {bytesize_to_hr(parallel_work_mem_total + temp_buffers * num_sessions_in_parallel)} or {(parallel_work_mem_total + temp_buffers * num_sessions_in_parallel) / usable_ram_noswap * 100:.2f} (%)
                    - Total (in single): {bytesize_to_hr(single_work_mem_total + temp_buffers * num_sessions_not_in_parallel)} or {(single_work_mem_total + temp_buffers * num_sessions_not_in_parallel) / usable_ram_noswap * 100:.2f} (%)
    - Effective Cache Size: {bytesize_to_hr(effective_cache_size)} or {effective_cache_size / usable_ram_noswap * 100:.2f} (%)

* Zero parallelized session >> Memory in use: {max_total_memory_used_hr}
    - Memory Ratio: {max_total_memory_used_ratio * 100:.2f} (%)
    - Normal Memory Usage: {max_total_memory_used_ratio <= min(1.0, _kwargs.max_normal_memory_usage + _epsilon_scale * _kwargs.mem_pool_epsilon_to_rollback)} ({_kwargs.max_normal_memory_usage * 100:.1f} % memory threshold)
    - P3: Generally Safe in Workload: {max_total_memory_used_ratio <= 0.70} (70 % memory threshold)
    - P2: Sufficiently Safe for Production: {max_total_memory_used_ratio <= 0.80} (80 % memory threshold)
    - P1: Risky for Production: {max_total_memory_used_ratio <= 0.90} (90 % memory threshold)
* With parallelized session >> Memory in use: {max_total_memory_used_with_parallel_hr}
    - Memory Ratio: {max_total_memory_used_with_parallel_ratio * 100:.2f} (%)
    - Normal Memory Usage: {max_total_memory_used_with_parallel_ratio <= min(1.0, _kwargs.max_normal_memory_usage + _epsilon_scale * _kwargs.mem_pool_epsilon_to_rollback)} ({_kwargs.max_normal_memory_usage * 100:.1f} % memory threshold)
    - P3: Generally Safe in Workload: {max_total_memory_used_with_parallel_ratio <= 0.70} (70 % memory threshold)
    - P2: Sufficiently Safe for Production: {max_total_memory_used_with_parallel_ratio <= 0.80} (80 % memory threshold)
    - P1: Risky for Production: {max_total_memory_used_with_parallel_ratio <= 0.90} (90 % memory threshold)

Report Summary (others):
----------------------- 
* Maintenance and (Auto-)Vacuum:
    - Autovacuum working memory (by definition): {managed_cache['autovacuum_work_mem']} --> Maintenance Work Mem: {bytesize_to_hr(managed_cache['maintenance_work_mem'])}
        + Autovacuum working memory on 1 worker: {bytesize_to_hr(real_autovacuum_work_mem)}
        + Autovacuum max workers: {managed_cache['autovacuum_max_workers']}
        + Autovacuum total memory: {bytesize_to_hr(real_autovacuum_work_mem * managed_cache['autovacuum_max_workers'])} or {real_autovacuum_work_mem * managed_cache['autovacuum_max_workers'] / usable_ram_noswap * 100:.2f} (%)
        + Parallelism:
            -> Maintenance workers: {managed_cache['max_parallel_maintenance_workers']}
            -> Maintenance total memory: {bytesize_to_hr(managed_cache['maintenance_work_mem'] * managed_cache['max_parallel_maintenance_workers'])} or {managed_cache['maintenance_work_mem'] * managed_cache['max_parallel_maintenance_workers'] / usable_ram_noswap * 100:.2f} (%)
            -> Parallel table scan size: {bytesize_to_hr(managed_cache['min_parallel_table_scan_size'])}
            -> Parallel index scan size: {bytesize_to_hr(managed_cache['min_parallel_index_scan_size'])}
    - Normal Vacuum at Table Size:
        + Threshold and Scale Factor for Normal Vacuum:
            -> Vacuum  :: Scale Factor={managed_cache['autovacuum_vacuum_scale_factor'] * 100} (%) :: Threshold={managed_cache['autovacuum_vacuum_threshold']}
            -> Analyze :: Scale Factor={managed_cache['autovacuum_analyze_scale_factor'] * 100} (%) :: Threshold={managed_cache['autovacuum_analyze_threshold']}
            -> Insert  :: Scale Factor={managed_cache['autovacuum_vacuum_insert_scale_factor'] * 100} (%) :: Threshold={managed_cache['autovacuum_vacuum_insert_threshold']}
            Report when number of dead tuples is reached:
            -> 10K rows :: Vacuum={normal_vacuum['10k']} :: Insert/Analyze={normal_analyze['10k']}
            -> 300K rows :: Vacuum={normal_vacuum['300k']} :: Insert/Analyze={normal_analyze['300k']}
            -> 5M rows :: Vacuum={normal_vacuum['5m']} :: Insert/Analyze={normal_analyze['5m']}
            -> 25M rows :: Vacuum={normal_vacuum['25m']} :: Insert/Analyze={normal_analyze['25m']}
            -> 400M rows :: Vacuum={normal_vacuum['400m']} :: Insert/Analyze={normal_analyze['400m']}
            -> 1B rows :: Vacuum={normal_vacuum['1b']} :: Insert/Analyze={normal_analyze['1b']}
    - Normal Vacuum Strength:
        + Page Cost Relative Factor :: Hit={managed_cache['vacuum_cost_page_hit']} :: Miss={managed_cache['vacuum_cost_page_miss']} :: Dirty/Disk={managed_cache['vacuum_cost_page_dirty']}
        + Autovacuum cost: {managed_cache['autovacuum_vacuum_cost_limit']} --> Vacuum cost: {managed_cache['vacuum_cost_limit']}
        + Autovacuum delay: {managed_cache['autovacuum_vacuum_cost_delay']} (ms) --> Vacuum delay: {managed_cache['vacuum_cost_delay']} (ms)
        + Vacuum Report on Worst Case Scenario:
            -> Hit (page in shared_buffers): Maximum {vacuum_report['max_num_hit_page']} pages or RAM throughput {vacuum_report['max_hit_data']:.2f} MiB/s 
                RAM Safety: {vacuum_report['max_hit_data'] < 10 * K10} (< 10 GiB/s for low DDR3)
            -> Miss (page in disk cache): Maximum {vacuum_report['max_num_miss_page']} pages or Disk throughput {vacuum_report['max_miss_data']:.2f} MiB/s
                RAM Safety: {vacuum_report['max_miss_data'] < 5 * K10} (< 5 GiB/s for low DDR3)
                Disk Safety: {vacuum_report['max_miss_data'] < data_iops} (< Data Disk IOPS)
            -> Dirty (page in data disk volume): Maximum {vacuum_report['max_num_dirty_page']} pages or Disk throughput {vacuum_report['max_dirty_data']:.2f} MiB/s
                Disk Safety: {vacuum_report['max_dirty_data'] < data_iops} (< Data Disk IOPS)
        + Other Scenarios with H:M:D ratio as 5:5:1 (frequent), or 1:1:1 (rarely)
            5:5:1 or {vacuum_report['5:5:1_page'] * 6} disk pages -> IOPS capacity of {vacuum_report['5:5:1_data']:.2f} MiB/s (write={vacuum_report['5:5:1_data'] * 1 / 6:.2f} MiB/s)
            1:1:1 or {vacuum_report['1:1:1_page'] * 3} disk pages -> IOPS capacity of {vacuum_report['1:1:1_data']:.2f} MiB/s (write={vacuum_report['1:1:1_data'] * 1 / 2:.2f} MiB/s)
    - Transaction ID Wraparound and Anti-Wraparound Vacuum:
        + Workload Write Transaction per Hour: {_kwargs.num_write_transaction_per_hour_on_workload}
        + TXID Vacuum :: Minimum={min_hr_txid:.2f} hrs :: Manual={norm_hr_txid:.2f} hrs :: Auto-forced={max_hr_txid:.2f} hrs
        + XMIN,XMAX Vacuum :: Minimum={min_hr_row_lock:.2f} hrs :: Manual={norm_hr_row_lock:.2f} hrs :: Auto-forced={max_hr_row_lock:.2f} hrs     
        
* Background Writers:
    - Delay: {managed_cache['bgwriter_delay']} (ms) for maximum {managed_cache['bgwriter_lru_maxpages']} dirty pages
        + {bgwriter_page_per_second} pages per second or {bgwriter_throughput} MiB/s in random WRITE IOPs

* Query Planning and Optimization:
    - Page Cost :: Sequential={managed_cache['seq_page_cost']:.2f} :: Random={managed_cache['random_page_cost']:.2f}
    - CPU Cost :: Tuple={managed_cache['cpu_tuple_cost']:.4f} :: Index={managed_cache['cpu_index_tuple_cost']:.4f} :: Operator={managed_cache['cpu_operator_cost']:.4f}
    - Bitmap Heap Planning :: Workload={managed_cache['effective_io_concurrency']:} :: Maintenance={managed_cache['maintenance_io_concurrency']:}
    - Parallelism :: Setup={managed_cache['parallel_setup_cost']} :: Tuple={managed_cache['parallel_tuple_cost']:.2f}
    - Batched Commit Delay: {managed_cache['commit_delay']} (ms)
    - Checkpoint: 
        + Effective Timeout: {checkpoint_timeout * checkpoint_completion_target:.1f} seconds ({checkpoint_timeout}::{checkpoint_completion_target})
        + Analyze Checkpoint Time (ensure the checkpoint can be written within the timeout and ignore dirty buffers on-the-go):
            -> 1 WAL file:
                * Data Amount: {bytesize_to_hr(ckpt01['data_amount'])} :: {ckpt01['page_amount']} pages :: {ckpt01['wal_amount']} WAL files
                * Expected Time:
                    - READ: {ckpt01['wal_read_time']} seconds with {ckpt01['wal_disk_utilization'] * 100:.2f} (%) utilization
                    - WRITE: {ckpt01['data_write_time']} seconds with {ckpt01['data_disk_utilization'] * 100:.2f} (%) utilization
                * Safe Test :: Time-based Check <- {ckpt01['data_write_time'] + ckpt01['wal_read_time'] <= checkpoint_timeout * checkpoint_completion_target}            
            -> 5.0x WAL Buffers (General):
                * Data Amount: {bytesize_to_hr(ckpt50['data_amount'])} :: {ckpt50['page_amount']} pages :: {ckpt50['wal_amount']} WAL files
                * Expected Time:
                    - READ: {ckpt50['wal_read_time']} seconds with {ckpt50['wal_disk_utilization'] * 100:.2f} (%) utilization
                    - WRITE: {ckpt50['data_write_time']} seconds with {ckpt50['data_disk_utilization'] * 100:.2f} (%) utilization
                * Safe Test :: Time-based Check <- {ckpt50['data_write_time'] + ckpt50['wal_read_time'] <= checkpoint_timeout * checkpoint_completion_target}
            -> 50.0x WAL Buffers (Heavy):
                * Data Amount: {bytesize_to_hr(ckpt500['data_amount'])} :: {ckpt500['page_amount']} pages :: {ckpt500['wal_amount']} WAL files
                * Expected Time:
                    - READ: {ckpt500['wal_read_time']} seconds with {ckpt500['wal_disk_utilization'] * 100:.2f} (%) utilization
                    - WRITE: {ckpt500['data_write_time']} seconds with {ckpt500['data_disk_utilization'] * 100:.2f} (%) utilization
                * Safe Test :: Time-based Check <- {ckpt500['data_write_time'] + ckpt500['wal_read_time'] <= checkpoint_timeout * checkpoint_completion_target}
            -> 250.0x WAL Buffers (Extreme):
                * Data Amount: {bytesize_to_hr(ckpt2500['data_amount'])} :: {ckpt2500['page_amount']} pages :: {ckpt2500['wal_amount']} WAL files
                * Expected Time:
                    - READ: {ckpt2500['wal_read_time']} seconds with {ckpt2500['wal_disk_utilization'] * 100:.2f} (%) utilization
                    - WRITE: {ckpt2500['data_write_time']} seconds with {ckpt2500['data_disk_utilization'] * 100:.2f} (%) utilization
                * Safe Test :: Time-based Check <- {ckpt2500['data_write_time'] + ckpt2500['wal_read_time'] <= checkpoint_timeout * checkpoint_completion_target}
            -> 1000.0x WAL Buffers (Crazy to Insane):
                * Data Amount: {bytesize_to_hr(ckpt10k['data_amount'])} :: {ckpt10k['page_amount']} pages :: {ckpt10k['wal_amount']} WAL files
                * Expected Time:
                    - READ: {ckpt10k['wal_read_time']} seconds with {ckpt10k['wal_disk_utilization'] * 100:.2f} (%) utilization
                    - WRITE: {ckpt10k['data_write_time']} seconds with {ckpt10k['data_disk_utilization'] * 100:.2f} (%) utilization
                * Safe Test :: Time-based Check <- {ckpt10k['data_write_time'] + ckpt10k['wal_read_time'] <= checkpoint_timeout * checkpoint_completion_target}
                
* Write-Ahead Logging and Data Integrity:
    - WAL Level: {managed_cache['wal_level']} with {managed_cache['wal_compression']} compression algorithm 
    - WAL Segment Size (1 file): {bytesize_to_hr(_kwargs.wal_segment_size)}
    - Integrity: 
        + Synchronous Commit: {managed_cache['synchronous_commit']}
        + Full Page Writes: {managed_cache['full_page_writes']}
        + Fsync: {managed_cache['fsync']}
    - Buffers Write Cycle within Data Loss Time: {options.max_time_transaction_loss_allow_in_millisecond} ms (depend on WAL volume throughput)
        + 1.0x when opt_wal_buffers={PG_PROFILE_OPTMODE.SPIDEY}:
            -> Elapsed Time :: Rotate: {wal10['rotate_time']:.2f} ms :: Write: {wal10['write_time']:.2f} ms :: Delay: {wal10['delay_time']:.2f} ms
            -> Total Time :: {wal10['total_time']:.2f} ms during {wal10['num_wal_files']} WAL files
            -> OK for Transaction Loss: {wal10['total_time'] <= options.max_time_transaction_loss_allow_in_millisecond}
        + 1.5x when opt_wal_buffers={PG_PROFILE_OPTMODE.OPTIMUS_PRIME}:
            -> Elapsed Time :: Rotate: {wal15['rotate_time']:.2f} ms :: Write: {wal15['write_time']:.2f} ms :: Delay: {wal15['delay_time']:.2f} ms
            -> Total Time :: {wal15['total_time']:.2f} ms during {wal15['num_wal_files']} WAL files
            -> OK for Transaction Loss: {wal15['total_time'] <= options.max_time_transaction_loss_allow_in_millisecond}
        + 2.0x when opt_wal_buffers={PG_PROFILE_OPTMODE.PRIMORDIAL}:
            -> Elapsed Time :: Rotate: {wal20['rotate_time']:.2f} ms :: Write: {wal20['write_time']:.2f} ms :: Delay: {wal20['delay_time']:.2f} ms
            -> Total Time :: {wal20['total_time']:.2f} ms during {wal20['num_wal_files']} WAL files
            -> OK for Transaction Loss: {wal20['total_time'] <= options.max_time_transaction_loss_allow_in_millisecond}
    - WAL Sizing: 
        + Max WAL Size for Automatic Checkpoint: {bytesize_to_hr(managed_cache['max_wal_size'])} or {managed_cache['max_wal_size'] / options.wal_spec.disk_usable_size * 100:.2f} (%)
        + Min WAL Size for WAL recycle instead of removal: {bytesize_to_hr(managed_cache['min_wal_size'])} 
            -> Disk usage must below {(1 - managed_cache['min_wal_size'] / options.wal_spec.disk_usable_size) * 100:.1f} (%)
        + WAL Keep Size for PITR/Replication: {bytesize_to_hr(managed_cache['wal_keep_size'])} or minimum {managed_cache['wal_keep_size'] / options.wal_spec.disk_usable_size * 100:.2f} (%)  

* Timeout:
    - Idle-in-Transaction Session Timeout: {managed_cache['idle_in_transaction_session_timeout']} seconds
    - Statement Timeout: {managed_cache['statement_timeout']} seconds
    - Lock Timeout: {managed_cache['lock_timeout']} seconds

WARNING (if any) and DISCLAIMER:
------------------------------------------
* These calculations could be incorrect due to capping, precision adjustment, rounding; and it is 
just the estimation. Please take proper consultant and testing to verify the actual memory usage, 
and bottleneck between processes.
* The working memory whilst the most critical part are in the assumption of **basic** full usage 
(one single HASH-based query and one CTE) and all connections are in the same state. It is best 
to test it under your **real** production business workload rather than this estimation report.
* For the autovacuum threshold, it is best to adjust it based on the actual table size, its 
active portion compared to the total size and its time, and the actual update/delete/insert 
rate to avoid bloat rather than using our above setting; but for general use, the current 
default is OK unless you are working on table with billion of rows or more.    
* Update the timeout based on your business requirement, database workload, and the 
application's behavior.
* Not every parameter can be covered or tuned, and not every parameter can be added as-is.
As mentioned, consult with your developer, DBA, and system administrator to ensure the
best performance and reliability of the database system.

# ===============================================================
'''

        if not skip_logger:
            _logger.info(_report)
        return _report, (max_total_memory_used if not _kwargs.mem_pool_parallel_estimate else
                         max_total_memory_used_with_parallel)

    def calc_worker_in_parallel(self, options: PG_TUNE_USR_OPTIONS, use_full_connection: bool = False) -> dict[str, int]:
        managed_cache = self.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG)
        _kwargs = options.tuning_kwargs

        # Number of Connections
        max_user_conns = (managed_cache['max_connections'] - managed_cache['superuser_reserved_connections'] -
                          managed_cache['reserved_connections'])
        active_user_conns = ceil(max_user_conns * _kwargs.effective_connection_ratio)
        num_user_conns = (max_user_conns if use_full_connection else active_user_conns)

        # Calculate the number of parallel workers
        num_parallel_workers = min(managed_cache['max_parallel_workers'], managed_cache['max_worker_processes'])

        # How many sessions can be in parallel
        num_sessions, remain_workers = divmod(num_parallel_workers, managed_cache['max_parallel_workers_per_gather'])
        num_sessions_in_parallel = num_sessions + (1 if remain_workers > 0 else 0)

        # Ensure the number of active user connections always larger than the num_sessions
        # The maximum 0 here is meant that all connections can have full parallelism
        num_sessions_not_in_parallel = max(0, num_user_conns - num_sessions_in_parallel)

        return {
            'num_user_conns': num_user_conns,
            'num_parallel_workers': num_parallel_workers,
            'num_sessions': num_sessions,
            'num_sessions_in_parallel': num_sessions_in_parallel,
            'num_sessions_not_in_parallel': num_sessions_not_in_parallel,
            'parallel_scale': (num_parallel_workers + num_sessions_in_parallel) / num_user_conns
        }

