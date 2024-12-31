"""
This module is to perform specific tuning on the PostgreSQL database server.

** WORKLOAD TUNING **
Triggering Parameters:
    workload_type: The PostgreSQL workload type.
    opt_memory: The PostgreSQL memory tuning mode.

Impacted Parameters:
    PG_SCOPE.CONNECTION:
        - max_connections: The maximum number of client connections allowed.

    PG_SCOPE.MEMORY:
        - shared_buffers: The amount of memory the database server uses for shared memory buffers.
        - temp_buffers: The maximum number of temporary buffers used by each database session.
        - work_mem: The amount of memory to be used by internal sort operations and hash tables before writing to disk.
        - effective_cache_size: The estimate of how much memory is available for disk caching by the operating system.

** LOGGING TUNING **
Triggering Parameters:
    opt_logging: The PostgreSQL logging tuning mode.
    db_log_spec: The disk used for database logging specification.

Impacted Parameters:
    PG_SCOPE.LOGGING:
        - logging_collector: Default to 'on' by official PostgreSQL documentation
        - log_destination: Default to 'stderr' by official PostgreSQL documentation
        - log_directory: Default to 'log' (or $PGDATA/log) by official PostgreSQL documentation
        - log_filename: Default to 'postgresql-%Y-%m-%d_%H%M.log' (customized by us).
        - log_rotation_age: Default to 1 day (3 days for small system and 4, 6 hours for large system)
        - log_rotation_size: Default to 256 MiB (32 MiB for small/medium system). It is better to make it rotate
        by time-based rather than size-based.
        - log_truncate_on_rotation: Default to 'on' (customized by us). However, truncation will occur only when a new
        file is being opened due to time-based rotation, not during server startup or size-based rotation
        - log_startup_progress_interval: Default to 1 second (customized by us as 10 seconds by official PostgreSQL
        documentation).
        - log_autovacuum_min_duration: Default to 300 seconds (customized by us as 600 seconds by official PostgreSQL
        documentation). Set to zero to log all statements and actions, and -1 to disable this feature.
        - log_checkpoints: Default to 'on' by official PostgreSQL documentation
        - log_connections: Default to 'on' (customized by us as 'off' by official PostgreSQL documentation).
        - log_disconnections: Default to 'on' (customized by us as 'off' by official PostgreSQL documentation).
        - log_duration: Default to 'on' (customized by us as 'off' by official PostgreSQL documentation).
        - log_error_verbosity: Default to 'VERBOSE' (customized by us as 'DEFAULT' by official PostgreSQL documentation).
        - log_line_prefix: Default to '%m [%p] %quser=%u@%r@%a_db=%d,backend=%b,xid=%x %v,log=%l' (customized by us).
        - log_lock_waits: Default to 'on' (customized by us as 'off' by official PostgreSQL documentation). A log message
        is produced when a session waits longer than deadlock_timeout to acquire a lock.
        - log_statement: Default to 'mod' (customized by us as 'none' by official PostgreSQL documentation).
        Controls which SQL statements are logged.
        - log_replication_commands: Default to 'on' (customized by us as 'off' by official PostgreSQL documentation).
        - log_timezone: Default to 'UTC' by official PostgreSQL documentation

"""
import logging
from typing import Callable, Any

from pydantic import ByteSize, ValidationError

from src.static.c_toml import LoadAppToml
from src.static.vars import APP_NAME_UPPER, Mi, APP_NAME_LOWER, RANDOM_IOPS, K10, MINUTE
from src.tuner.data.options import PG_TUNE_USR_OPTIONS, backup_description
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.scope import PG_SCOPE
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.pg_dataclass import PG_SYS_SHARED_INFO, PG_TUNE_REQUEST
from src.tuner.profile.gtune_common_db_config import cap_value, get_postgresql_memory_worst_case_remaining, \
    calculate_maximum_mem_in_use

__all__ = ["stune_db_config"]
_logger = logging.getLogger(APP_NAME_UPPER)
_MIN_USER_CONN_FOR_ANALYTICS = 10
_MAX_USER_CONN_FOR_ANALYTICS = 50
_DEFAULT_WAL_SENDERS: int = 3

