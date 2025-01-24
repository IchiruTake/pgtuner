"""
This module is to perform specific tuning on the PostgreSQL database server.

"""
import logging
from math import ceil, sqrt
from typing import Callable, Any

from pydantic import ValidationError

from src.static.c_toml import LoadAppToml
from src.static.vars import APP_NAME_UPPER, Mi, RANDOM_IOPS, K10, MINUTE, Gi, DB_PAGE_SIZE, BASE_WAL_SEGMENT_SIZE, \
    SECOND, WEB_MODE, THROUGHPUT
from src.tuner.data.disks import network_disk_performance
from src.tuner.data.options import backup_description, PG_TUNE_USR_OPTIONS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.pg_dataclass import PG_TUNE_RESPONSE, PG_TUNE_REQUEST
from src.tuner.profile.database.shared import wal_time
from src.utils.pydantic_utils import bytesize_to_hr
from src.utils.pydantic_utils import realign_value_to_unit, cap_value
from src.utils.timing import time_decorator

__all__ = ['correction_tune']
_logger = logging.getLogger(APP_NAME_UPPER)
_MIN_USER_CONN_FOR_ANALYTICS = 10
_MAX_USER_CONN_FOR_ANALYTICS = 40
_DEFAULT_WAL_SENDERS: tuple[int, int, int] = (3, 5, 7)
_TARGET_SCOPE = PGTUNER_SCOPE.DATABASE_CONFIG


def _trigger_tuning(keys: dict[PG_SCOPE, tuple[str, ...]], request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    change_list = []
    for scope, items in keys.items():
        managed_items = response.get_managed_items(_TARGET_SCOPE, scope=scope)
        for key in items:
            if (t_itm := managed_items.get(key, None)) is not None and isinstance(t_itm.trigger, Callable):
                old_result = managed_cache[key]
                t_itm.after = t_itm.trigger(managed_cache, managed_cache, request.options, response)
                managed_cache[key] = t_itm.after
                if old_result != t_itm.after:
                    change_list.append((key, t_itm.out_display()))
    if change_list:
        _logger.info(f'The following items are updated: {change_list}')
    else:
        _logger.warning('No change is detected in the trigger tuning.')
    return None


def _item_tuning(key: str, after: Any, scope: PG_SCOPE, response: PG_TUNE_RESPONSE,
                 suffix_text: str = '', before: Any = None) -> bool:
    if before is None:
        before = response.get_managed_cache(_TARGET_SCOPE)[key]

    if before is None or before != after:
        items, cache = response.get_managed_items_and_cache(_TARGET_SCOPE, scope=scope)
        _logger.info(f'The {key} is updated from {before} (or {items[key].out_display()}) to '
                     f'{after} (or {items[key].out_display(override_value=after)}) {suffix_text}.')
        try:
            items[key].after = after
            cache[key] = after
        except KeyError:
            msg = f'The {key} is not found in the managed tuning item list, probably the scope is invalid.'
            _logger.critical(msg)
            raise KeyError(msg)

    return before != after


# =============================================================================
# CPU & Statistics
@time_decorator
def _conn_cache_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE) -> None:
    _logger.info('Start tuning the memory of the PostgreSQL database server based on the database workload')
    _kwargs = request.options.tuning_kwargs
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)

    # ----------------------------------------------------------------------------------------------
    # Optimize the max_connections
    if _kwargs.user_max_connections > 0:
        _logger.info('The user has overridden the max_connections -> Skip the maximum tuning')
    elif request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_LAKE, PG_WORKLOAD.DATA_WAREHOUSE,
                                           PG_WORKLOAD.LOG, PG_WORKLOAD.TSR_OLAP):
        _logger.info('The workload type is primarily managed by the application such as full-based analytics or '
                     'logging/blob storage workload. ')

        # Find the PG_SCOPE.CONNECTION -> max_connections
        max_connections: str = 'max_connections'
        reserved_connections = managed_cache['reserved_connections'] + managed_cache['superuser_reserved_connections']
        new_result = cap_value(managed_cache[max_connections] - reserved_connections,
                               max(_MIN_USER_CONN_FOR_ANALYTICS, reserved_connections),
                               max(_MAX_USER_CONN_FOR_ANALYTICS, reserved_connections))
        _item_tuning(key=max_connections, after=new_result + reserved_connections, scope=PG_SCOPE.CONNECTION,
                     response=response, before=managed_cache[max_connections])
        _trigger_tuning({
            PG_SCOPE.MEMORY: ('temp_buffers', 'work_mem'),
            PG_SCOPE.QUERY_TUNING: ('effective_cache_size',),
        }, request, response)
    else:
        _logger.info('The connection tuning is ignored due to applied workload type does not match expectation.')

    # ----------------------------------------------------------------------------------------------
    # Tune the idle_in_transaction_session_timeout -> Reduce timeout allowance when more connection
    # GitLab: https://gitlab.com/gitlab-com/gl-infra/production/-/issues/1053
    # In this example, they tune to minimize idle-in-transaction state, but we don't know its number of connections
    # so default 5 minutes and reduce 30 seconds for every 25 connections is a great start for most workloads.
    # But you can adjust this based on the workload type independently.
    _logger.info('Start tuning the idle_in_transaction_session_timeout based on the number of connections.')
    idle_in_transaction_session_timeout = 'idle_in_transaction_session_timeout'
    user_connections = (managed_cache['max_connections'] - managed_cache['reserved_connections'] -
                        managed_cache['superuser_reserved_connections'])
    if user_connections > _MAX_USER_CONN_FOR_ANALYTICS:
        _tmp_user_conn = (user_connections - _MAX_USER_CONN_FOR_ANALYTICS)
        after_idle_in_transaction_session_timeout = \
            managed_cache[idle_in_transaction_session_timeout] - 30 * SECOND * (_tmp_user_conn // 25)
        _item_tuning(key=idle_in_transaction_session_timeout, after=max(31, after_idle_in_transaction_session_timeout),
                     scope=PG_SCOPE.OTHERS, response=response,
                     before=managed_cache[idle_in_transaction_session_timeout])

    return None


@time_decorator
def _query_timeout_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE) -> None:
    _logger.info('Start tuning the query planner (cpu_tuple_cost, parallel_tuple_cost), timeout (statement_timeout, '
                 'lock_timeout), statistics planning, batched commit (commit_delay) of the PostgreSQL '
                 'database server based on the database  workload.')

    # Tune the cpu_tuple_cost, parallel_tuple_cost, lock_timeout, statement_timeout
    _workload_translations: dict[PG_WORKLOAD, tuple[float, tuple[int, int]]] = {
        PG_WORKLOAD.LOG: (0.005, (3 * MINUTE, 5)),
        PG_WORKLOAD.SOLTP: (0.0075, (5 * MINUTE, 5)),
        PG_WORKLOAD.TSR_IOT: (0.0075, (5 * MINUTE, 5)),

        PG_WORKLOAD.SEARCH: (0.02, (5 * MINUTE, 5)),  # Text-based Search
        PG_WORKLOAD.OLTP: (0.015, (10 * MINUTE, 3)),

        PG_WORKLOAD.RAG: (0.025, (5 * MINUTE, 5)),  # Vector-search
        PG_WORKLOAD.GEOSPATIAL: (0.025, (5 * MINUTE, 5)),
        PG_WORKLOAD.TSR_HTAP: (0.025, (30 * MINUTE, 2)),
        PG_WORKLOAD.HTAP: (0.025, (45 * MINUTE, 2)),

        PG_WORKLOAD.OLAP: (0.03, (90 * MINUTE, 2)),
        PG_WORKLOAD.DATA_WAREHOUSE: (0.03, (90 * MINUTE, 2)),
        PG_WORKLOAD.DATA_LAKE: (0.03, (90 * MINUTE, 2)),
        PG_WORKLOAD.TSR_OLAP: (0.03, (90 * MINUTE, 2)),
    }
    _suffix_text: str = f'by workload: {request.options.workload_type}'
    if request.options.workload_type in _workload_translations:
        new_cpu_tuple_cost, (base_timeout, multiplier_timeout) = _workload_translations[request.options.workload_type]
        if _item_tuning(key='cpu_tuple_cost', after=new_cpu_tuple_cost, scope=PG_SCOPE.QUERY_TUNING, response=response,
                        suffix_text=_suffix_text, before=None):
            _trigger_tuning({
                PG_SCOPE.QUERY_TUNING: ('parallel_tuple_cost',),
            }, request, response)

        # 3 seconds was added as the reservation for query plan before taking the lock
        new_lock_timeout = int(base_timeout * multiplier_timeout)
        new_statement_timeout = new_lock_timeout + 3
        _item_tuning(key='lock_timeout', after=new_lock_timeout, scope=PG_SCOPE.OTHERS, response=response,
                     suffix_text=_suffix_text, before=None)
        _item_tuning(key='statement_timeout', after=new_statement_timeout, scope=PG_SCOPE.OTHERS,
                     response=response, suffix_text=_suffix_text, before=None)

    # Tune the default_statistics_target
    _logger.info('Start tuning the default_statistics_target of the PostgreSQL database server based on the '
                 'database workload.')
    default_statistics_target = 'default_statistics_target'
    managed_items, managed_cache = response.get_managed_items_and_cache(_TARGET_SCOPE, scope=PG_SCOPE.QUERY_TUNING)
    after_default_statistics_target = managed_cache[default_statistics_target]
    hw_scope = managed_items[default_statistics_target].hardware_scope[1]
    if request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE,
                                         PG_WORKLOAD.TSR_OLAP):
        after_default_statistics_target = 200
        if hw_scope == 'medium':
            after_default_statistics_target = 350
        elif hw_scope == 'large':
            after_default_statistics_target = 500
        elif hw_scope == 'mall':
            after_default_statistics_target = 750
        elif hw_scope == 'bigt':
            after_default_statistics_target = 1000
    elif request.options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.TSR_HTAP):
        after_default_statistics_target = 150
        if hw_scope == 'large':
            after_default_statistics_target = 225
        elif hw_scope == 'mall':
            after_default_statistics_target = 350
        elif hw_scope == 'bigt':
            after_default_statistics_target = 500
    elif request.options.workload_type in (PG_WORKLOAD.OLTP, PG_WORKLOAD.SEARCH, PG_WORKLOAD.RAG,
                                           PG_WORKLOAD.GEOSPATIAL):
        after_default_statistics_target = 100
        if hw_scope == 'medium' and not request.options.workload_type == PG_WORKLOAD.OLTP:
            after_default_statistics_target = 150
        elif hw_scope == 'large':
            after_default_statistics_target = 200
        elif hw_scope == 'mall':
            after_default_statistics_target = 300
        elif hw_scope == 'bigt':
            after_default_statistics_target = 400
    _item_tuning(key=default_statistics_target, after=after_default_statistics_target, scope=PG_SCOPE.QUERY_TUNING,
                 response=response, suffix_text=_suffix_text, )

    # -------------------------------------------------------------------------
    # Tune the commit_delay (in micro-second), and commit_siblings.
    # Don't worry about the async behaviour with as these commits are synchronous. Additional delay is added
    # synchronously with the application code is justified for batched commits.
    # The WRITE operation in WAL partition is sequential, but its read (when WAL content is not flushed to the
    # datafiles) is random IOPS.  Especially during high-latency replication, unclean/unexpected shutdown, or
    # high-transaction rate, the READ operation on WAL partition is used intensively. Thus, we use the minimum
    # IOPS between the data partition and WAL partition.
    # Now we can calculate the commit_delay (* K10 to convert to millisecond)
    commit_delay = 'commit_delay'
    after_commit_delay = managed_cache[commit_delay]
    managed_items = response.get_managed_items(_TARGET_SCOPE, scope=PG_SCOPE.QUERY_TUNING)
    commit_delay_hw_scope = managed_items[commit_delay].hardware_scope[1]

    if request.options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG, PG_WORKLOAD.TSR_IOT):
        # These workloads are not critical so we can set a high commit_delay. In normal case, the constraint is
        # based on the number of commits and disk size. The server largeness may not impact here
        # The commit_siblings is tuned by sizing at general tuning phase so no actions here.
        _disk_toml_iops = LoadAppToml()['disk'][RANDOM_IOPS]

        # This is made during burst so we combine the calculation here
        _data_iops = request.options.data_index_spec.raid_perf()[1]
        wal_translated_iops = request.options.wal_spec.raid_perf()[0] * (Mi // DB_PAGE_SIZE)
        mixed_iops = min(_data_iops, wal_translated_iops)

        # This is just the rough estimation so don't fall for it.
        network_disk_iops_bound = network_disk_performance(mode=RANDOM_IOPS)
        if mixed_iops <= _disk_toml_iops['hddv1']:
            after_commit_delay = 5 * K10
        elif mixed_iops <= _disk_toml_iops['hddv2']:
            after_commit_delay = 4 * K10
        elif mixed_iops <= min(network_disk_iops_bound):
            after_commit_delay = 3 * K10
        elif mixed_iops <= max(network_disk_iops_bound):
            after_commit_delay = 2 * K10
        else:
            after_commit_delay = 1 * K10

        if commit_delay_hw_scope == 'medium':
            after_commit_delay *= 3
        elif commit_delay_hw_scope == 'large':
            after_commit_delay *= 5
        elif commit_delay_hw_scope == 'mall':
            after_commit_delay *= 7.5
        elif commit_delay_hw_scope == 'bigt':
            after_commit_delay *= 10

        pass
    elif request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE,
                                           PG_WORKLOAD.TSR_OLAP):
        # These workloads are critical but not require end-user and internally managed and transformed by the
        # application side so a high commit_delay is allowed (but may not bring much benefit) unless the database
        # is used on multiple tenants or business requirements. However, since these workloads are run independently
        # and assumed the application side do not mess thing up, the commit_siblings are good to go.
        after_commit_delay = 2 * K10
    elif request.options.workload_type in (PG_WORKLOAD.SEARCH, PG_WORKLOAD.RAG, PG_WORKLOAD.GEOSPATIAL):
        # Since these workloads don't risk the data integrity but the latency are important but not as critical.
        # Thus, even in batch commit, we should prefer a low commit_delay.
        # However, since these workloads are run independently with request, the commit_siblings are good to go.
        after_commit_delay = 1 * K10
        if commit_delay_hw_scope == 'large':
            after_commit_delay = K10 * 5 // 10
        elif commit_delay_hw_scope == 'mall':
            after_commit_delay = K10 * 3 // 10
        elif commit_delay_hw_scope == 'bigt':
            after_commit_delay = K10 * 2 // 10

    elif request.options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.TSR_HTAP, PG_WORKLOAD.OLTP):
        # These workloads have highest and require the data integrity. Thus, the commit_delay should be set to the
        # minimum value. The commit_siblings are tuned by sizing at gtune phase so no actions here.
        # However, since these workloads are run independently with request, the commit_siblings are good to go.
        # For the TSR_HTAP, I am still not sure about this workload of which
        after_commit_delay = K10 * 5 // 10
        if commit_delay_hw_scope == 'large':
            after_commit_delay = K10 * 3 // 10
        elif commit_delay_hw_scope == 'mall':
            after_commit_delay = K10 * 2 // 10
        elif commit_delay_hw_scope == 'bigt':
            after_commit_delay = K10 * 1 // 10
    _item_tuning(key=commit_delay, after=int(after_commit_delay), scope=PG_SCOPE.QUERY_TUNING, response=response,
                 suffix_text=_suffix_text, before=managed_cache[commit_delay])

    return None