# =============================================================================
def _trigger_tuning(keys: dict[PG_SCOPE, tuple[str, ...]], request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    for scope, items in keys.items():
        managed_items, managed_cache = sys_info.get_managed_item_and_cache('database', 'config',
                                                                           scope=scope)
        for key in items:
            if (t_itm := managed_items.get(key, None)) is not None:
                t_itm.after = t_itm.trigger(managed_cache, managed_cache, request.options, sys_info) \
                    if isinstance(t_itm.trigger, Callable) else t_itm.trigger
                managed_cache[key] = t_itm.after
    return None

def _item_tuning(key: str, after: Any, scope: PG_SCOPE, sys_info: PG_SYS_SHARED_INFO,
                 suffix_text: str = '', before: Any = None) -> bool:
    if before is None:
        before = sys_info.get_managed_cache('database', 'config')[key]

    if before is None or before != after:
        items, cache = sys_info.get_managed_item_and_cache('database', 'config', scope=scope)
        _logger.info(f"The {key} is updated from {before} to {after} {suffix_text}.")
        try:
            items[key].after = after
            cache[key] = after
        except KeyError:
            _logger.error(f"The {key} is not found in the managed tuning item list, probably the scope is invalid.")
            raise KeyError(f"The {key} is not found in the managed tuning item list, probably the scope is invalid.")
    else:
        _logger.warning(f"The {key} is not updated due to no change detected.")

    return before != after


# =============================================================================
# Connection and Memory Tuning for the PostgreSQL Database Server
def _max_conn_tune(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO) -> bool:
    if request.options.workload_type not in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_LAKE, PG_WORKLOAD.DATA_WAREHOUSE,
                                             PG_WORKLOAD.LOG):
        _logger.info("The workload type is not primarily managed by the application. Only the OLAP, Data Lake, "
                     "Data Warehouse, Logging workloads are primarily managed by the application.")
        return False
    if request.options.workload_type == PG_WORKLOAD.HTAP:
        _logger.info("The workload type is hybrid between OLAP and OLTP, thus the number of connection is "
                     "not resizing.")
        return False
    if request.options.tuning_kwargs.user_max_connections > 0:
        _logger.info("The user has overridden the max_connections -> Skip the tuning")
        return False

    # Find the PG_SCOPE.CONNECTION -> max_connections
    max_connections: str = 'max_connections'
    cache = sys_info.get_managed_cache('database', 'config')
    reserved_connections = cache['reserved_connections'] + cache['superuser_reserved_connections']
    new_result = cap_value(cache[max_connections].after - reserved_connections,
                           max(_MIN_USER_CONN_FOR_ANALYTICS, reserved_connections),
                           max(_MAX_USER_CONN_FOR_ANALYTICS, reserved_connections))
    new_result += reserved_connections
    detect_change = _item_tuning(key=max_connections, after=new_result, scope=PG_SCOPE.CONNECTION, sys_info=sys_info,
                                 before=cache[max_connections])
    return detect_change