# =============================================================================
# Disk-based (Performance)
@time_decorator
def _disk_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    # Tune the random_page_cost by converting to disk throughput, then compute its minimum
    _disk_toml_iops = LoadAppToml()['disk'][RANDOM_IOPS]
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    # The WRITE operation in WAL partition is sequential, but its read (when WAL content is not flushed to the
    # datafiles) is random IOPS.  Especially during high-latency replication, unclean/unexpected shutdown, or
    # high-transaction rate, the READ operation on WAL partition is used intensively. Thus, we use the minimum
    # IOPS between the data partition and WAL partition.
    minimum_iops = request.options.data_index_spec.raid_perf()[1]
    network_disk_iops_bound = network_disk_performance(mode=RANDOM_IOPS)

    # Tune the random_page_cost by converting to disk throughput, then compute its minimum
    _logger.info(f'Start tuning the disk with random_page_cost attribute (controlled by disk random IOPS)')
    random_page_cost = 'random_page_cost'
    before_random_page_cost = managed_cache[random_page_cost]
    after_random_page_cost = managed_cache[random_page_cost]
    if minimum_iops <= _disk_toml_iops['hddv1']:
        after_random_page_cost = 3.25
    elif minimum_iops >= _disk_toml_iops['nvmepciev3x4v1']:
        after_random_page_cost = 1.05
    elif minimum_iops >= _disk_toml_iops['ssdv4']:
        after_random_page_cost = 1.10
    elif minimum_iops >= _disk_toml_iops['ssdv3']:
        after_random_page_cost = 1.15
    elif minimum_iops >= _disk_toml_iops['ssdv2']:
        after_random_page_cost = 1.20
    elif minimum_iops >= _disk_toml_iops['ssdv1']:
        after_random_page_cost = 1.25
    elif minimum_iops >= max(network_disk_iops_bound):  # Could be a local disk
        # The random_page_cost is linearly decreased by the IOPS -> Find the lower bound and corresponding it with
        # the final random_page_cost
        num_interceptions: int = 4
        random_page_cost_interval = (1.50 - 1.25) / num_interceptions
        iops_interval = (_disk_toml_iops['ssdv1'] - max(network_disk_iops_bound)) // num_interceptions
        minimum_iops_index = (minimum_iops - max(network_disk_iops_bound)) // iops_interval
        after_random_page_cost = 1.50 - random_page_cost_interval * (num_interceptions - minimum_iops_index)
    elif minimum_iops >= min(network_disk_iops_bound):  # Could be a network disk
        num_interceptions: int = 5
        random_page_cost_interval = (1.75 - 1.50) / num_interceptions
        iops_interval = (max(network_disk_iops_bound) - min(network_disk_iops_bound)) // num_interceptions
        minimum_iops_index = (minimum_iops - min(network_disk_iops_bound)) // iops_interval
        after_random_page_cost = 1.75 - random_page_cost_interval * (num_interceptions - minimum_iops_index)
    _item_tuning(key=random_page_cost, after=after_random_page_cost, scope=PG_SCOPE.QUERY_TUNING, response=response,
                 before=before_random_page_cost)

    # Tune the effective_io_concurrency and maintenance_io_concurrency by converting to disk throughput
    _logger.info(f'Start tuning the disk with effective_io_concurrency and maintenance_io_concurrency '
                 f'attributes (controlled by disk random IOPS)')
    effective_io_concurrency = 'effective_io_concurrency'
    before_effective_io_concurrency = managed_cache[effective_io_concurrency]
    after_effective_io_concurrency = before_effective_io_concurrency

    maintenance_io_concurrency = 'maintenance_io_concurrency'
    before_maintenance_io_concurrency = managed_cache[maintenance_io_concurrency]
    if minimum_iops >= _disk_toml_iops['nvmepciev5x4v1']:
        after_effective_io_concurrency = 512
    elif minimum_iops >= _disk_toml_iops['nvmepciev4x4v1']:
        after_effective_io_concurrency = 384
    if minimum_iops >= _disk_toml_iops['nvmepciev3x4v1']:
        after_effective_io_concurrency = 256
    elif minimum_iops >= _disk_toml_iops['ssdv3']:
        after_effective_io_concurrency = 224
    elif minimum_iops >= _disk_toml_iops['ssdv2']:
        after_effective_io_concurrency = 192
    elif minimum_iops >= min(network_disk_iops_bound):
        pivots = (3 / 2, 4 / 3, 7 / 6, 1, 5 / 6, 2 / 3, 1 / 2, 1 / 3, 1 / 6, 1 / 8, 1 / 10, 1 / 12, 1 / 15)
        for i, sub_iops in enumerate(pivots):
            if minimum_iops >= int(_disk_toml_iops['ssdv1'] * sub_iops):
                after_effective_io_concurrency = min(192, int(128 * sub_iops) + 16)
                break
    after_maintenance_io_concurrency = max(16, after_effective_io_concurrency // 2)
    after_effective_io_concurrency = cap_value(after_effective_io_concurrency, 16, K10)
    after_maintenance_io_concurrency = cap_value(after_maintenance_io_concurrency, 16, K10)
    _item_tuning(key=effective_io_concurrency, after=after_effective_io_concurrency, scope=PG_SCOPE.OTHERS,
                 response=response, before=before_effective_io_concurrency)
    _item_tuning(key=maintenance_io_concurrency, after=after_maintenance_io_concurrency, scope=PG_SCOPE.OTHERS,
                 response=response, before=before_maintenance_io_concurrency)

    # Tune the vacuum_cost_page_dirty
    vacuum_cost_page_dirty = 'vacuum_cost_page_dirty'
    before_vacuum_cost_page_dirty = managed_cache[vacuum_cost_page_dirty]
    after_vacuum_cost_page_dirty = before_vacuum_cost_page_dirty
    if minimum_iops >= _disk_toml_iops['nvmepciev3x4v1']:
        after_vacuum_cost_page_dirty = 16
    elif minimum_iops >= _disk_toml_iops['ssdv2']:
        after_vacuum_cost_page_dirty = 17
    elif minimum_iops >= _disk_toml_iops['ssdv1']:
        after_vacuum_cost_page_dirty = 18
    elif minimum_iops >= _disk_toml_iops['ssdv1'] // 2:
        after_vacuum_cost_page_dirty = 19
    _item_tuning(key=vacuum_cost_page_dirty, after=after_vacuum_cost_page_dirty, scope=PG_SCOPE.MAINTENANCE,
                 response=response, before=before_vacuum_cost_page_dirty)

    return None


@time_decorator
def _bgwriter_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    _logger.info('Start tuning the background writer of the PostgreSQL database server based on the database workload. '
                 '\nImpacted Attributes: bgwriter_lru_maxpages, ... ')
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    _data_iops = request.options.data_index_spec.raid_perf()[1]
    # Maximum pages is 1/20 of disk random IOPS, minimum is 4 MiB of random IOPS for HDD (default of PostgreSQL)
    max_data = max(4 * Mi // DB_PAGE_SIZE, _data_iops // 20)
    max_pages = max_data * (K10 / managed_cache['bgwriter_delay'])
    bgwriter_lru_maxpages = 'bgwriter_lru_maxpages'
    _item_tuning(key=bgwriter_lru_maxpages, after=realign_value_to_unit(ceil(max_pages), page_size=20)[0],
                 scope=PG_SCOPE.OTHERS, response=response, before=managed_cache[bgwriter_lru_maxpages])


# =============================================================================
# Write-Ahead Logging (WAL)
@time_decorator
def _wal_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    _logger.info('Start tuning the WAL of the PostgreSQL database server based on the '
                 'data integrity and high-availability requirements.')
    replication_level: int = backup_description()[request.options.max_backup_replication_tool][1]
    num_replicas: int = (request.options.max_num_logical_replicas_on_primary +
                         request.options.max_num_stream_replicas_on_primary)
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)

    # -------------------------------------------------------------------------
    # Configure the wal_level
    wal_level = 'wal_level'
    after_wal_level = managed_cache[wal_level]
    if replication_level == 3 or request.options.max_num_logical_replicas_on_primary > 0:
        # Logical replication (highest)
        after_wal_level = 'logical'
    elif replication_level == 2 or request.options.max_num_stream_replicas_on_primary > 0 or num_replicas > 0:
        # Streaming replication (medium level)
        # The condition of num_replicas > 0 is to ensure that the user has set the replication slots
        after_wal_level = 'replica'
    elif replication_level <= 1 and num_replicas == 0:
        after_wal_level = 'minimal'
    _item_tuning(key=wal_level, after=after_wal_level, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 response=response, before=managed_cache[wal_level])
    # Disable since it is not used
    _item_tuning(key='log_replication_commands', after='on' if managed_cache[wal_level] != 'minimal' else 'off',
                 scope=PG_SCOPE.LOGGING, response=response, before=managed_cache['log_replication_commands'])
    if managed_cache[wal_level] == 'minimal' and num_replicas > 0:
        # The post-condition check to prevent the un-realistic error
        _msg = ('P1: The replication level is minimal, but the number of replicas is greater than 0 -> '
                'Developers are urged to validate the above code.')
        _logger.critical(_msg)
        raise ValueError(_msg)

    # Tune the max_wal_senders, max_replication_slots, and wal_sender_timeout
    # We can use request.options.max_num_logical_replicas_on_primary for max_replication_slots, but the user could
    # forget to update this value so it is best to update it to be identical. Also, this value meant differently on
    # sending servers and subscriber, so it is best to keep it identical.
    _logger.info(f'Start tuning the replication with max_wal_senders, max_replication_slots, and wal_sender_timeout '
                 f'attributes based on the number of replicas and offshore replication option.'
                 f'\nReplication level: {replication_level}, Number of replicas: {num_replicas}, '
                 f'WAL level: {managed_cache[wal_level]}')

    # At PostgreSQL 11 or previously, the max_wal_senders is counted in max_connections
    max_wal_senders = 'max_wal_senders'
    reserved_wal_senders = _DEFAULT_WAL_SENDERS[0]
    if managed_cache[wal_level] != 'minimal':
        if num_replicas >= 8:
            reserved_wal_senders = _DEFAULT_WAL_SENDERS[1]
        elif num_replicas >= 16:
            reserved_wal_senders = _DEFAULT_WAL_SENDERS[2]
    after_max_wal_senders = reserved_wal_senders + (num_replicas if managed_cache[wal_level] != 'minimal' else 0)
    _item_tuning(key=max_wal_senders, after=after_max_wal_senders, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 response=response, before=managed_cache[max_wal_senders])

    max_replication_slots = 'max_replication_slots'
    reserved_replication_slots = _DEFAULT_WAL_SENDERS[0]
    if request.options.versioning()[0] >= 15 and managed_cache[wal_level] == 'logical':
        # Before PostgreSQL 15, conditional logical replication is not available and not completed, so we use
        # num_replicas instead; but now the schema-based, row filter, partitioned tables can be replicated
        # so we switch to use the max_num_logical_replicas_on_primary instead.
        if request.options.max_num_logical_replicas_on_primary >= 8:
            reserved_replication_slots = _DEFAULT_WAL_SENDERS[1]
        elif request.options.max_num_logical_replicas_on_primary >= 16:
            reserved_replication_slots = _DEFAULT_WAL_SENDERS[2]
        after_max_replication_slots = reserved_replication_slots + request.options.max_num_logical_replicas_on_primary
    else:
        reserved_replication_slots = reserved_wal_senders
        after_max_replication_slots = reserved_replication_slots + num_replicas  # Equivalent to max_wal_senders
    _item_tuning(key=max_replication_slots, after=after_max_replication_slots,
                 scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 response=response, before=managed_cache[max_replication_slots])

    # Tune the wal_sender_timeout
    if request.options.offshore_replication and managed_cache[wal_level] != 'minimal':
        wal_sender_timeout = 'wal_sender_timeout'
        after_wal_sender_timeout = max(10 * MINUTE, ceil(MINUTE * (2 + (num_replicas / 4))))
        _item_tuning(key=wal_sender_timeout, after=after_wal_sender_timeout,
                     scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                     response=response, before=managed_cache[wal_sender_timeout])

    # -------------------------------------------------------------------------
    # Tune the synchronous_commit, full_page_writes, fsync
    _logger.info('Start tuning the synchronous_commit, full_page_writes, fsync variables of the PostgreSQL server')
    _profile_optmode_level = PG_PROFILE_OPTMODE.profile_ordering()
    synchronous_commit = 'synchronous_commit'
    if request.options.opt_transaction_lost in _profile_optmode_level[1:]:
        if managed_cache[wal_level] == 'minimal':
            after_synchronous_commit = 'off'
        elif num_replicas == 0:
            after_synchronous_commit = 'local'
        else:
            # We don't reach to 'on' here: See https://postgresqlco.nf/doc/en/param/synchronous_commit/
            after_synchronous_commit = 'remote_write'
        _logger.warning(f'User allows the lost transaction during crash but with {managed_cache[wal_level]} wal_level '
                        f'at profile {request.options.opt_transaction_lost} but data loss could be there. Only '
                        f'enable this during testing only. ')
        _item_tuning(key=synchronous_commit, after=after_synchronous_commit,
                     scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                     response=response, before=managed_cache[synchronous_commit])
        if request.options.opt_transaction_lost in _profile_optmode_level[2:]:
            full_page_writes = 'full_page_writes'
            _item_tuning(key=full_page_writes, after='off', scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                         response=response, before=managed_cache[full_page_writes])
            if request.options.opt_transaction_lost in _profile_optmode_level[3:]:
                fsync = 'fsync'
                _item_tuning(key=fsync, after='off', scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                             response=response, before=managed_cache[fsync])

    return None


@time_decorator
def _wal_size_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE) -> None:
    _logger.info('Start tuning the WAL size of the PostgreSQL database server based on the WAL disk sizing'
                 '\nImpacted Attributes: min_wal_size, max_wal_size, wal_keep_size')
    _wal_disk_size = request.options.wal_spec.disk_usable_size
    _kwargs = request.options.tuning_kwargs
    _scope = PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE
    managed_items, managed_cache = response.get_managed_items_and_cache(_TARGET_SCOPE, scope=_scope)

    # Tune the max_wal_size (This is easy to tune as it is based on the maximum WAL disk total size)
    # Ensure a full use of WAL partition
    max_wal_size = 'max_wal_size'
    if _wal_disk_size * (1 - _kwargs.max_wal_size_ratio) > _kwargs.max_wal_size_remain_upper_size:
        after_max_wal_size = _wal_disk_size - _kwargs.max_wal_size_remain_upper_size
    else:
        after_max_wal_size = _wal_disk_size * _kwargs.max_wal_size_ratio
    after_max_wal_size = realign_value_to_unit(max(1 * Gi, after_max_wal_size), _kwargs.wal_segment_size)[1]
    _item_tuning(key=max_wal_size, after=after_max_wal_size, scope=_scope,
                 response=response, before=managed_cache[max_wal_size])
    assert managed_cache[max_wal_size] <= int(_wal_disk_size), 'The max_wal_size is greater than the WAL disk size'
    _trigger_tuning({
        PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE: ('wal_keep_size',)
    }, request, response)

    # Tune the min_wal_size as these are not specifically related to the max_wal_size. This is the top limit of the
    # WAL partition so that if the disk usage beyond the threshold (disk capacity - min_wal_size), the WAL file
    # is removed. Otherwise, the WAL file is being recycled. This is to prevent the disk full issue.
    # Increase the min_wal_size so that the system can handle spikes in WAL usage during batch jobs and other
    # unusual circumstances
    # You could set the min_wal_size to be larger or smaller than max_wal_size and nothing will happen (but making
    # sure those must be smaller than the WAL disk size)
    # Don't worry as this value is not important and only set as reserved boundary to prevent issue.
    min_wal_size = 'min_wal_size'
    after_min_wal_size = max(min(10 * _kwargs.wal_segment_size, _wal_disk_size),
                             int((_wal_disk_size - managed_cache[max_wal_size]) * _kwargs.min_wal_ratio_scale))
    after_min_wal_size = realign_value_to_unit(after_min_wal_size, _kwargs.wal_segment_size)[1]
    _item_tuning(key=min_wal_size, after=after_min_wal_size, scope=_scope,
                 response=response, before=managed_cache[min_wal_size])
    assert managed_cache[min_wal_size] <= int(_wal_disk_size), 'The min_wal_size is greater than the WAL disk size'

    # -------------------------------------------------------------------------
    # Tune the archive_timeout based on the WAL segment size. This is easy because we want to flush the WAL
    # segment to make it have better database health
    # Tune the checkpoint timeout: This is hard to tune as it mostly depends on the amount of data change
    # (workload_profile), disk strength (IO), expected RTO.
    # In general, this is more on the DBA and business strategies. So I think the general tuning phase is good enough
    if _kwargs.wal_segment_size > BASE_WAL_SEGMENT_SIZE:
        _logger.info('Start tuning the archive_timeout and checkpoint_timeout of the PostgreSQL database server based '
                     'on the WAL disk sizing')
        base_timeout: int = 5 * MINUTE
        _wal_segment_size_scale = sqrt(_kwargs.wal_segment_size // BASE_WAL_SEGMENT_SIZE)

        # 30-seconds of precision
        archive_timeout = 'archive_timeout'
        after_archive_timeout = managed_cache[archive_timeout] + int(_wal_segment_size_scale * base_timeout)
        _item_tuning(key=archive_timeout, after=realign_value_to_unit(after_archive_timeout, MINUTE // 2)[0],
                     scope=_scope, response=response, before=managed_cache[archive_timeout])

        _logger.warning('The checkpoint_timeout is increased since you have increased the WAL segment size. Note '
                        'that this is hard to tune as it mostly depends on the amount of data change, disk strength, '
                        'expected RTO. So we only increase it your workload is large, mall, bigt; your data disk '
                        'is performant with ssdv2 or higher, with strong data write and critical workload for end-user '
                        'such as OLTP, HTAP, TSR_HTAP, ...; but it still cannot accommodate all scenarios')
        _disk_toml_iops = LoadAppToml()['disk'][RANDOM_IOPS]
        _data_iops = request.options.data_index_spec.raid_perf()[1]
        _ckpt_wrkl_allow = (PG_WORKLOAD.OLTP, PG_WORKLOAD.HTAP, PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_LAKE,
                            PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.TSR_HTAP, PG_WORKLOAD.TSR_IOT,
                            PG_WORKLOAD.TSR_OLAP)
        if _data_iops >= _disk_toml_iops['ssdv2'] and \
                managed_items['checkpoint_timeout'].hardware_scope[1] in ('large', 'mall', 'bigt') and \
                request.options.workload_type in _ckpt_wrkl_allow:
            checkpoint_timeout = 'checkpoint_timeout'
            after_checkpoint_timeout = managed_cache[checkpoint_timeout] + int(_wal_segment_size_scale * base_timeout)
            _item_tuning(key=checkpoint_timeout, after=realign_value_to_unit(after_checkpoint_timeout, MINUTE // 4)[0],
                         scope=_scope, response=response, before=managed_cache[checkpoint_timeout])

    return None


@time_decorator
def _wal_integrity_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    _logger.info('Start tuning the WAL performance and integrity of the PostgreSQL database server based on the '
                 'provided allowed time of data transaction loss.'
                 '\nImpacted Attributes: wal_buffers and wal_writer_delay ')
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    wal_writer_delay = 'wal_writer_delay'
    _kwargs = request.options.tuning_kwargs
    if managed_cache['synchronous_commit'] == 'off':
        _logger.warning('The synchronous_commit is off -> If data integrity is less important to you than response '
                        'times (for example, if you are running a social networking application or processing logs) '
                        'you can turn this off, making your transaction logs asynchronous. This can result in up '
                        'to wal_buffers or wal_writer_delay * 2 (3 times on worst case) worth of data in an unexpected '
                        'shutdown, but your database will not be corrupted. Note that you can also set this on a '
                        'per-session basis, allowing you to mix “lossy” and “safe” transactions, which is a better '
                        'approach for most applications. It is recommended to set it to local or remote_write if you '
                        "don't prefer lossy transactions. Don't fear of data corruption here")

    # Apply tune the wal_writer_delay here regardless of the synchronous_commit so that we can ensure
    # no mixed of lossy and safe transactions
    after_wal_writer_delay = int(request.options.max_time_transaction_loss_allow_in_millisecond / 3.25)
    _item_tuning(key=wal_writer_delay, after=after_wal_writer_delay, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 response=response, before=managed_cache[wal_writer_delay])

    # -------------------------------------------------------------------------
    # Now we need to estimate how much time required to flush the full WAL buffers to disk (assuming we
    # have no write after the flush or wal_writer_delay is being waken up or 2x of wal_buffers are synced)
    wal_tput = request.options.wal_spec.raid_perf()[0]
    wal_buffers_str: str = 'wal_buffers'

    # Just some useful information
    best_wal_time = wal_time(managed_cache[wal_buffers_str], 1.0, _kwargs.wal_segment_size,
                             wal_writer_delay_in_ms=after_wal_writer_delay, wal_throughput=wal_tput)['total_time']
    worst_wal_time = wal_time(managed_cache[wal_buffers_str], 2.0, _kwargs.wal_segment_size,
                              wal_writer_delay_in_ms=after_wal_writer_delay, wal_throughput=wal_tput)['total_time']

    if (best_wal_time > after_wal_writer_delay or
            worst_wal_time > request.options.max_time_transaction_loss_allow_in_millisecond):
        _logger.warning('The WAL buffers flush time is greater than the wal_writer_delay. It is better to reduce '
                        'the WAL buffers or increase your WAL file size (to optimize clean throughput).')
    _logger.info(f'The WAL buffer (at full) flush time is estimated to be {best_wal_time:.2f} ms and '
                 f'{worst_wal_time:.2f} ms between cycle.')

    # Force enable the WAL buffers adjustment minimally to SPIDEY when the WAL disk is HDD or Network Disk
    _disk_toml_tput = LoadAppToml()['disk'][THROUGHPUT]
    if wal_tput < network_disk_performance(mode=THROUGHPUT)[1]:
        if request.options.opt_wal_buffers == PG_PROFILE_OPTMODE.NONE and \
                request.options.workload_type not in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG):
            request.options.opt_wal_buffers = PG_PROFILE_OPTMODE.SPIDEY
            _logger.warning('The WAL disk throughput is less than the maximum of network disk throughput on important '
                            'workload -> Force enable the WAL buffers adjustment to SPIDEY')

    if request.options.opt_wal_buffers is not PG_PROFILE_OPTMODE.NONE:
        match request.options.opt_wal_buffers:
            case PG_PROFILE_OPTMODE.SPIDEY:
                data_amount_ratio_input = 1
                transaction_loss_ratio = 2 / 3.25
            case PG_PROFILE_OPTMODE.OPTIMUS_PRIME:
                data_amount_ratio_input = 1.5
                transaction_loss_ratio = 1.0
            case PG_PROFILE_OPTMODE.PRIMORDIAL:
                data_amount_ratio_input = 2
                transaction_loss_ratio = 1.0
            case _:
                data_amount_ratio_input = 1
                transaction_loss_ratio = 2 / 3.25

        decay_rate = 32 * DB_PAGE_SIZE
        current_wal_buffers = int(managed_cache[wal_buffers_str])  # Ensure a new copy
        while (request.options.max_time_transaction_loss_allow_in_millisecond * transaction_loss_ratio <=
               wal_time(current_wal_buffers, data_amount_ratio_input, _kwargs.wal_segment_size,
                        after_wal_writer_delay, wal_tput)['total_time']):
            current_wal_buffers -= decay_rate
        if (wal_buffers_diff := managed_cache[wal_buffers_str] - current_wal_buffers) > 0:
            if request.options.repurpose_wal_buffers:
                request.options.tuning_kwargs.max_work_buffer_ratio += wal_buffers_diff / request.options.usable_ram_noswap
                _trigger_tuning({
                    PG_SCOPE.MEMORY: ('temp_buffers', 'work_mem'),
                    PG_SCOPE.QUERY_TUNING: ('effective_cache_size',),
                }, request, response)
            _item_tuning(key=wal_buffers_str, after=current_wal_buffers, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                         response=response, before=managed_cache[wal_buffers_str])
        wal_time_report = wal_time(current_wal_buffers, data_amount_ratio_input, _kwargs.wal_segment_size,
                                   after_wal_writer_delay, wal_tput)['msg']
        _logger.info(f'The wal_buffers is set to {bytesize_to_hr(current_wal_buffers)} with '
                     f'{request.options.opt_wal_buffers} -> {wal_time_report}')

    return None


# =============================================================================
# Tune the memory usage based on specific workload
def _get_wrk_mem_func():
    def _func_v1(options: PG_TUNE_USR_OPTIONS, response: PG_TUNE_RESPONSE):
        return response.mem_test(options, use_full_connection=True, ignore_report=True)[1]

    def _func_v2(options: PG_TUNE_USR_OPTIONS, response: PG_TUNE_RESPONSE):
        return response.mem_test(options, use_full_connection=False, ignore_report=True)[1]

    def _func_v3(options: PG_TUNE_USR_OPTIONS, response: PG_TUNE_RESPONSE):
        return (_func_v1(options, response) + _func_v2(options, response)) // 2

    return {
        PG_PROFILE_OPTMODE.SPIDEY: _func_v1,
        PG_PROFILE_OPTMODE.OPTIMUS_PRIME: _func_v3,
        PG_PROFILE_OPTMODE.PRIMORDIAL: _func_v2,
    }


def _get_wrk_mem(optmode: PG_PROFILE_OPTMODE, options: PG_TUNE_USR_OPTIONS, response: PG_TUNE_RESPONSE):
    return _get_wrk_mem_func()[optmode](options, response)


@time_decorator
def _wrk_mem_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    # Tune the shared_buffers and work_mem by boost the scale factor (we don't change heuristic connection
    # as it represented their real-world workload). Similarly, with the ratio between temp_buffers and work_mem
    # Enable extra tuning to increase the memory usage if not meet the expectation

    # Additional workload for specific workload
    keys = {
        PG_SCOPE.QUERY_TUNING: ('effective_cache_size',),
        PG_SCOPE.MAINTENANCE: ('vacuum_buffer_usage_limit',),
    }
    if request.options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG, PG_WORKLOAD.TSR_IOT):
        # Disable the additional memory tuning as these workload does not make benefits when increase the memory
        request.options.opt_mem_pool = PG_PROFILE_OPTMODE.NONE
        _logger.warning('The memory precision tuning is disabled as these workload does not bring benefit when '
                        'increase the shared_buffers due to high amount of INSERT with less SELECT. For these '
                        'workload, the shared_buffers is forced to be capped at 8 GiB for LOG workload and '
                        '16 GiB for SOLTP and TSR_IOT workload. temp_buffers and work_mem are not subjected '
                        'to be changed; Only the wal_buffers and effective_cache_size are tuned.')
        shared_buffers = 'shared_buffers'
        managed_cache = response.get_managed_cache(_TARGET_SCOPE)
        if request.options.workload_type == PG_WORKLOAD.LOG:
            _item_tuning(key=shared_buffers, after=min(managed_cache[shared_buffers], 8 * Gi), scope=PG_SCOPE.MEMORY,
                         response=response, suffix_text=f'by workload: {request.options.workload_type}')
        elif request.options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.TSR_IOT):
            _item_tuning(key=shared_buffers, after=min(managed_cache[shared_buffers], 32 * Gi), scope=PG_SCOPE.MEMORY,
                         response=response, suffix_text=f'by workload: {request.options.workload_type}')

        _trigger_tuning(keys, request, response)
        return None

    # Memory precision tuning
    if request.options.opt_mem_pool == PG_PROFILE_OPTMODE.NONE:
        _logger.info('The memory precision tuning is disabled by the user -> Skip the extra tuning')
        return None

    _logger.info('Start tuning the overall memory usage of the PostgreSQL database server. Impacted attributes: '
                 'shared_buffers, temp_buffers, work_mem, wal_buffers, effective_cache_size')
    _kwargs = request.options.tuning_kwargs
    usable_ram_noswap = request.options.usable_ram_noswap
    srv_mem_str = bytesize_to_hr(usable_ram_noswap)

    stop_point: float = _kwargs.max_normal_memory_usage
    rollback_point: float = min(stop_point + _kwargs.mem_pool_epsilon_to_rollback, 1.0)
    boost_ratio: float = _kwargs.mem_pool_tuning_increment
    keys = {
        PG_SCOPE.MEMORY: ('shared_buffers', 'temp_buffers', 'work_mem'),
        PG_SCOPE.QUERY_TUNING: ('effective_cache_size',),
        PG_SCOPE.MAINTENANCE: ('vacuum_buffer_usage_limit',),
    }

    def _show_tuning_result(first_text: str):
        texts = [first_text]
        for scope, key_itm_list in keys.items():
            m_items = response.get_managed_items(_TARGET_SCOPE, scope=scope)
            for key_itm in key_itm_list:
                texts.append(f'\n\t - {m_items[key_itm].transform_keyname()}: {m_items[key_itm].out_display()} (in '
                             f'postgresql.conf) or detailed: {m_items[key_itm].after} (in bytes).')
        _logger.info(''.join(texts))

    _show_tuning_result('Result (before): ')
    _mem_check_string = '; '.join([f'{scope}={bytesize_to_hr(func(request.options, response))}'
                                   for scope, func in _get_wrk_mem_func().items()])
    _logger.info(f'The working memory usage based on memory profile on all profiles are {_mem_check_string}.')

    # Trigger the tuning
    _logger.debug(f'Expected maximum memory usage in normal condition: {stop_point * 100:.2f} (%) of {srv_mem_str}')
    count: int = 0
    shared_buffers_ratio_increment = boost_ratio * 2.0 * _kwargs.mem_pool_tuning_ratio
    max_work_buffer_ratio_increment = boost_ratio * 2.0 * (1 - _kwargs.mem_pool_tuning_ratio)

    working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)
    working_memory_ratio = working_memory / usable_ram_noswap

    # Save state before to stop if convergent is not met
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    state = (managed_cache['shared_buffers'], managed_cache['temp_buffers'], managed_cache['work_mem'])
    while working_memory / usable_ram_noswap < stop_point:
        # Trigger the increment
        sbuf_ok = False
        wbuf_ok = False
        try:
            _kwargs.shared_buffers_ratio += shared_buffers_ratio_increment
            sbuf_ok = True
        except ValidationError as e:
            _logger.error(f'Error: The shared_buffers_ratio cannot be incremented more. \nDetail: {e}')
        try:
            _kwargs.max_work_buffer_ratio += max_work_buffer_ratio_increment
            wbuf_ok = True
        except ValidationError as e:
            _logger.error(f'Error: The two tuning keywords cannot be incremented more. Stop the auto-tuning.'
                          f'\nDetail: {e}')
        if not sbuf_ok and not wbuf_ok:
            _logger.warning('The shared_buffers and work_mem are not increased as the condition is met -> Stop ...')
            break

        _trigger_tuning(keys, request, response)
        working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)
        working_memory_ratio = working_memory / usable_ram_noswap
        _logger.debug(f'Iteration #{count}: The working memory usage based on memory profile increased to '
                      f'{bytesize_to_hr(working_memory)} or {working_memory_ratio * 100:.2f} (%) of {srv_mem_str}.')
        if working_memory_ratio >= stop_point:
            _logger.warning(f'The working memory usage is over the expected condition. Check if require rollback ...')
            if working_memory_ratio >= rollback_point:
                _logger.warning(f'The working memory usage ratio is over the expected condition by '
                                f'{(working_memory_ratio - rollback_point) * 100:.2f} (%). Requesting a rollback ...')
                if sbuf_ok:
                    _kwargs.shared_buffers_ratio -= shared_buffers_ratio_increment
                if wbuf_ok:
                    _kwargs.max_work_buffer_ratio -= max_work_buffer_ratio_increment
                _trigger_tuning(keys, request, response)
            else:
                _logger.warning(f'The working memory usage is over the expected condition but no rollback ...')
            break

        # Result verbose
        count += 1
        if count % 5 == 0:
            _show_tuning_result(f'Result (Iteration #{count}): ')

        # If we have been capped by the algorithm during the general tuning phase
        new_state = (managed_cache['shared_buffers'], managed_cache['temp_buffers'], managed_cache['work_mem'])
        if all(old == new for old, new in zip(state, new_state)):
            _logger.warning('The shared_buffers and work_mem are not increased as the convergence is met -> Stop ...')
            break

        # Iteration check
        if _kwargs.mem_pool_max_iterations == 0:
            continue
        elif count >= _kwargs.mem_pool_max_iterations:
            _logger.warning(f'The shared_buffers and work_mem are not increased as the maximum iteration '
                            f'({_kwargs.mem_pool_max_iterations}) is reached -> Stop ...')
            break

    # Result display here
    if count == 0:
        _logger.warning('The shared_buffers and work_mem are not increased due to the maximum normal memory usage '
                        'is already over the expected condition.')
    _logger.info(f'The shared_buffers and work_mem are increased by {count} iteration(s).')
    _logger.info(f'The shared_buffers_ratio is now {_kwargs.shared_buffers_ratio:.5f}.')
    _logger.info(f'The max_work_buffer_ratio is now {_kwargs.max_work_buffer_ratio:.5f}.')
    _show_tuning_result('Result (after): ')
    _mem_check_string = '; '.join([f'{scope}={bytesize_to_hr(func(request.options, response))}'
                                   for scope, func in _get_wrk_mem_func().items()])
    _logger.info(f'The working memory usage based on memory profile on all profiles are {_mem_check_string}.')

    return None


@time_decorator
def _wrk_mem_tune_final(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    # -------------------------------------------------------------------------
    # Tune the hash_mem_multiplier to use more memory.
    # TODO: I don't think hash_mem_multiplier is a good idea to tune here. It should be tuned under the while loop a
    # above, but there is not any effective way. But because not everything is hash-based operation so I think it is
    # OK then
    _logger.info('Start tuning the hash_mem_multiplier of the PostgreSQL database server based on the database '
                 'workload and working memory.')
    hash_mem_multiplier = 'hash_mem_multiplier'
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    current_work_mem = managed_cache['work_mem']

    before_working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)
    after_hash_mem_multiplier = managed_cache[hash_mem_multiplier]
    if request.options.workload_type in (PG_WORKLOAD.OLTP,):
        if current_work_mem >= 40 * Mi:
            after_hash_mem_multiplier = 2.25
    elif request.options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.TSR_HTAP, PG_WORKLOAD.SEARCH,
                                           PG_WORKLOAD.RAG, PG_WORKLOAD.GEOSPATIAL):
        if current_work_mem >= 40 * Mi:
            after_hash_mem_multiplier = 2.25
        elif current_work_mem >= 70 * Mi:
            after_hash_mem_multiplier = 2.50
        elif current_work_mem >= 100 * Mi:
            after_hash_mem_multiplier = 2.75
    elif request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE,
                                           PG_WORKLOAD.TSR_OLAP):
        if current_work_mem >= 40 * Mi:
            after_hash_mem_multiplier = 2.50
        elif current_work_mem >= 80 * Mi:
            after_hash_mem_multiplier = 2.75
        elif current_work_mem >= 120 * Mi:
            after_hash_mem_multiplier = 3.0
    else:
        _logger.info('The hash_mem_multiplier is not updated due to the workload type is not matched our experience.')

    if after_hash_mem_multiplier != managed_cache[hash_mem_multiplier]:
        _logger.warning(f'The hash_mem_multiplier is updated to {after_hash_mem_multiplier} due to the over-sized '
                        f'of the work_mem and the workload type. The keywords max_normal_memory_usage is expected to '
                        f'be bypassed, but hopefully not too much.')

    _item_tuning(key=hash_mem_multiplier, after=after_hash_mem_multiplier, scope=PG_SCOPE.MEMORY, response=response,
                 suffix_text=f'by workload: {request.options.workload_type} and working memory {current_work_mem}',
                 before=managed_cache[hash_mem_multiplier])