def _mem_tune(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    _logger.info("Start tuning the memory of the PostgreSQL database server based on the database workload")
    if  _max_conn_tune(request, sys_info) is True:  # The tuning observed the change
        _logger.info('The connection tuning is completed and change is detected -> Re-tune the memory')
        _trigger_tuning({
            PG_SCOPE.MEMORY: ('shared_buffers', 'temp_buffers', 'work_mem'),
            PG_SCOPE.QUERY_TUNING: ('effective_cache_size',),
            PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE: ('wal_buffers',),
        }, request, sys_info)
    else:
        _logger.info('The connection tuning is completed or ignored due to change is not there -> Skiping ...')

    # Tune the shared_buffers and effective_cache_size
    _logger.info(f"The memory tuning is set to {request.options.opt_memory} mode -> Tune the effective_cache_size")
    kwargs = request.options.tuning_kwargs
    before_eff_cache_size_percentage = kwargs.effective_cache_size_available_ratio
    pairs: dict[PG_PROFILE_OPTMODE, tuple[float, float]] = {
        PG_PROFILE_OPTMODE.SPIDEY: (0.92, 0.96),
        PG_PROFILE_OPTMODE.OPTIMUS_PRIME: (0.94, 0.97),
        PG_PROFILE_OPTMODE.PRIMORDIAL: (0.97, 0.99),  # We don't want 100% of memory is exploited
        PG_PROFILE_OPTMODE.NONE: (before_eff_cache_size_percentage, before_eff_cache_size_percentage)
    }
    _logger.debug(f"Re-update the effective_cache_size_available_ratio between {pairs[request.options.opt_memory]}")
    after_eff_cache_size_percentage = cap_value(before_eff_cache_size_percentage, *pairs[request.options.opt_memory])
    if before_eff_cache_size_percentage != after_eff_cache_size_percentage:
        kwargs.effective_cache_size_available_ratio = after_eff_cache_size_percentage
        _logger.debug(f"The effective_cache_size_heuristic_percentage is updated from "
                      f"{before_eff_cache_size_percentage} to {after_eff_cache_size_percentage}")
        _trigger_tuning({
            PG_SCOPE.MEMORY: ('shared_buffers',),
            PG_SCOPE.QUERY_TUNING: ('effective_cache_size',)
        }, request, sys_info)
        _trigger_tuning({
            PG_SCOPE.MEMORY: ('temp_buffers', 'work_mem'),
            PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE: ('wal_buffers',)
        }, request, sys_info)

    # Tune the work_mem and hash_mem_multiplier to use more memory on OLAP workload
    work_mem = 'work_mem'
    hash_mem_multiplier = 'hash_mem_multiplier'
    items, cache = sys_info.get_managed_item_and_cache('database', 'config', scope=PG_SCOPE.MEMORY)
    after_hash_mem_multiplier = cache[hash_mem_multiplier]
    if cache[work_mem] >= 40 * Mi:  # Proceed if the work_mem is greater than 40 MiB
        if request.options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.RAG, PG_WORKLOAD.SEARCH,
                                             PG_WORKLOAD.TIME_SERIES):
            after_hash_mem_multiplier = 2.5
        elif request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE):
            after_hash_mem_multiplier = 3.0
        _item_tuning(key=hash_mem_multiplier, after=after_hash_mem_multiplier, scope=PG_SCOPE.MEMORY, sys_info=sys_info,
                     suffix_text=f'by workload: {request.options.workload_type}',
                     before=cache[hash_mem_multiplier])
    return None

# =============================================================================
# Disk Tuning for the PostgreSQL Database Server
def _disk_tune(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    # Tune the random_page_cost by converting to disk throughput, then compute its minimum
    _disk_toml_iops = LoadAppToml()['disk'][RANDOM_IOPS]
    cache = sys_info.get_managed_cache('database', 'config')
    minimum_iops = min(request.options.data_index_spec.single_perf()[1], request.options.wal_spec.single_perf()[1])

    # Tune the random_page_cost by converting to disk throughput, then compute its minimum
    _logger.info(f'Start tuning the disk with random_page_cost attribute (controlled by disk random IOPS)')
    random_page_cost = 'random_page_cost'
    before_random_page_cost = cache[random_page_cost]
    after_random_page_cost = cache[random_page_cost]
    if minimum_iops <= _disk_toml_iops['hddv1']:
        after_random_page_cost = 3.25
    elif minimum_iops >= _disk_toml_iops['nvmepciev3x4v1']:
        after_random_page_cost = 1.05
    elif minimum_iops >= _disk_toml_iops['ssdv3']:
        after_random_page_cost = 1.1
    elif minimum_iops >= _disk_toml_iops['ssdv2']:
        after_random_page_cost = 1.2
    elif minimum_iops > 4 * _disk_toml_iops['hddv2']:
        num_interceptions: int = 16
        final_random_page_cost: float = 1.25
        decay_rate = (before_random_page_cost - final_random_page_cost) / num_interceptions
        assert decay_rate > 0, "The decay rate is not positive"
        assert (_disk_toml_iops[f'ssdv1'] * 1 // num_interceptions) > 4 * _disk_toml_iops['hddv2'], \
            f"The 1/{num_interceptions} IOPS of SSDv1 is not greater than the 4x IOPS of HDDv2"
        for i in range(1, num_interceptions + 1):
            if minimum_iops >= int(_disk_toml_iops[f'ssdv1'] * i // num_interceptions):
                after_random_page_cost = max(final_random_page_cost, after_random_page_cost - decay_rate)
            else:
                break
    _item_tuning(key=random_page_cost, after=after_random_page_cost, scope=PG_SCOPE.QUERY_TUNING, sys_info=sys_info,
                 suffix_text='due to the use of modern SSD', before=before_random_page_cost)

    # Tune the effective_io_concurrency and maintenance_io_concurrency by converting to disk throughput
    _logger.info(f'Start tuning the disk with effective_io_concurrency and maintenance_io_concurrency '
                 f'attributes (controlled by disk random IOPS)')
    effective_io_concurrency = 'effective_io_concurrency'
    before_effective_io_concurrency = cache[effective_io_concurrency]
    after_effective_io_concurrency = before_effective_io_concurrency

    maintenance_io_concurrency = 'maintenance_io_concurrency'
    before_maintenance_io_concurrency = cache[maintenance_io_concurrency]

    if minimum_iops >= _disk_toml_iops['nvmepciev3x4v1']:
        after_effective_io_concurrency = 256
    elif minimum_iops >= _disk_toml_iops['ssdv2']:
        after_effective_io_concurrency = 192
    elif minimum_iops > _disk_toml_iops['hddv2']:
        for i, sub_iops in enumerate((4/3, 7/6, 1, 5/6, 2/3, 1/2, 1/3, 1/6, 1/8)):
            if minimum_iops >= int(_disk_toml_iops[f'ssdv1'] * sub_iops):
                after_effective_io_concurrency = int(128 * sub_iops + 16)
                break

    if (raid_scale := min(request.options.data_index_spec.raid_scale_factor(), request.options.wal_spec.raid_scale_factor())) > 1:
        after_effective_io_concurrency *= (raid_scale ** request.options.tuning_kwargs.raid_io_efficiency)
        after_maintenance_io_concurrency = max(16, after_effective_io_concurrency // 4)
    else:
        after_maintenance_io_concurrency = max(16, after_effective_io_concurrency // 2)
    after_effective_io_concurrency = cap_value(after_effective_io_concurrency, 16, K10)
    after_maintenance_io_concurrency = cap_value(after_maintenance_io_concurrency, 16, K10)
    _item_tuning(key=effective_io_concurrency, after=after_effective_io_concurrency, scope=PG_SCOPE.OTHERS,
                 sys_info=sys_info, suffix_text='due to the use of modern SSD', before=before_effective_io_concurrency)
    _item_tuning(key=maintenance_io_concurrency, after=after_maintenance_io_concurrency, scope=PG_SCOPE.OTHERS,
                 sys_info=sys_info, suffix_text='due to the use of modern SSD', before=before_maintenance_io_concurrency)

    # Tune the vacuum_cost_page_dirty

    vacuum_cost_page_dirty = 'vacuum_cost_page_dirty'
    before_vacuum_cost_page_dirty = cache[vacuum_cost_page_dirty]
    after_vacuum_cost_page_dirty = before_vacuum_cost_page_dirty
    if minimum_iops >= _disk_toml_iops['nvmepciev3x4v1']:
        after_vacuum_cost_page_dirty = 15
    elif minimum_iops >= _disk_toml_iops['ssdv2']:
        after_vacuum_cost_page_dirty = 17
    elif minimum_iops >= _disk_toml_iops['ssdv1']:
        after_vacuum_cost_page_dirty = 18
    elif minimum_iops >= _disk_toml_iops['ssdv1'] // 2:
        after_vacuum_cost_page_dirty = 19
    _item_tuning(key=vacuum_cost_page_dirty, after=after_vacuum_cost_page_dirty, scope=PG_SCOPE.MAINTENANCE,
                 sys_info=sys_info, suffix_text='due to the use of modern SSD', before=before_vacuum_cost_page_dirty)

    # Tune the bgwriter_lru_maxpages
    _logger.info(f'Start tuning the disk with bgwriter_lru_maxpages attribute (controlled by disk random IOPS)')
    bgwriter_lru_maxpages = 'bgwriter_lru_maxpages'
    before_bgwriter_lru_maxpages = cache[bgwriter_lru_maxpages]
    after_bgwriter_lru_maxpages = before_bgwriter_lru_maxpages
    if minimum_iops >= 4 * _disk_toml_iops['hddv2']:
        after_bgwriter_lru_maxpages = 250
    elif minimum_iops >= _disk_toml_iops['hddv2']:
        after_bgwriter_lru_maxpages = 200
    elif minimum_iops >= _disk_toml_iops['hddv1']:
        after_bgwriter_lru_maxpages = 100
    _item_tuning(key=bgwriter_lru_maxpages, after=after_bgwriter_lru_maxpages, scope=PG_SCOPE.OTHERS,
                 sys_info=sys_info, suffix_text='due to the use of HDD', before=before_bgwriter_lru_maxpages)

    # Tune the commit_delay (in micro-second) based on database workload
    _logger.info(f'Start tuning the disk with commit_delay attribute (controlled by disk random IOPS)')
    minimum_iops = min(request.options.data_index_spec.single_perf()[1], request.options.wal_spec.single_perf()[1])
    commit_delay = 'commit_delay'
    after_commit_delay = cache[commit_delay]
    if request.options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG):
        if minimum_iops <= _disk_toml_iops['hddv1']:
            after_commit_delay = 5 * K10
        elif minimum_iops <= _disk_toml_iops['hddv2']:
            after_commit_delay = 2 * K10
        else:
            after_commit_delay = 1 * K10
    elif request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE):
        after_commit_delay = 2 * K10
    _item_tuning(key=commit_delay, after=after_commit_delay, scope=PG_SCOPE.QUERY_TUNING, sys_info=sys_info,
                 suffix_text=f"by workload: {request.options.workload_type}", before=cache[commit_delay])
    return None


# =============================================================================
# Query Tuning for the PostgreSQL Database Server
def _query_tune(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    # Tune the cpu_tuple_cost and parallel_tuple_cost
    _logger.info("Start tuning the query planner of the PostgreSQL database server based on the database workload. "
                 "Impactedd attributes: cpu_tuple_cost, parallel_tuple_cost")
    cpu_tuple_cost = 'cpu_tuple_cost'
    _workload_translations = {
        PG_WORKLOAD.SOLTP: 0.01,
        PG_WORKLOAD.LOG: 0.005,
        PG_WORKLOAD.OLTP: 0.015,
        PG_WORKLOAD.SEARCH: 0.015,
        PG_WORKLOAD.HTAP: 0.025,
        PG_WORKLOAD.OLAP: 0.03,
        PG_WORKLOAD.DATA_WAREHOUSE: 0.03,
        PG_WORKLOAD.DATA_LAKE: 0.03,
    }
    if request.options.workload_type in _workload_translations:
        new_cpu_tuple_cost = _workload_translations[request.options.workload_type]
        if _item_tuning(key=cpu_tuple_cost, after=new_cpu_tuple_cost, scope=PG_SCOPE.QUERY_TUNING, sys_info=sys_info,
                        suffix_text=f"by workload: {request.options.workload_type}", before=None):
            _trigger_tuning({
                PG_SCOPE.QUERY_TUNING: ('parallel_tuple_cost',),
            }, request, sys_info)
            return True

    _logger.info('Other workload types can be sticked with the default options.')
    return False


# =============================================================================
# Tune the data integrity and replication for the PostgreSQL Database Server
def _repl_tune(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    _logger.info("Start tuning the data integrity and replication of the PostgreSQL database server based on the "
                 "data integrity and high-availability requirements")
    wal_level = 'wal_level'
    synchronous_commit = 'synchronous_commit'
    replication_level: int = backup_description()[request.options.max_level_backup_tool][1]
    num_replicas: int = request.options.max_num_logical_replicas_on_primary + request.options.max_num_stream_replicas_on_primary
    items, cache = sys_info.get_managed_item_and_cache('database', 'config',
                                                       scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE)
    if replication_level < 2 and request.options.max_num_logical_replicas_on_primary == 0 and request.options.max_num_stream_replicas_on_primary == 0:
        _logger.debug("User don't intend to have any replication or archiving -> Switch to minimal")
        _item_tuning(key=wal_level, after='minimal', scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, sys_info=sys_info,
                     before=cache[wal_level])

    if request.options.allow_lost_transaction_during_crash:
        if cache[wal_level] == 'minimal':
            _logger.debug("User allows the lost transaction during crash -> Switch to off")
            _item_tuning(key=synchronous_commit, after='off', scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                         sys_info=sys_info, before=cache[synchronous_commit])

        elif request.options.max_num_logical_replicas_on_primary + request.options.max_num_stream_replicas_on_primary == 0:
            _logger.debug("User allows the lost transaction during crash but with non-minimal wal-level. As user having "
                          "no replicas or standby -> Switch to local")
            _item_tuning(key=synchronous_commit, after='local', scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                         sys_info=sys_info, before=cache[synchronous_commit])

    # Tune the max_wal_senders
    _logger.info("Start tuning the replication with max_wal_senders, max_replication_slots, and wal_sender_timeout "
                 "attributes")
    max_wal_senders = 'max_wal_senders'
    _logger.info(f"Replication level: {replication_level}, Number of replicas: {num_replicas}, "
                 f"WAL level: {cache[wal_level]}")
    after_max_wal_senders = _DEFAULT_WAL_SENDERS + (num_replicas if cache[wal_level] != 'minimal' else 0)
    _item_tuning(key=max_wal_senders, after=after_max_wal_senders, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 sys_info=sys_info, before=cache[max_wal_senders])

    # Tune the max_replication_slots
    # We can use request.options.max_num_stream_replicas_on_primary, but the user could forget to update this
    # value so it is best to update it to be identical. Also, this value meant differently on sending servers
    # and subscriber, so it is best to keep it identical.
    max_replication_slots = 'max_replication_slots'
    _item_tuning(key=max_replication_slots, after=after_max_wal_senders, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 sys_info=sys_info, before=cache[max_replication_slots])

    # Tune the wal_sender_timeout
    if request.options.offshore_replication:
        wal_sender_timeout = 'wal_sender_timeout'
        _item_tuning(key=wal_sender_timeout, after=2 * MINUTE, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                     sys_info=sys_info, before=cache[wal_sender_timeout])

    return None


# =============================================================================
# Tune based on specific workload
def _wrk_tune(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    # Tune the shared_buffers and work_mem by boost the scale factor (we don't change heuristic connection
    # as it represented their real-world workload). Similarly, with the ratio between temp_buffers and work_mem
    # Enable extra tuning to increase the memory usage if not meet the expectation
    if request.options.opt_memory_precision == PG_PROFILE_OPTMODE.NONE:
        _logger.info("The memory precision tuning is disabled by the user -> Skip the extra tuning")
        return None

    _logger.info("Start tuning the overall memory usage of the PostgreSQL database server. Impacted attributes: "
                 "shared_buffers, temp_buffers, work_mem, wal_buffers, effective_cache_size")
    srv_mem = (sys_info.vm_snapshot.mem_virtual.total - request.options.base_kernel_memory_usage -
               request.options.base_monitoring_memory_usage)
    srv_mem_bytesize = ByteSize(srv_mem).human_readable(separator=' ')

    stop_point: float = request.options.tuning_kwargs.max_normal_memory_usage
    boost_ratio: float = request.options.tuning_kwargs.memory_precision_tuning_ratio
    working_memory_functions = {
        PG_PROFILE_OPTMODE.SPIDEY:
            (lambda ro, si: calculate_maximum_mem_in_use(ro, si, scale_to_normal=False)),
        PG_PROFILE_OPTMODE.OPTIMUS_PRIME:
            (lambda ro, si: (calculate_maximum_mem_in_use(ro, si, scale_to_normal=False) +
                             calculate_maximum_mem_in_use(ro, si, scale_to_normal=True)) // 2),
        PG_PROFILE_OPTMODE.PRIMORDIAL:
            (lambda ro, si: calculate_maximum_mem_in_use(ro, si, scale_to_normal=True)),
    }
    keys = {
        PG_SCOPE.MEMORY: ('shared_buffers', 'temp_buffers', 'work_mem'),
        PG_SCOPE.QUERY_TUNING: ('effective_cache_size',),
        PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE: ('wal_buffers',)
    }

    working_memory = working_memory_functions[request.options.opt_memory_precision](ro=request.options, si=sys_info)
    working_memory_ratio = working_memory / srv_mem

    if working_memory_ratio < stop_point:
        _logger.info(f"The working memory usage based on memory profile is {working_memory_ratio * 100:.2f} (%) of "
                     f"{srv_mem_bytesize} or {ByteSize(working_memory).human_readable(separator=' ')} which is less "
                     f"than the user-defined threshold. Proceed to tune the shared_buffers, temp_buffers, work_mem, "
                     f"wal_buffers evenly with boost rate: {boost_ratio} under profile mode = "
                     f"{request.options.opt_memory_precision}.")

    def _show_tuning_result(first_text: str):
        texts = [first_text]
        for scope, key_itm_list in keys.items():
            items = sys_info.get_managed_items('database', 'config', scope=scope)
            for key_itm in key_itm_list:
                texts.append(f'\n\t - {items[key_itm].transform_keyname()}: {items[key_itm].out_display()}')
        _logger.info(''.join(texts))

    _show_tuning_result('Result (before): ')
    _logger.debug(f'Expected maximum memory usage in normal condition: {stop_point * 100:.2f} (%) '
                  f'of {srv_mem_bytesize}')
    if request.options.workload_type not in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG):
        count: int = 0
        ongoing_keys = keys.copy()
        ongoing_keys.pop(PG_SCOPE.QUERY_TUNING)
        while working_memory / srv_mem < request.options.tuning_kwargs.max_normal_memory_usage:
            try:
                request.options.tuning_kwargs.shared_buffers_ratio += boost_ratio
                request.options.tuning_kwargs.max_work_buffer_ratio += boost_ratio
            except ValidationError as e:
                _logger.error(f'Error: The two tuning keywords cannot be incremented more. Stop the auto-tuning.'
                              f'\nDetail: {e}')
                break
            _trigger_tuning(ongoing_keys, request, sys_info)

            working_memory = working_memory_functions[request.options.opt_memory_precision](ro=request.options, si=sys_info)
            working_memory_ratio = working_memory / srv_mem
            _logger.info(f'Iteration #{count}: The working memory usage based on memory profile increased to '
                         f'{ByteSize(working_memory).human_readable(separator=' ')} or '
                         f'{working_memory_ratio * 100:.2f} (%) of {srv_mem_bytesize}.')
            if working_memory_ratio >= stop_point:
                _logger.info(f'The working memory usage ratio is over the expected condition. Rollback ...')
                request.options.tuning_kwargs.shared_buffers_ratio -= boost_ratio
                request.options.tuning_kwargs.max_work_buffer_ratio -= boost_ratio
                _trigger_tuning(keys, request, sys_info)
                break

            count += 1
            if count == 1 or count % 5 == 0:
                _show_tuning_result(f'Result (Iteration #{count}): ')

        if count != 0:
            _logger.info(f'The shared_buffers and work_mem are increased by {count} iteration(s).')
            _logger.info(f'The shared_buffers_ratio is now {request.options.tuning_kwargs.shared_buffers_ratio:.2f} ')
            _logger.info(f'The max_work_buffer_ratio is now {request.options.tuning_kwargs.max_work_buffer_ratio:.2f}.')
            _show_tuning_result('Result (after): ')

        else:
            _logger.warning('The shared_buffers and work_mem are not increased due to the maximum normal memory usage '
                            'is already over the expected condition.')
    else:
        _logger.warning(f"The workload type is {request.options.workload_type} which is not in the scope of "
                        f"extra tuning, requesting not a SOLTP or LOG workload type.")

    return None


def stune_db_config(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    if not request.options.enable_database_correction_tuning:
        _logger.info("The database correction tuning is disabled by the user -> Skip the workload tuning")
        return None

    _logger.info('==========================================================================================')
    _logger.info("Start tuning the workload of the PostgreSQL database server based on the database workload")

    # Connection and Memory Tuning
    _mem_tune(request, sys_info)

    # Disk Tuning
    _disk_tune(request, sys_info)

    # Query Tuning
    _query_tune(request, sys_info)

    # Replication Tuning
    _repl_tune(request, sys_info)

    # Workload Tuning
    _wrk_tune(request, sys_info)

    # Try re-sync cache
    diverged_items = sys_info.sync_cache_from_items('database', 'config')
    if diverged_items:
        _logger.warning(f'The cache is diverged from the managed items: {diverged_items}')

    # Compute memory usage
    # Don't use the :func:`get_postgresql_memory_worst_case_remaining` here since we are in the tuning stage
    srv_mem = (sys_info.vm_snapshot.mem_virtual.total - request.options.base_kernel_memory_usage -
               request.options.base_monitoring_memory_usage)
    srv_mem_bytesize = ByteSize(srv_mem).human_readable(separator=' ')
    maximum_normal_memory = calculate_maximum_mem_in_use(request.options, sys_info, scale_to_normal=False)
    normal_memory = calculate_maximum_mem_in_use(request.options, sys_info, scale_to_normal=True)
    maximum_normal_memory_ratio = maximum_normal_memory / srv_mem
    normal_memory_ratio = normal_memory / srv_mem
    _logger.info(f'Your server uses {ByteSize(normal_memory).human_readable(separator=' ')} in the normal working '
                 f'condition and {ByteSize(maximum_normal_memory).human_readable()} in its worst case '
                 f'(ignore high-availability, maintenance, replication, administration), which associated to '
                 f'respectively {normal_memory_ratio * 100:.2f} (%) and {maximum_normal_memory_ratio * 100:.2f} (%) '
                 f'of the total memory ({srv_mem_bytesize}).')
    return None