# =============================================================================
@time_decorator
def _logger_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    _logger.info('Start tuning the logging and query statistics on the PostgreSQL database server based on the '
                 'database workload and production guidelines. Impacted attributes: track_activity_query_size, '
                 'log_parameter_max_length, log_parameter_max_length_on_error, log_min_duration_statement, '
                 'auto_explain.log_min_duration, track_counts, track_io_timing, track_wal_io_timing, ')
    _kwargs = request.options.tuning_kwargs

    # Configure the track_activity_query_size, log_parameter_max_length, log_parameter_max_error_length
    log_length = realign_value_to_unit(_kwargs.max_query_length_in_bytes, 64)[1]
    _item_tuning(key='track_activity_query_size', after=log_length, scope=PG_SCOPE.QUERY_TUNING, response=response)
    _item_tuning(key='log_parameter_max_length', after=log_length, scope=PG_SCOPE.LOGGING, response=response)
    _item_tuning(key='log_parameter_max_length_on_error', after=log_length, scope=PG_SCOPE.LOGGING, response=response)

    # Configure the log_min_duration_statement, auto_explain.log_min_duration
    log_min_duration = realign_value_to_unit(_kwargs.max_runtime_ms_to_log_slow_query, 20)[1]
    explain_min_duration = int(log_min_duration * _kwargs.max_runtime_ratio_to_explain_slow_query)
    _item_tuning(key='log_min_duration_statement', after=log_min_duration, scope=PG_SCOPE.LOGGING, response=response)
    _item_tuning(key='auto_explain.log_min_duration', after=realign_value_to_unit(explain_min_duration, 20)[1],
                 scope=PG_SCOPE.EXTRA, response=response)

    # Tune the IO timing
    _item_tuning(key='track_counts', after='on', scope=PG_SCOPE.QUERY_TUNING, response=response)
    _item_tuning(key='track_io_timing', after='on', scope=PG_SCOPE.QUERY_TUNING, response=response)
    _item_tuning(key='track_wal_io_timing', after='on', scope=PG_SCOPE.QUERY_TUNING, response=response)
    _item_tuning(key='auto_explain.log_timing', after='on', scope=PG_SCOPE.EXTRA, response=response)
    return None


# =============================================================================
def _analyze(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    _logger.info('\n================================================================================================= '
                 '\n ### Memory Usage Estimation ###')
    response.mem_test(options=request.options, use_full_connection=True, ignore_report=False)
    response.mem_test(options=request.options, use_full_connection=False, ignore_report=False)
    _logger.info('\n================================================================================================= ')
    return None


@time_decorator
def correction_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    if not request.options.enable_database_correction_tuning:
        _logger.warning('The database correction tuning is disabled by the user -> Skip the workload tuning')
        return None

    # -------------------------------------------------------------------------
    # CPU & Statistics
    # Connection and Disk Cache Tuning
    _conn_cache_tune(request, response)

    # Query Tuning
    _query_timeout_tune(request, response)

    # -------------------------------------------------------------------------
    # Disk-based
    # Background Writer
    _bgwriter_tune(request, response)

    # Disk-based (Performance) Tuning
    _disk_tune(request, response)

    # -------------------------------------------------------------------------
    # Data Integrity Tuning
    # Write-Ahead Logging
    _wal_tune(request, response)
    _wal_size_tune(request, response)

    _wal_integrity_tune(request, response)

    # Logging Tuning
    _logger_tune(request, response)

    # -------------------------------------------------------------------------
    # Working Memory Tuning
    _wrk_mem_tune(request, response)
    _wrk_mem_tune_final(request, response)

    # -------------------------------------------------------------------------
    if not WEB_MODE:
        _analyze(request, response)
    return None
