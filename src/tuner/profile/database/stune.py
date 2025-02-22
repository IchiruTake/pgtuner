"""
This module is to perform specific tuning on the PostgreSQL database server.

"""
import logging
from math import ceil, sqrt, floor
from typing import Callable, Any

from pydantic import ValidationError

from src.static.vars import APP_NAME_UPPER, Mi, RANDOM_IOPS, K10, MINUTE, Gi, DB_PAGE_SIZE, BASE_WAL_SEGMENT_SIZE, \
    SECOND, WEB_MODE, THROUGHPUT, M10, Ki, HOUR
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.options import backup_description, PG_TUNE_USR_OPTIONS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.pg_dataclass import PG_TUNE_RESPONSE, PG_TUNE_REQUEST
from src.tuner.profile.database.shared import wal_time
from src.utils.avg import pow_avg
from src.utils.pydantic_utils import bytesize_to_hr
from src.utils.pydantic_utils import realign_value, cap_value
from src.utils.timing import time_decorator
from src.tuner.data.sizing import PG_DISK_SIZING, PG_SIZING

__all__ = ['correction_tune']
_logger = logging.getLogger(APP_NAME_UPPER)
_MIN_USER_CONN_FOR_ANALYTICS = 10
_MAX_USER_CONN_FOR_ANALYTICS = 40
_DEFAULT_WAL_SENDERS: tuple[int, int, int] = (3, 5, 7)
_TARGET_SCOPE = PGTUNER_SCOPE.DATABASE_CONFIG


def _trigger_tuning(keys: dict[PG_SCOPE, tuple[str, ...]], request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE,
                    _log_pool: list[str] | None) -> None:
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
    if isinstance(_log_pool, list):
        if change_list:
            _log_pool.append(f'The following items are updated: {change_list}')
        else:
            _log_pool.append('No change is detected in the trigger tuning.')
    return None


def _item_tuning(key: str, after: Any, scope: PG_SCOPE, response: PG_TUNE_RESPONSE,
                 _log_pool: list[str] | None, suffix_text: str = '') -> None:
    items, cache = response.get_managed_items_and_cache(_TARGET_SCOPE, scope=scope)
    if key not in items or key not in cache:
        msg = f'WARNING: The {key} is not found in the managed tuning item list, probably the scope is invalid.'
        _logger.critical(msg)
        raise KeyError(msg)

    before = cache[key]
    if isinstance(_log_pool, list):
        _log_pool.append(f'The {key} is updated from {before} (or {items[key].out_display()}) to '
                         f'{after} (or {items[key].out_display(override_value=after)}) {suffix_text}.')

    items[key].after = after
    cache[key] = after
    return None


# =============================================================================
# CPU & Statistics
@time_decorator
def _conn_cache_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]) -> None:
    _log_pool.append('Start tuning the connection, statistic caching, disk cache of the PostgreSQL database server '
                     'based on the database workload. \nImpacted Attributes: max_connections, temp_buffers, work_mem, '
                     'effective_cache_size, idle_in_transaction_session_timeout. ')
    _kwargs = request.options.tuning_kwargs
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)

    # ----------------------------------------------------------------------------------------------
    # Optimize the max_connections
    if _kwargs.user_max_connections > 0:
        _log_pool.append('The user has overridden the max_connections -> Skip the maximum tuning')
    elif request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_LAKE, PG_WORKLOAD.DATA_WAREHOUSE,
                                           PG_WORKLOAD.LOG, PG_WORKLOAD.TSR_OLAP):
        _log_pool.append('The workload type is primarily managed by the application such as full-based analytics or '
                         'logging/blob storage workload. ')

        # Find the PG_SCOPE.CONNECTION -> max_connections
        max_connections: str = 'max_connections'
        reserved_connections = managed_cache['reserved_connections'] + managed_cache['superuser_reserved_connections']
        new_result = cap_value(managed_cache[max_connections] - reserved_connections,
                               max(_MIN_USER_CONN_FOR_ANALYTICS, reserved_connections),
                               max(_MAX_USER_CONN_FOR_ANALYTICS, reserved_connections))
        _item_tuning(key=max_connections, after=new_result + reserved_connections, scope=PG_SCOPE.CONNECTION,
                     response=response, _log_pool=_log_pool)
        _trigger_tuning({
            PG_SCOPE.MEMORY: ('temp_buffers', 'work_mem'),
            PG_SCOPE.QUERY_TUNING: ('effective_cache_size',),
        }, request, response, _log_pool)
    else:
        _log_pool.append('The connection tuning is ignored due to applied workload type does not match expectation.')

    # ----------------------------------------------------------------------------------------------
    # Tune the idle_in_transaction_session_timeout -> Reduce timeout allowance when more connection
    # GitLab: https://gitlab.com/gitlab-com/gl-infra/production/-/issues/1053
    # In this example, they tune to minimize idle-in-transaction state, but we don't know its number of connections
    # so default 5 minutes and reduce 30 seconds for every 25 connections is a great start for most workloads.
    # But you can adjust this based on the workload type independently.
    idle_in_transaction_session_timeout = 'idle_in_transaction_session_timeout'
    user_connections = (managed_cache['max_connections'] - managed_cache['reserved_connections'] -
                        managed_cache['superuser_reserved_connections'])
    if user_connections > _MAX_USER_CONN_FOR_ANALYTICS:
        _tmp_user_conn = (user_connections - _MAX_USER_CONN_FOR_ANALYTICS)
        after_idle_in_transaction_session_timeout = \
            managed_cache[idle_in_transaction_session_timeout] - 30 * SECOND * (_tmp_user_conn // 25)
        _item_tuning(key=idle_in_transaction_session_timeout, after=max(31, after_idle_in_transaction_session_timeout),
                     scope=PG_SCOPE.OTHERS, response=response, _log_pool=_log_pool)

    return None


@time_decorator
def _query_timeout_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]) -> None:
    _log_pool.append('Start tuning the query timeout of the PostgreSQL database server based on the database workload. '
                     '\nImpacted Attributes: statement_timeout, lock_timeout, cpu_tuple_cost, parallel_tuple_cost, '
                     'default_statistics_target, commit_delay. ')

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
                        _log_pool=_log_pool, suffix_text=_suffix_text):
            _trigger_tuning({
                PG_SCOPE.QUERY_TUNING: ('parallel_tuple_cost',),
            }, request, response, _log_pool)

        # 3 seconds was added as the reservation for query plan before taking the lock
        new_lock_timeout = int(base_timeout * multiplier_timeout)
        new_statement_timeout = new_lock_timeout + 3
        _item_tuning(key='lock_timeout', after=new_lock_timeout, scope=PG_SCOPE.OTHERS, response=response,
                     _log_pool=_log_pool, suffix_text=_suffix_text)
        _item_tuning(key='statement_timeout', after=new_statement_timeout, scope=PG_SCOPE.OTHERS, response=response,
                     _log_pool=_log_pool, suffix_text=_suffix_text)

    # Tune the default_statistics_target
    default_statistics_target = 'default_statistics_target'
    managed_items, managed_cache = response.get_managed_items_and_cache(_TARGET_SCOPE, scope=PG_SCOPE.QUERY_TUNING)
    after_default_statistics_target = managed_cache[default_statistics_target]
    hw_scope = managed_items[default_statistics_target].hardware_scope[1]
    if request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE,
                                         PG_WORKLOAD.TSR_OLAP, PG_WORKLOAD.HTAP, PG_WORKLOAD.TSR_HTAP):
        after_default_statistics_target = 200
        if hw_scope == PG_SIZING.MEDIUM:
            after_default_statistics_target = 350
        elif hw_scope == PG_SIZING.LARGE:
            after_default_statistics_target = 500
        elif hw_scope == PG_SIZING.MALL:
            after_default_statistics_target = 750
        elif hw_scope == PG_SIZING.BIGT:
            after_default_statistics_target = 1000
    elif request.options.workload_type in (PG_WORKLOAD.OLTP, PG_WORKLOAD.SEARCH, PG_WORKLOAD.RAG,
                                           PG_WORKLOAD.GEOSPATIAL):
        if hw_scope == PG_SIZING.LARGE:
            after_default_statistics_target = 250
        elif hw_scope == PG_SIZING.MALL:
            after_default_statistics_target = 400
        elif hw_scope == PG_SIZING.BIGT:
            after_default_statistics_target = 600
    _item_tuning(key=default_statistics_target, after=after_default_statistics_target, scope=PG_SCOPE.QUERY_TUNING,
                 response=response, _log_pool=_log_pool, suffix_text=_suffix_text)

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
        # This is made during burst so we combine the calculation here
        _data_iops = request.options.data_index_spec.raid_perf()[1]
        wal_translated_iops = PG_DISK_PERF.throughput_to_iops(request.options.wal_spec.raid_perf()[0])
        mixed_iops = min(_data_iops, wal_translated_iops)

        # This is just the rough estimation so don't fall for it.
        if PG_DISK_SIZING.match_disk_series(mixed_iops, RANDOM_IOPS, 'hdd', interval='weak'):
            after_commit_delay = 3 * K10
        elif PG_DISK_SIZING.match_disk_series(mixed_iops, RANDOM_IOPS, 'hdd', interval='strong'):
            after_commit_delay = int(2.5 * K10)
        elif PG_DISK_SIZING.match_disk_series(mixed_iops, RANDOM_IOPS, 'san'):
            after_commit_delay = 2 * K10
        else:
            after_commit_delay = 1 * K10
    elif request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE,
                                           PG_WORKLOAD.TSR_OLAP):
        # Workload: OLAP, Data Warehouse, Data Lake, TSR_OLAP
        # These workloads are critical but not require end-user and internally managed and transformed by the
        # application side so a high commit_delay is allowed, but it does not bring large impact since commit_delay
        # affected group/batched commit of small transactions.
        after_commit_delay = 2 * K10
    elif request.options.workload_type in (PG_WORKLOAD.SEARCH, PG_WORKLOAD.RAG, PG_WORKLOAD.GEOSPATIAL):
        # Workload: Search, RAG, Geospatial
        # The workload pattern of this is usually READ, the indexing is added incrementally if user make new
        # or updated resources. Since update patterns are rarely done, the commit_delay still not have much
        # impact.
        after_commit_delay = int(K10 // 10 * 2.5 * (commit_delay_hw_scope.num() + 1))

    elif request.options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.TSR_HTAP, PG_WORKLOAD.OLTP):
        # Workload: HTAP, TSR_HTAP, OLTP
        # These workloads have highest and require the data integrity. Thus, the commit_delay should be set to the
        # minimum value. The higher data rate change, the burden caused on the disk is large, so we want to minimize
        # the disk impact, but hopefully we got UPS or BBU for the disk.
        after_commit_delay = K10
    _item_tuning(key=commit_delay, after=int(after_commit_delay), scope=PG_SCOPE.QUERY_TUNING, response=response,
                 _log_pool=_log_pool, suffix_text=_suffix_text)
    _item_tuning(key='commit_siblings', after=5 + 3 * managed_items['commit_siblings'].hardware_scope[1].num(),
                 scope=PG_SCOPE.QUERY_TUNING, response=response, _log_pool=_log_pool, suffix_text=_suffix_text)
    return None


# =============================================================================
# Disk-based (Performance)
@time_decorator
def _disk_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]):
    _log_pool.append('Start tuning the disk of the PostgreSQL database server based on the data disk random IOPS. '
                     '\nImpacted Attributes: random_page_cost, effective_io_concurrency, maintenance_io_concurrency')
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)

    # The WRITE operation in WAL partition is sequential, but its read (when WAL content is not flushed to the
    # datafiles) is random IOPS.  Especially during high-latency replication, unclean/unexpected shutdown, or
    # high-transaction rate, the READ operation on WAL partition is used intensively. Thus, we use the minimum
    # IOPS between the data partition and WAL partition.
    data_iops = request.options.data_index_spec.raid_perf()[1]

    # Tune the random_page_cost by converting to disk throughput, then compute its minimum
    random_page_cost = 'random_page_cost'
    before_random_page_cost = managed_cache[random_page_cost]
    if PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'hdd', interval='weak'):
        after_random_page_cost = 3.25
    elif PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'hdd', interval='strong'):
        after_random_page_cost = 2.60
    elif PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'san', interval='weak'):
        after_random_page_cost = 2.00
    elif PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'san', interval='strong'):
        after_random_page_cost = 1.50
    elif PG_DISK_SIZING.match_one_disk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv1):
        after_random_page_cost = 1.25
    elif PG_DISK_SIZING.match_one_disk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv2):
        after_random_page_cost = 1.20
    elif PG_DISK_SIZING.match_one_disk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv3):
        after_random_page_cost = 1.15
    elif PG_DISK_SIZING.match_one_disk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv4):
        after_random_page_cost = 1.10
    elif PG_DISK_SIZING.match_one_disk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.SSDv5):
        after_random_page_cost = 1.05
    else:
        after_random_page_cost = 1.01
    _item_tuning(key=random_page_cost, after=after_random_page_cost, scope=PG_SCOPE.QUERY_TUNING, response=response,
                 _log_pool=_log_pool)

    # Tune the effective_io_concurrency and maintenance_io_concurrency
    effective_io_concurrency = 'effective_io_concurrency'
    maintenance_io_concurrency = 'maintenance_io_concurrency'
    before_effective_io_concurrency = managed_cache[effective_io_concurrency]
    after_effective_io_concurrency = before_effective_io_concurrency

    before_maintenance_io_concurrency = managed_cache[maintenance_io_concurrency]
    if PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'nvmepciev5'):
        after_effective_io_concurrency = 512
    elif PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'nvmepciev4'):
        after_effective_io_concurrency = 384
    elif PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'nvmepciev3'):
        after_effective_io_concurrency = 256
    elif (PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'ssd', interval='strong') or
          PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'nvmebox')):
        after_effective_io_concurrency = 224
    elif PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'ssd', interval='weak'):
        after_effective_io_concurrency = 192
    elif PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'san', interval='strong'):
        after_effective_io_concurrency = 160
    elif PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'san', interval='weak'):
        after_effective_io_concurrency = 128
    elif PG_DISK_SIZING.match_one_disk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.HDDv3):
        after_effective_io_concurrency = 64
    elif PG_DISK_SIZING.match_one_disk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.HDDv2):
        after_effective_io_concurrency = 32
    after_maintenance_io_concurrency = max(16, after_effective_io_concurrency // 2)
    after_effective_io_concurrency = cap_value(after_effective_io_concurrency, 16, K10)
    after_maintenance_io_concurrency = cap_value(after_maintenance_io_concurrency, 16, K10)
    _item_tuning(key=effective_io_concurrency, after=after_effective_io_concurrency, scope=PG_SCOPE.OTHERS,
                 response=response, _log_pool=_log_pool)
    _item_tuning(key=maintenance_io_concurrency, after=after_maintenance_io_concurrency, scope=PG_SCOPE.OTHERS,
                 response=response, _log_pool=_log_pool)

    return None


@time_decorator
def _bgwriter_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]):
    _log_pool.append('Start tuning the background writer of the PostgreSQL database server based on the database '
                     'workload. \nImpacted Attributes: bgwriter_lru_maxpages, bgwriter_delay.')
    _kwargs = request.options.tuning_kwargs
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    _data_iops = request.options.data_index_spec.raid_perf()[1]

    # Tune the bgwriter_delay and bgwriter_lru_maxpages
    bgwriter_delay = 'bgwriter_delay'
    after_bgwriter_delay = max(100, managed_cache[bgwriter_delay] - 5 * _data_iops // int(1 * K10))
    _item_tuning(key=bgwriter_delay, after=after_bgwriter_delay, scope=PG_SCOPE.OTHERS, response=response,
                 _log_pool=_log_pool)


@time_decorator
def _vacuum_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]):
    """
    This docstring aims to describe how we tune the autovacuum. Basically, we run autovacuum more frequently, the ratio
    of dirty pages compared to total is minimized (usually between 1/8 - 1/16, average at 1/12). But if the autovacuum
    or vacuum is run rarely, the ratio becomes 1/3 or higher, and the missed page is always higher than the dirty page.
    So the page sourced from disk usually around 65-75% (average at 70%) or higher. Since PostgreSQL 12, the MISS page
    cost is set to 2, making the dominant cost of IO is at WRITE on DIRTY page.

    In the official PostgreSQL documentation, the autovacuum (or normal VACUUM) "normally only scans pages that have
    been modified since the last vacuum" due to the use of visibility map. The visibility map is a bitmap that to
    keep track of which pages contain only tuples that are known to be visible to all active transactions (and
    all future transactions, until the page is again modified). This has two purposes. First, vacuum itself can
    skip such pages on the next run. Second, it allows PostgreSQL to answer some queries using only the index,
    without reference to the underlying table --> Based on this information, the VACUUM used the random IOPS

    But here is the things I found (which you can analyze from my Excel file):
    - Frequent autovacuum has DIRTY page of 1/12 on total. DIRTY:MISS ratio is around 1/4 - 1/8
    - The DIRTY page since PostgreSQL 12 (MISS=2 for page in RAM) becomes the dominant point of cost estimation if doing
    less frequently

    Here is my disk benchmark with CrystalDiskMark 8.0.5 on 8 KiB NTFS page on Windows 10 at i7-8700H, 32GB RAM DDR4,
    1GB test file 3 runs (don't focus on the raw number, but more on ratio and disk type). I just let the number only
    and scrubbed the disk name for you to feel the value rather than reproduce your benchmark, also the number are
    relative (I have rounded some for simplicity):

    Disk Type: HDD 5400 RPM 1 TB (34% full)
    -> In HDD, large page size (randomly) can bring higher throughput but the IOPS is maintained. Queue depth or
    IO thread does not affect the story.
    -> Here the ratio is 1:40 (synthetically) so the autovacuum seems right.
    | Benchmark | READ (MiB/s -- IOPS) | WRITE (MiB/s -- IOPS) |
    | --------- | -------------------- | --------------------- |
    | Seq (1M)  | 80  -- 77            | 80 -- 75              |
    | Rand (8K) | 1.7 -- 206           | 1.9 -- 250            |
    | --------- | -------------------- | --------------------- |

    Disk Type: NVME PCIe v3x4 1 TB (10 % full, locally) HP FX900 PRO
    -> In NVME, the IOPS is high but the throughput is maintained.
    -> The ratio now is 1:2 (synthetically)
    | Benchmark         | READ (MiB/s -- IOPS) | WRITE (MiB/s -- IOPS) |
    | ----------------- | -------------------- | --------------------- |
    | Seq (1M Q8T1)     | 3,380 -- 3228.5      | 3,360 -- 3205.0       |
    | Seq (128K Q32T1)  | 3,400 -- 25983       | 3,360 -- 25671        |
    | Rand (8K Q32T16)  | 2,000 -- 244431      | 1,700 -- 207566       |
    | Rand (8K Q1T1)    | 97.60 -- 11914       | 218.9 -- 26717        |
    | ----------------- | -------------------- | --------------------- |

    Our goal are well aligned with PostgreSQL ideology: "moderately-frequent standard VACUUM runs are a better
    approach than infrequent VACUUM FULL runs for maintaining heavily-updated tables." And the autovacuum (normal
    VACUUM) or manual vacuum (which can have ANALYZE or VACUUM FULL) can hold SHARE UPDATE EXCLUSIVE lock or
    even ACCESS EXCLUSIVE lock when VACUUM FULL so we want to have SHARE UPDATE EXCLUSIVE lock more than ACCESS
    EXCLUSIVE lock (see line 2041 in src/backend/commands/vacuum.c).

    Its source code can be found at
    - Cost Determination: relation_needs_vacanalyze in src/backend/commands/autovacuum.c
    - Action Triggering for Autovacuum: autovacuum_do_vac_analyze in src/backend/commands/autovacuum.c
    - Vacuum Action: vacuum, vacuum_rel in src/backend/commands/vacuum.c
    - Vacuum Delay: vacuum_delay_point in src/backend/commands/vacuum.c
    - Table Vacuum: table_relation_vacuum in src/include/access/tableam.h --> heap_vacuum_rel in src/backend/access/heap
    /vacuumlazy.c and in here we coud see it doing the statistic report

    """
    _log_pool.append('Start tuning the autovacuum of the PostgreSQL database server based on the database workload. '
                     '\nImpacted Attributes: *_vacuum_cost_delay, vacuum_cost_page_dirty, *_vacuum_cost_limit, '
                     '*_freeze_min_age, *_failsafe_age, *_table_age ')
    _kwargs = request.options.tuning_kwargs
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    data_iops = request.options.data_index_spec.raid_perf()[1]

    # Since we are leveraging the cost-based tuning, and the *_cost_limit we have derived from the data disk IOPs,
    # thus the high value of dirty pages seems use-less and make other value difficult as based on the below thread,
    # those pages are extracted from shared_buffers (HIT) and RAM/effective_cache_size (MISS). Whilst technically,
    # the idea is to tell that dirtying the pages (DIRTY -> WRITE) is 10x dangerous. The main reason is that PostgreSQL
    # don't know about your disk hardware or capacity, so it is better to have a high cost for the dirty page.
    # But now, we acknowledge that our cost is managed under control by the data disk IOPS, we could revise the cost
    # of dirty page so as it can be running more frequently.
    #
    # On this algorithm, increase either MISS cost or DIRTY cost would allow more pages as HIT but from our perspective,
    # it is mostly useless, even the RAM is not the best as bare metal, usually at around 10 GiB/s (same as low-end
    # DDR3 or DDR2, 20x times stronger than SeqIO of SSD) (DB server are mostly virtualized or containerized),
    # but our real-world usually don't have NVME SSD for data volume due to the network bandwidth on SSD, and in the
    # database, performance can be easily improved by adding more RAM on most cases (hopefully more cache hit due to
    # RAM lacking) rather focusing on increasing the disk strength solely which is costly and not always have high
    # cost per performance improvement.
    # Thereby, we want to increase the MISS cost (as compared to HIT cost) to scale our budget, and close the gap
    # between the MISS and DIRTY cost. This is the best way to improve the autovacuum performance.
    # Meanwhile, a high cost delay would allow lower budget, and let the IO controller have time to "breathe" and flush
    # data in a timely interval, without overflowing the disk queue.

    autovacuum_vacuum_cost_delay = 'autovacuum_vacuum_cost_delay'
    vacuum_cost_page_dirty = 'vacuum_cost_page_dirty'
    after_vacuum_cost_page_miss = 3
    if PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'hdd', interval='weak'):
        after_autovacuum_vacuum_cost_delay = 15
        after_vacuum_cost_page_dirty = 15
    elif (PG_DISK_SIZING.match_one_disk(data_iops, RANDOM_IOPS, PG_DISK_SIZING.HDDv3) or
          PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'san')):
        after_autovacuum_vacuum_cost_delay = 12
        after_vacuum_cost_page_dirty = 15
    elif (PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'ssd') or
          PG_DISK_SIZING.match_disk_series(data_iops, RANDOM_IOPS, 'nvme')):
        after_autovacuum_vacuum_cost_delay = 5
        after_vacuum_cost_page_dirty = 10
    else:
        # Default fallback
        after_autovacuum_vacuum_cost_delay = 12
        after_vacuum_cost_page_dirty = 15
    _item_tuning(key='vacuum_cost_page_miss', after=after_vacuum_cost_page_miss, scope=PG_SCOPE.MAINTENANCE,
                 response=response, _log_pool=_log_pool)
    _item_tuning(key=autovacuum_vacuum_cost_delay, after=after_autovacuum_vacuum_cost_delay, scope=PG_SCOPE.MAINTENANCE,
                 response=response, _log_pool=_log_pool)
    _item_tuning(key=vacuum_cost_page_dirty, after=after_vacuum_cost_page_dirty, scope=PG_SCOPE.MAINTENANCE,
                 response=response, _log_pool=_log_pool)

    # Now we tune the vacuum_cost_limit. Don;t worry about this decay, it is just the estimation
    # P/s: If autovacuum frequently, the number of pages when MISS:DIRTY is around 4:1 to 6:1. If not, the ratio is
    # around 1.3:1 to 1:1.3.
    autovacuum_max_page_per_sec = floor(data_iops * _kwargs.autovacuum_utilization_ratio)
    if request.options.operating_system == 'windows':
        # On Windows, PostgreSQL has writes its own pg_usleep emulator, in which you can track it at
        # src/backend/port/win32/signal.c and src/port/pgsleep.c. Whilst the default is on Win32 API is 15.6 ms,
        # some older hardware and old Windows kernel observed minimally 20ms or more. But since our target database is
        # PostgreSQL 13 or later, we believe that we can have better time resolution.
        # The timing here based on emulator code is 1 ms minimum or 500 us addition
        _delay = max(1.0, after_autovacuum_vacuum_cost_delay + 0.5)
    else:
        # On Linux this seems to be smaller (10 - 50 us), when it used the nanosleep() of C functions, which
        # used this interrupt of timer_slop 50 us by default (found in src/port/pgsleep.c).
        # The time resolution is 10 - 50 us on Linux (too small value could take a lot of CPU interrupts)
        # 10 us added here to prevent some CPU fluctuation could be observed in real-life
        _delay = max(0.05, after_autovacuum_vacuum_cost_delay + 0.02)
    _delay += 0.005     # Adding 5us for the CPU interrupt and context switch
    _delay *= 1.025     # Adding 2.5% of the delay to safely reduce the number of maximum page per cycle by 2.43%
    # _delay *= 1.05      # Adding 5% of the delay to safely reduce the number of maximum page per cycle by 4.76%
    autovacuum_max_page_per_cycle = floor(autovacuum_max_page_per_sec / K10 * _delay)

    # Since I tune for auto-vacuum, it is best to stick with MISS:DIRTY ratio is 5:5:1 (5 pages reads, 1 page writes,
    # assume with even distribution). This is the best ratio for the autovacuum. If the normal vacuum is run manually,
    # usually during idle or administrative tasks, the MISS:DIRTY ratio becomes 1.3:1 ~ 1:1.3 --> 1:1
    # For manual vacuum, the MISS:DIRTY ratio becomes 1.3:1 ~ 1:1.3 --> 1:1
    # Worst Case: The database is autovacuum without cache or cold start.

    # Worst Case: every page requires WRITE on DISK rather than fetch on disk or OS page cache
    miss, dirty = 12 - _kwargs.vacuum_safety_level, _kwargs.vacuum_safety_level
    vacuum_cost_model = (managed_cache['vacuum_cost_page_miss'] * miss +
                         managed_cache['vacuum_cost_page_dirty'] * dirty) / (miss + dirty)

    # For manual VACUUM, usually only a minor of tables gets bloated, and we assume you don't do that stupid to DDoS
    # your database to overflow your disk, but we met
    after_vacuum_cost_limit = floor(autovacuum_max_page_per_cycle * vacuum_cost_model)
    after_vacuum_cost_limit = realign_value(
        after_vacuum_cost_limit,
        after_vacuum_cost_page_dirty + after_vacuum_cost_page_miss
    )[request.options.align_index]
    _item_tuning(key='vacuum_cost_limit', after=after_vacuum_cost_limit, scope=PG_SCOPE.MAINTENANCE, response=response,
                 _log_pool=_log_pool)
    # print(f'Page per Second: {autovacuum_max_page_per_sec} or {autovacuum_max_page_per_sec / data_iops * 100:.2f} (%)'
    #       f'\n-> Page per Cycle: {autovacuum_max_page_per_cycle} with delay: {_delay:.2f} ms. '
    #       f'\nCost Limit Estimation: '
    #       f'\nLow IOPS: {autovacuum_max_page_per_cycle * vacuum_cost_iops_best_v1} '
    #       f'\nAverage IOPS: {autovacuum_max_page_per_cycle * vacuum_cost_avg_iops} '
    #       f'\nHigh IOPS: {autovacuum_max_page_per_cycle * vacuum_cost_worst_iops}')
    return None


@time_decorator
def _wraparound_vacuum_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]):
    # =============================================================================
    # The dependency here is related to workload (amount of transaction), disk strength (to run wrap-around), the
    # largest table size (the amount of data to be vacuumed), and especially if the user can predict correctly
    _log_pool.append('Start tuning the autovacuum of the PostgreSQL database server based on the database workload. '
                     '\nImpacted Attributes: *_freeze_min_age, *_failsafe_age, *_table_age ')
    _kwargs = request.options.tuning_kwargs
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)

    # Use-case: We extracted the TXID use-case from the GitLab PostgreSQL database, which has the TXID of 55M per day
    # or 2.3M per hour, at some point, it has 1.4K/s on weekday (5M/h) and 600/s (2M/h) on weekend.
    # Since GitLab is a substantial large use-case, we can exploit this information to tune the autovacuum. Whilst
    # its average is 1.4K/s on weekday, but with 2.3M/h, its average WRITE time is 10.9h per day, which is 45.4% of
    # of the day, seems valid compared to 8 hours of working time in human life.
    _transaction_rate = request.options.num_write_transaction_per_hour_on_workload
    _transaction_coef = request.options.workload_profile.num()

    # Our wish is to have a better estimation of how anti-wraparound vacuum works with good enough analysis, so that
    # we can either delay or fasten the VACUUM process as our wish. Since the maximum safe cutoff point from PostgreSQL
    # is 2.0B (100M less than the theory), we would like to take our value a bit less than that (1.9B), so we can
    # have a safe margin for the future.
    # Our tuning direction is to do useful work with minimal IO and less disruptive as possible, either doing
    # frequently with minimal IO (and probably useless work, if not optimize), or doing high IO workload at stable
    # rate during emergency (but leaving headroom for the future).
    # Tune the vacuum_failsafe_age for relfrozenid, and vacuum_multixact_failsafe_age
    # Ref: https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/413
    # Ref: https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/12630

    # Data amount and disk write strength: Usually, the monitoring team would raise alert when the disk usage is at
    # 80% capacity, so we take this as the threshold. Since index does not contain xid, xmin, or xmax (and on average),
    # it takes about 20 - 30% of the table size. So assuming it is database-wide, we can assume that only 75% of data
    # needs anti-wraparound vacuum. But since, the user mostly performs READ more than WRITE, so let's assume they
    # are doing with 80% of random I/O (on idle time), but since at normal rate, usually only 10-30% of IOPS is in
    # used. This formula is only there to serve as threshold. 30% may seem large, but when disk is full (especially
    # with cache SSD or NVME SSD with pSLC, then usually the best utilization is around 30% of current IOPS for WRITE
    data_trans_tput = PG_DISK_PERF.iops_to_throughput(request.options.data_index_spec.raid_perf()[1] * 0.2)
    data_size = min(0.60 * (request.options.data_index_spec.disk_usable_size / Mi),
                    0.75 * request.options.database_size_in_gib * Ki)   # Measured in MiB
    _log_pool.append(
        f'In the worst-case scenario (our assumption is having 80% of full capacity with 30% index), the database size '
        f'could be 60% of disk capacity or 75% of your database size expectation, resulting in {data_size} MiB with '
        f'vacuum at 20% performance (around {data_trans_tput:.1f} MiB/s)'
    )
    # This is basically the worst-case scenario when 30% I/O for WRITE is used, and the database is full at
    # 80% capacity. The scale factor of 10 here is reserved for peak traffic, too long wait on disk, ...
    failsafe_hour_worst_case_theory = (data_size / data_trans_tput) / HOUR
    if request.options.workload_type in (PG_WORKLOAD.OLTP, PG_WORKLOAD.SEARCH, PG_WORKLOAD.RAG,
                                         PG_WORKLOAD.GEOSPATIAL):
        # These workload do not burst in data amount, but increase incrementally
        failsafe_hour_worst_case_practical = failsafe_hour_worst_case_theory * 5
    elif request.options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE,
                                           PG_WORKLOAD.DATA_LAKE, PG_WORKLOAD.TSR_OLAP, PG_WORKLOAD.TSR_HTAP):
        failsafe_hour_worst_case_practical = failsafe_hour_worst_case_theory * 10
    else:
        # These workload do not burst in data amount, but increase incrementally
        failsafe_hour_worst_case_practical = failsafe_hour_worst_case_theory * 3
    failsafe_hour_worst_case_practical = ceil(failsafe_hour_worst_case_practical) # Bump up to the next hour
    _log_pool.append(
        f'Our worst-case scenario for aggressive anti-wraparound vacuum is at {failsafe_hour_worst_case_theory} hours, '
        f'and for practical scenario (peak data transaction) is at {failsafe_hour_worst_case_practical} hours.'
    )

    # Maximum time of un-vacuumed table is 2B - *_min_age (by last vacuum) --> PostgreSQL introduce the *_failsafe_age
    # which is by default 80% of 2B (1.6B) to prevent the overflow of the XID. However, when overflowed at xmin or
    # xmax, only a subset of the WRITE is blocked compared to xid exhaustion which blocks all WRITE transaction.
    # See Section 24.1.5.1: Multixacts and Wraparound in PostgreSQL documentation.
    # Our perspective is that we either need to set our failsafe as low as possible (ranging as 1.4B to 1.9B), for
    # xid failsafe, and a bit higher for xmin/xmax failsafe
    _decre_xid = max(24 + (18 - _transaction_coef) * _transaction_coef, failsafe_hour_worst_case_practical)
    _decre_mxid = max(24 + (12 - _transaction_coef) * _transaction_coef, failsafe_hour_worst_case_practical // 2)
    xid_failsafe_age = max(1_900_000_000 - _transaction_rate * _decre_xid, 1_400_000_000)
    xid_failsafe_age = realign_value(xid_failsafe_age, 500 * K10)[request.options.align_index]
    mxid_failsafe_age = max(1_900_000_000 - _transaction_rate * _decre_mxid, 1_400_000_000)
    mxid_failsafe_age = realign_value(mxid_failsafe_age, 500 * K10)[request.options.align_index]
    if 'vacuum_failsafe_age' in managed_cache:
        _item_tuning(key='vacuum_failsafe_age', after=xid_failsafe_age, scope=PG_SCOPE.MAINTENANCE, response=response,
                     _log_pool=_log_pool)
    if 'vacuum_multixact_failsafe_age' in managed_cache:
        _item_tuning(key='vacuum_multixact_failsafe_age', after=mxid_failsafe_age, scope=PG_SCOPE.MAINTENANCE,
                     response=response, _log_pool=_log_pool)

    # Tune the autovacuum_*_max_age. We want the autovacuum can be run frequently to leverage the visibility map
    _decre_max_xid = max(48 + (24 - _transaction_coef) * _transaction_coef, failsafe_hour_worst_case_practical)
    _decre_max_mxid = max(36 + (20 - _transaction_coef) * _transaction_coef, failsafe_hour_worst_case_practical // 2)

    xid_max_age = max(400_000_000, 0.80 * xid_failsafe_age - _transaction_rate * _decre_max_xid)
    xid_max_age = realign_value(xid_max_age, 250 * K10)[request.options.align_index]

    mxid_max_age = max(700_000_000, 0.80 * mxid_failsafe_age - _transaction_rate * _decre_max_mxid)
    mxid_max_age = realign_value(mxid_max_age, 250 * K10)[request.options.align_index]

    _item_tuning(key='autovacuum_freeze_max_age', after=xid_max_age, scope=PG_SCOPE.MAINTENANCE, response=response,
                 _log_pool=_log_pool)
    _item_tuning(key='autovacuum_multixact_freeze_max_age', after=mxid_max_age, scope=PG_SCOPE.MAINTENANCE,
                 response=response, _log_pool=_log_pool)

    _trigger_tuning({
        PG_SCOPE.MAINTENANCE: ('vacuum_freeze_table_age', 'vacuum_multixact_freeze_table_age',)
    }, request, response, _log_pool)

    # =============================================================================
    # Tune the *_freeze_min_age high enough so that it can be stable, and allowing some newer rows to remain unfrozen.
    # These rows can be frozen later when the database is stable and operating normally.
    # One disadvantage of decreasing vacuum_freeze_min_age is that it might cause VACUUM to do useless work: freezing
    # a row version is a waste of time if the row is modified soon thereafter (causing it to acquire a new XID). So
    # the setting should be large enough that rows are not frozen until they are unlikely to change anymore.
    # Whilst it silently capped at 50%, since the maximum has been tuned for larger value, we would cap it result
    # to be lower than the maximum value.
    xid_min_age = cap_value(_transaction_rate * 24, 20 * M10,
                            managed_cache['autovacuum_freeze_max_age'] * 0.25)
    xid_min_age = realign_value(xid_min_age, 250 * K10)[request.options.align_index]
    _item_tuning(key='vacuum_freeze_min_age', after=xid_min_age, scope=PG_SCOPE.MAINTENANCE, response=response,
                 _log_pool=_log_pool)

    # For the MXID min_age, this support the row locking which is rarely met in the real-world (unless concurrent
    # analytics/warehouse workload). But usually only one instance of WRITE connection is done gracefully (except
    # concurrent Kafka stream, etc are writing during incident). Usually, unless you need the row visibility on
    # long time for transaction, this could be low (5M of xmin/xmax vs 50M of xid by default).
    # Tune the *_freeze_min_age
    multixact_min_age = cap_value(_transaction_rate * 18, 1 * M10,
                                  managed_cache['autovacuum_multixact_freeze_max_age'] * 0.25)
    multixact_min_age = realign_value(multixact_min_age, 250 * K10)[request.options.align_index]
    _item_tuning(key='vacuum_multixact_freeze_min_age', after=multixact_min_age, scope=PG_SCOPE.MAINTENANCE,
                 response=response, _log_pool=_log_pool)



# =============================================================================
# Write-Ahead Logging (WAL)
@time_decorator
def _wal_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]):
    _log_pool.append('Start tuning the WAL of the PostgreSQL database server based on the data integrity and HA '
                     'requirements. \nImpacted Attributes: wal_level, max_wal_senders, max_replication_slots, '
                     'wal_sender_timeout, log_replication_commands, synchronous_commit, full_page_writes, fsync, '
                     'logical_decoding_work_mem')

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
                 response=response, _log_pool=_log_pool)
    # Disable since it is not used
    _item_tuning(key='log_replication_commands', after='on' if managed_cache[wal_level] != 'minimal' else 'off',
                 scope=PG_SCOPE.LOGGING, response=response, _log_pool=_log_pool)
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
                 response=response, _log_pool=_log_pool)

    max_replication_slots = 'max_replication_slots'
    _item_tuning(key=max_replication_slots, after=after_max_wal_senders, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 response=response, _log_pool=_log_pool)

    # Tune the wal_sender_timeout
    if request.options.offshore_replication and managed_cache[wal_level] != 'minimal':
        wal_sender_timeout = 'wal_sender_timeout'
        after_wal_sender_timeout = max(10 * MINUTE, ceil(MINUTE * (2 + (num_replicas / 4))))
        _item_tuning(key=wal_sender_timeout, after=after_wal_sender_timeout,
                     scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response=response, _log_pool=_log_pool)

    # Tune the logical_decoding_work_mem
    if managed_cache[wal_level] != 'logical':
        _item_tuning(key='logical_decoding_work_mem', after=64 * Mi, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                     response=response, _log_pool=_log_pool)

    # -------------------------------------------------------------------------
    # Tune the synchronous_commit, full_page_writes, fsync
    _profile_optmode_level = PG_PROFILE_OPTMODE.profile_ordering()
    synchronous_commit = 'synchronous_commit'
    if request.options.opt_transaction_lost in _profile_optmode_level[1:]:
        if managed_cache[wal_level] == 'minimal':
            after_synchronous_commit = 'off'
            _log_pool.append('WARNING: The synchronous_commit is off -> If data integrity is less important to you '
                             'than response times (for example, if you are running a social networking application or '
                             'processing logs) you can turn this off, making your transaction logs asynchronous. '
                             'This can result in up to wal_buffers or wal_writer_delay * 2 (3 times on worst case) '
                             'worth of data in an unexpected shutdown, but your database will not be corrupted. Note '
                             'that you can also set this on a per-session basis, allowing you to mix “lossy” and '
                             '“safe” transactions, which is a better approach for most applications. It is '
                             'recommended to set it to local or remote_write if you do not prefer lossy transactions.')
        elif num_replicas == 0:
            after_synchronous_commit = 'local'
        else:
            # We don't reach to 'on' here: See https://postgresqlco.nf/doc/en/param/synchronous_commit/
            after_synchronous_commit = 'remote_write'
        _log_pool.append(f'WARNING: User allows the lost transaction during crash but with {managed_cache[wal_level]} '
                         f'wal_level at profile {request.options.opt_transaction_lost} but data loss could be there. '
                         f'Only enable this during testing only. ')
        _item_tuning(key=synchronous_commit, after=after_synchronous_commit,
                     scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response=response, _log_pool=_log_pool)
        if request.options.opt_transaction_lost in _profile_optmode_level[2:]:
            full_page_writes = 'full_page_writes'
            _item_tuning(key=full_page_writes, after='off', scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                         response=response, _log_pool=_log_pool)
            if request.options.opt_transaction_lost in _profile_optmode_level[3:]:
                fsync = 'fsync'
                _item_tuning(key=fsync, after='off', scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, response=response,
                             _log_pool=_log_pool)

    return None


@time_decorator
def _wal_size_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]) -> None:
    _logger.info('Start tuning the WAL size of the PostgreSQL database server based on the WAL disk sizing'
                 '\nImpacted Attributes: min_wal_size, max_wal_size, wal_keep_size, archive_timeout, '
                 'checkpoint_timeout')
    _wal_disk_size = request.options.wal_spec.disk_usable_size
    _kwargs = request.options.tuning_kwargs
    _scope = PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE
    managed_items, managed_cache = response.get_managed_items_and_cache(_TARGET_SCOPE, scope=_scope)

    # -------------------------------------------------------------------------
    # Tune the max_wal_size (This is easy to tune as it is based on the maximum WAL disk total size) to trigger
    # the CHECKPOINT process. It is usually used to handle spikes in WAL usage (when the interval between two
    # checkpoints is not met soon, and data integrity is highly preferred).
    # Ref: https://www.cybertec-postgresql.com/en/checkpoint-distance-and-amount-of-wal/
    # Two strategies:
    # 1) Tune by ratio of WAL disk size
    # 2) Tune by number of WAL files
    after_max_wal_size = cap_value(
        int(_wal_disk_size * _kwargs.max_wal_size_ratio),
        min(64 * _kwargs.wal_segment_size, 4 * Gi),
        64 * Gi
    )
    after_max_wal_size = realign_value(after_max_wal_size, 32 * _kwargs.wal_segment_size)[request.options.align_index]
    _item_tuning(key='max_wal_size', after=after_max_wal_size, scope=_scope, response=response, _log_pool=_log_pool)
    assert managed_cache['max_wal_size'] <= int(_wal_disk_size), 'The max_wal_size is greater than the WAL disk size'

    # Tune the min_wal_size as these are not specifically related to the max_wal_size. This is the top limit of the
    # WAL partition so that if the disk usage beyond the threshold (disk capacity - min_wal_size), the WAL file
    # is removed. Otherwise, the WAL file is being recycled. This is to prevent the disk full issue, but allow
    # at least a small portion to handle burst large data WRITE job(s) between CHECKPOINT interval and other unusual
    # circumstances.
    after_min_wal_size = cap_value(
        int(_wal_disk_size * _kwargs.min_wal_size_ratio),
        min(32 * _kwargs.wal_segment_size, 2 * Gi),
        int(1.05 * after_max_wal_size)
    )
    after_min_wal_size = realign_value(after_min_wal_size, 16 * _kwargs.wal_segment_size)[request.options.align_index]
    _item_tuning(key='min_wal_size', after=after_min_wal_size, scope=_scope, response=response, _log_pool=_log_pool)

    # 95% here to ensure you don't make mistake from your tuning guideline
    assert 2 * managed_cache['max_wal_size'] + managed_cache['min_wal_size'] <= int(_wal_disk_size * 0.95), \
        'The sum of min_wal_size and 2x max_wal_size is greater than the WAL disk size'

    # Tune the wal_keep_size. This parameter is there to prevent the WAL file from being removed by pg_archivecleanup
    # before the replica (for DR server, not HA server or offload READ queries purpose as it used replication slots
    # by max_slot_wal_keep_size) to catch up the data during DR server downtime, network intermittent, or other issues.
    # For proper production standard, this setup required you have a proper DBA with reliable monitoring tools to keep
    # track DR server lag time.
    # Also, keeping this value too high can cause disk to be easily full and unable to run any user transaction; and
    # if you use the DR server, this is the worst indicator
    after_wal_keep_size = cap_value(
        int(_wal_disk_size * _kwargs.wal_keep_size_ratio),
        min(32 * _kwargs.wal_segment_size, 2 * Gi),
        64 * Gi
    )
    after_wal_keep_size = realign_value(after_wal_keep_size, 16 * _kwargs.wal_segment_size)[request.options.align_index]
    _item_tuning(key='wal_keep_size', after=after_wal_keep_size, scope=_scope, response=response, _log_pool=_log_pool)
    assert managed_cache['wal_keep_size'] <= int(_wal_disk_size * 0.50), \
        'The wal_keep_size is greater than half of the WAL disk size'

    # -------------------------------------------------------------------------
    # Tune the archive_timeout based on the WAL segment size. This is easy because we want to flush the WAL
    # segment to make it have better database health
    # Tune the checkpoint timeout: This is hard to tune as it mostly depends on the amount of data change
    # (workload_profile), disk strength (IO), expected RTO.
    # In general, this is more on the DBA and business strategies. So I think the general tuning phase is good enough
    if (_wal_scale_factor := _kwargs.wal_segment_size // BASE_WAL_SEGMENT_SIZE) >= 1:
        _wal_scale_factor -= 1

        # archive_timeout: Force a switch to next WAL file after the timeout is reached. On the READ replicas
        # or during idle time, the LSN or XID don't increase so no WAL file is switched unless manually forced
        # See CheckArchiveTimeout() at line 679 of postgres/src/backend/postmaster/checkpoint.c
        archive_timeout = 'archive_timeout'
        after_archive_timeout = realign_value(
            managed_cache[archive_timeout] + int(_wal_scale_factor * managed_cache[archive_timeout] // 4),
            page_size=MINUTE // 4
        )[request.options.align_index]
        _item_tuning(key=archive_timeout, after=after_archive_timeout, scope=_scope, response=response,
                     _log_pool=_log_pool)

        # Checkpoint Timeout: Hard to tune as it mostly depends on the amount of data change, disk strength,
        # and expected RTO. For best practice, we must ensure that the checkpoint_timeout must be larger than
        # the time of reading 64 WAL files sequentially by 30% and writing those data randomly by 30%
        _wal_tput = request.options.wal_spec.raid_perf()[0] * 0.3
        _data_tput = PG_DISK_PERF.iops_to_throughput(request.options.data_index_spec.raid_perf()[1] * 0.3)
        min_ckpt_time = ceil(64 * _kwargs.wal_segment_size // Mi * (1 / _wal_tput + 1 / _data_tput))
        checkpoint_timeout = 'checkpoint_timeout'
        after_checkpoint_timeout = realign_value(
            max(managed_cache[checkpoint_timeout] + int(_wal_scale_factor * 5 * MINUTE),
                min_ckpt_time), page_size=MINUTE // 4
        )[request.options.align_index]
        _item_tuning(key=checkpoint_timeout, after=after_checkpoint_timeout, scope=_scope, response=response,
                     _log_pool=_log_pool)

    return None


@time_decorator
def _wal_integrity_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]):
    _log_pool.append('Start tuning the WAL integrity of the PostgreSQL database server based on the data integrity '
                     'and provided allowed time of data transaction loss.'
                     '\nImpacted Attributes: wal_buffers, wal_writer_delay ')
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    _kwargs = request.options.tuning_kwargs

    # Apply tune the wal_writer_delay here regardless of the synchronous_commit so that we can ensure
    # no mixed of lossy and safe transactions
    after_wal_writer_delay = int(request.options.max_time_transaction_loss_allow_in_millisecond / 3.25)
    _item_tuning(key='wal_writer_delay', after=after_wal_writer_delay, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 response=response, _log_pool=_log_pool)

    # -------------------------------------------------------------------------
    # Now we need to estimate how much time required to flush the full WAL buffers to disk (assuming we
    # have no write after the flush or wal_writer_delay is being waken up or 2x of wal_buffers are synced)
    # No low scale factor because the WAL disk is always active with one purpose only (sequential write)

    # Force enable the WAL buffers adjustment minimally to SPIDEY when the WAL disk throughput is too weak and
    # non-critical workload.
    if request.options.opt_wal_buffers == PG_PROFILE_OPTMODE.NONE:
        if request.options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG):
            _log_pool.append('WARNING: The WAL disk throughput is placed on non-critical workload with no requirements '
                             'of data loss in WAL buffers that is lower than time-based interval.')
            return None
        request.options.opt_wal_buffers = PG_PROFILE_OPTMODE.SPIDEY
        _log_pool.append('WARNING: The WAL disk throughput is enforced from NONE to SPIDEY due to important workload.')

    wal_tput = request.options.wal_spec.raid_perf()[0]
    wal_buffers_str: str = 'wal_buffers'
    current_wal_buffers = int(managed_cache[wal_buffers_str])  # Ensure a new copy

    # Just some useful information
    best_wal_time = wal_time(current_wal_buffers, 1.0, _kwargs.wal_segment_size,
                             wal_writer_delay_in_ms=after_wal_writer_delay, wal_throughput=wal_tput)['total_time']
    worst_wal_time = wal_time(current_wal_buffers, 2.0, _kwargs.wal_segment_size,
                              wal_writer_delay_in_ms=after_wal_writer_delay, wal_throughput=wal_tput)['total_time']
    _log_pool.append(f'The WAL buffer (at full) flush time is estimated to be {best_wal_time:.2f} ms and '
                     f'{worst_wal_time:.2f} ms between cycle.')
    if (best_wal_time > after_wal_writer_delay or
            worst_wal_time > request.options.max_time_transaction_loss_allow_in_millisecond):
        _log_pool.append('NOTICE: The WAL buffers flush time is greater than the wal_writer_delay or the maximum '
                         'time of transaction loss allowed. It is better to reduce the WAL buffers or increase your '
                         'WAL file size (to optimize clean throughput).')

    match request.options.opt_wal_buffers:
        case PG_PROFILE_OPTMODE.SPIDEY:
            data_amount_ratio_input = 1
            transaction_loss_ratio = 2 / 3.25   # Not 2x of delay at 1 full WAL buffers
        case PG_PROFILE_OPTMODE.OPTIMUS_PRIME:
            data_amount_ratio_input = 1.5
            transaction_loss_ratio = 3 / 3.25
        case PG_PROFILE_OPTMODE.PRIMORDIAL:
            data_amount_ratio_input = 2
            transaction_loss_ratio = 3 / 3.25
        case _:
            data_amount_ratio_input = 1
            transaction_loss_ratio = 2 / 3.25

    decay_rate = 16 * DB_PAGE_SIZE
    current_wal_buffers = int(managed_cache[wal_buffers_str])  # Ensure a new copy
    transaction_loss_time = request.options.max_time_transaction_loss_allow_in_millisecond * transaction_loss_ratio
    while transaction_loss_time <= wal_time(current_wal_buffers, data_amount_ratio_input, _kwargs.wal_segment_size,
                                            after_wal_writer_delay, wal_tput)['total_time']:
        current_wal_buffers -= decay_rate
    _item_tuning(key=wal_buffers_str, after=current_wal_buffers, scope=PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE,
                 response=response, _log_pool=_log_pool)
    wal_time_report = wal_time(current_wal_buffers, data_amount_ratio_input, _kwargs.wal_segment_size,
                               after_wal_writer_delay, wal_tput)['msg']
    _log_pool.append(f'The wal_buffers is set to {bytesize_to_hr(current_wal_buffers)} -> {wal_time_report}')
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


def _hash_mem_adjust(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    # -------------------------------------------------------------------------
    # Tune the hash_mem_multiplier to use more memory when work_mem become large enough. Integrate between the
    # iterative tuning.
    hash_mem_multiplier = 'hash_mem_multiplier'
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    current_work_mem = managed_cache['work_mem']

    after_hash_mem_multiplier = 2.0
    if request.options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.OLTP, PG_WORKLOAD.TSR_HTAP, PG_WORKLOAD.SEARCH,
                                         PG_WORKLOAD.RAG, PG_WORKLOAD.GEOSPATIAL):
        after_hash_mem_multiplier = min(2.0 + 0.125 * (current_work_mem // (40 * Mi)), 3.0)
    elif request.options.workload_type in (PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE,
                                           PG_WORKLOAD.TSR_OLAP):
        after_hash_mem_multiplier = min(2.0 + 0.150 * (current_work_mem // (40 * Mi)), 3.0)
    _item_tuning(key=hash_mem_multiplier, after=after_hash_mem_multiplier, scope=PG_SCOPE.MEMORY, response=response,
                 _log_pool=None,
                 suffix_text=f'by workload: {request.options.workload_type} and working memory {current_work_mem}')


def _wrk_mem_tune_oneshot(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str],
                          shared_buffers_ratio_increment: float, max_work_buffer_ratio_increment: float,
                          tuning_items: dict[PG_SCOPE, tuple[str, ...]]) -> tuple[bool, bool]:
    # Trigger the increment / decrement
    _kwargs = request.options.tuning_kwargs
    sbuf_ok = False
    wbuf_ok = False
    try:
        _kwargs.shared_buffers_ratio += shared_buffers_ratio_increment
        sbuf_ok = True
    except ValidationError as e:
        _log_pool.append(f'WARNING: The shared_buffers_ratio cannot be incremented more. \nDetail: {e}')
    try:
        _kwargs.max_work_buffer_ratio += max_work_buffer_ratio_increment
        wbuf_ok = True
    except ValidationError as e:
        _log_pool.append(f'WARNING: The max_work_buffer_ratio cannot be incremented more. \nDetail: {e}')

    if not sbuf_ok and not wbuf_ok:
        _log_pool.append(f'WARNING: The shared_buffers and work_mem are not increased as the condition is met '
                         f'or being unchanged, or converged -> Stop ...')
    _trigger_tuning(tuning_items, request, response, _log_pool=None)
    _hash_mem_adjust(request, response)
    return sbuf_ok, wbuf_ok


@time_decorator
def _wrk_mem_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]):
    # Tune the shared_buffers and work_mem by boost the scale factor (we don't change heuristic connection
    # as it represented their real-world workload). Similarly, with the ratio between temp_buffers and work_mem
    # Enable extra tuning to increase the memory usage if not meet the expectation.
    # Note that at this phase, we don't trigger auto-tuning from other function

    # Additional workload for specific workload
    _hash_mem_adjust(request, response) # Ensure the hash_mem adjustment is there before the tuning.
    if request.options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG, PG_WORKLOAD.TSR_IOT):
        # Disable the additional memory tuning as these workload does not make benefits when increase the memory
        request.options.opt_mem_pool = PG_PROFILE_OPTMODE.NONE
        _log_pool.append('WARNING: The memory precision tuning is disabled as these workload does not bring benefit '
                         'when increase the shared_buffers due to high amount of INSERT with less SELECT. For these '
                         'workload, the shared_buffers is forced to be capped at 8 GiB for LOG workload and 16 GiB '
                         'for SOLTP and TSR_IOT workload. temp_buffers and work_mem are not subjected to be changed; '
                         'Only the vacuum_buffer_usage_limit and effective_cache_size are tuned.')
        shared_buffers = 'shared_buffers'
        managed_cache = response.get_managed_cache(_TARGET_SCOPE)
        after_shared_buffers = managed_cache[shared_buffers]
        if request.options.workload_type == PG_WORKLOAD.LOG:
            after_shared_buffers = min(managed_cache[shared_buffers], 8 * Gi)
        elif request.options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.TSR_IOT):
            after_shared_buffers = min(managed_cache[shared_buffers], 32 * Gi)

        if after_shared_buffers != managed_cache[shared_buffers]:
            _log_pool.append(f'NOTICE: The shared_buffers is capped at {bytesize_to_hr(after_shared_buffers)} by '
                             f'workload: {request.options.workload_type}')
            _item_tuning(key=shared_buffers, after=after_shared_buffers, scope=PG_SCOPE.MEMORY, response=response,
                         _log_pool=_log_pool, suffix_text=f'by workload: {request.options.workload_type}')
            _trigger_tuning({
                PG_SCOPE.MEMORY: ('temp_buffers', 'work_mem'),
                PG_SCOPE.QUERY_TUNING: ('effective_cache_size',),
                PG_SCOPE.MAINTENANCE: ('vacuum_buffer_usage_limit',),
            }, request, response, _log_pool)
            _hash_mem_adjust(request, response)

        return None
    elif request.options.opt_mem_pool == PG_PROFILE_OPTMODE.NONE:
        _log_pool.append('WARNING: The memory pool tuning is disabled by the user -> Skip the extra tuning')
        return None

    _log_pool.append('Start tuning the memory usage based on the specific workload profile. \nImpacted attributes: '
                     'shared_buffers, temp_buffers, work_mem, vacuum_buffer_usage_limit, effective_cache_size')
    _kwargs = request.options.tuning_kwargs
    ram  = request.options.usable_ram
    srv_mem_str = bytesize_to_hr(ram)

    stop_point: float = _kwargs.max_normal_memory_usage
    rollback_point: float = min(stop_point + 0.0075, 1.0) # Small epsilon to rollback
    boost_ratio: float = 1 / 560    # Any small arbitrary number is OK (< 0.005), but not too small or too large
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
        _log_pool.append(''.join(texts))

    _show_tuning_result('Result (before): ')
    _mem_check_string = '; '.join([f'{scope}={bytesize_to_hr(func(request.options, response))}'
                                   for scope, func in _get_wrk_mem_func().items()])
    _log_pool.append(f'The working memory usage based on memory profile on all profiles are {_mem_check_string}.'
                     f'\nNOTICE: Expected maximum memory usage in normal condition: {stop_point * 100:.2f} (%) of '
                     f'{srv_mem_str} or {bytesize_to_hr(int(ram * stop_point))}.')

    # Trigger the tuning
    shared_buffers_ratio_increment = boost_ratio * 2.0 * _kwargs.mem_pool_tuning_ratio
    max_work_buffer_ratio_increment = boost_ratio * 2.0 * (1 - _kwargs.mem_pool_tuning_ratio)

    # Use ceil to gain higher bound
    managed_cache = response.get_managed_cache(_TARGET_SCOPE)
    num_conn = managed_cache['max_connections'] - managed_cache['superuser_reserved_connections'] - managed_cache['reserved_connections']
    mem_conn = num_conn * _kwargs.single_memory_connection_overhead * _kwargs.memory_connection_to_dedicated_os_ratio / ram
    active_connection_ratio = {
        PG_PROFILE_OPTMODE.SPIDEY: 1.0 / _kwargs.effective_connection_ratio,
        PG_PROFILE_OPTMODE.OPTIMUS_PRIME: (1.0 + _kwargs.effective_connection_ratio) / (2 * _kwargs.effective_connection_ratio),
        PG_PROFILE_OPTMODE.PRIMORDIAL: 1.0,
    }
    hash_mem = pow_avg(1, managed_cache['hash_mem_multiplier'], level=_kwargs.hash_mem_usage_level)
    work_mem_single = (1 - _kwargs.temp_buffers_ratio) * hash_mem
    if _kwargs.mem_pool_parallel_estimate:
        parallel_scale_nonfull = response.calc_worker_in_parallel(
            request.options,
            ceil(_kwargs.effective_connection_ratio * num_conn)
        )['work_mem_parallel_scale']
        parallel_scale_full = response.calc_worker_in_parallel(request.options, num_conn)['work_mem_parallel_scale']
        if request.options.opt_mem_pool == PG_PROFILE_OPTMODE.SPIDEY:
            TBk = _kwargs.temp_buffers_ratio + work_mem_single * parallel_scale_full
        elif request.options.opt_mem_pool == PG_PROFILE_OPTMODE.OPTIMUS_PRIME:
            TBk = _kwargs.temp_buffers_ratio + work_mem_single * (parallel_scale_full + parallel_scale_nonfull) / 2
        else:
            TBk = _kwargs.temp_buffers_ratio + work_mem_single * parallel_scale_nonfull
    else:
        TBk = _kwargs.temp_buffers_ratio + work_mem_single
    TBk *= active_connection_ratio[request.options.opt_mem_pool]

    # Interpret as below:
    A = _kwargs.shared_buffers_ratio * ram      # The original shared_buffers value
    B = shared_buffers_ratio_increment * ram    # The increment of shared_buffers
    C = max_work_buffer_ratio_increment         # The increment of max_work_buffer_ratio
    D = _kwargs.max_work_buffer_ratio           # The original max_work_buffer_ratio
    E = ram - mem_conn - A      # The current memory usage (without memory connection and original shared_buffers)
    F = TBk                     # The average working memory usage per connection
    LIMIT = stop_point * ram - mem_conn         # The limit of memory usage without static memory usage

    # Transform as quadratic function we have:
    a = C * F * (0 - B)
    b = B + F * C * E - B * D * F
    c = A + F * E * D - LIMIT
    x = ((-b + sqrt(b ** 2 - 4 * a * c)) / (2 * a))
    # print(a, b, c)
    _wrk_mem_tune_oneshot(request, response, _log_pool, shared_buffers_ratio_increment * x,
                          max_work_buffer_ratio_increment * x, tuning_items=keys)
    working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)

    _mem_check_string = '; '.join([f'{scope}={bytesize_to_hr(func(request.options, response))}'
                                   for scope, func in _get_wrk_mem_func().items()])
    _log_pool.append('---------')
    _log_pool.append(f'DEBUG: The working memory usage based on memory profile increased to {bytesize_to_hr(working_memory)} '
                     f'or {working_memory / ram * 100:.2f} (%) of {srv_mem_str} after {x} steps.')
    _log_pool.append(f'DEBUG: The working memory usage based on memory profile on all profiles are {_mem_check_string} '
                     f'after {x} steps.')

    # Now we trigger our one-step decay until we find the optimal point.
    bump_step = 0
    while working_memory < stop_point * ram:
        _wrk_mem_tune_oneshot(request, response, _log_pool, shared_buffers_ratio_increment,
                              max_work_buffer_ratio_increment, tuning_items=keys)
        working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)
        bump_step += 1

    decay_step = 0
    while working_memory >= rollback_point * ram:
        _wrk_mem_tune_oneshot(request, response, _log_pool, 0 - shared_buffers_ratio_increment,
                              0 - max_work_buffer_ratio_increment, tuning_items=keys)
        working_memory = _get_wrk_mem(request.options.opt_mem_pool, request.options, response)
        decay_step += 1

    _log_pool.append('---------')
    _log_pool.append(f'DEBUG: Optimal point is found after {bump_step} bump steps and {decay_step} decay steps')
    if bump_step + decay_step >= 3:
        _log_pool.append('DEBUG: The memory pool tuning algorithm is incorrect. Revise algorithm to be more accurate')
    _log_pool.append(f'The shared_buffers_ratio is now {_kwargs.shared_buffers_ratio:.5f}.')
    _log_pool.append(f'The max_work_buffer_ratio is now {_kwargs.max_work_buffer_ratio:.5f}.')
    _show_tuning_result('Result (after): ')
    _mem_check_string = '; '.join([f'{scope}={bytesize_to_hr(func(request.options, response))}'
                                   for scope, func in _get_wrk_mem_func().items()])
    _log_pool.append(f'The working memory usage based on memory profile on all profiles are {_mem_check_string}.')

    return None

# =============================================================================
@time_decorator
def _logger_tune(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, _log_pool: list[str]):
    _log_pool.append('Start tuning the logging and query statistics on the PostgreSQL database server based on the '
                     'database workload and production guidelines. Impacted attributes: track_activity_query_size, '
                     'log_parameter_max_length, log_parameter_max_length_on_error, log_min_duration_statement, '
                     'auto_explain.log_min_duration, track_counts, track_io_timing, track_wal_io_timing, ')
    _kwargs = request.options.tuning_kwargs

    # Configure the track_activity_query_size, log_parameter_max_length, log_parameter_max_error_length
    log_length = realign_value(_kwargs.max_query_length_in_bytes, 64)[request.options.align_index]
    _item_tuning(key='track_activity_query_size', after=log_length, scope=PG_SCOPE.QUERY_TUNING, response=response,
                 _log_pool=_log_pool)
    _item_tuning(key='log_parameter_max_length', after=log_length, scope=PG_SCOPE.LOGGING, response=response,
                 _log_pool=_log_pool)
    _item_tuning(key='log_parameter_max_length_on_error', after=log_length, scope=PG_SCOPE.LOGGING, response=response,
                 _log_pool=_log_pool)

    # Configure the log_min_duration_statement, auto_explain.log_min_duration
    log_min_duration = realign_value(_kwargs.max_runtime_ms_to_log_slow_query, 20)[request.options.align_index]
    _item_tuning(key='log_min_duration_statement', after=log_min_duration, scope=PG_SCOPE.LOGGING, response=response,
                 _log_pool=_log_pool)
    explain_min_duration = int(log_min_duration * _kwargs.max_runtime_ratio_to_explain_slow_query)
    explain_min_duration = realign_value(explain_min_duration, 20)[request.options.align_index]
    _item_tuning(key='auto_explain.log_min_duration', after=explain_min_duration, scope=PG_SCOPE.EXTRA,
                 response=response, _log_pool=_log_pool)

    # Tune the IO timing
    # _item_tuning(key='track_counts', after='on', scope=PG_SCOPE.QUERY_TUNING, response=response, _log_pool=_log_pool)
    # _item_tuning(key='track_io_timing', after='on', scope=PG_SCOPE.QUERY_TUNING, response=response,
    #              _log_pool=_log_pool)
    # _item_tuning(key='track_wal_io_timing', after='on', scope=PG_SCOPE.QUERY_TUNING, response=response,
    #              _log_pool=_log_pool)
    # _item_tuning(key='auto_explain.log_timing', after='on', scope=PG_SCOPE.EXTRA, response=response,
    #              _log_pool=_log_pool)
    return None


# =============================================================================
def _analyze(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    _logger.info('\n================================================================================================= '
                 '\n ### Memory Usage Estimation ###')
    # response.mem_test(options=request.options, use_full_connection=True, ignore_report=False)
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
    _cpu_stat_log = ['\n ===== CPU & Statistics Tuning =====']
    _conn_cache_tune(request, response, _cpu_stat_log)

    # Query Tuning
    _query_timeout_tune(request, response, _cpu_stat_log)

    if len(_cpu_stat_log) > 1:
        _logger.info('\n'.join(_cpu_stat_log))

    # -------------------------------------------------------------------------
    # Disk-based
    # Background Writer
    _disk_log = ['\n ===== Disk-based Tuning =====']
    _bgwriter_tune(request, response, _disk_log)

    # Disk-based (Performance) Tuning
    _disk_tune(request, response, _disk_log)

    # Vacuum Tuning
    _vacuum_tune(request, response, _disk_log)
    _wraparound_vacuum_tune(request, response, _disk_log)

    if len(_disk_log) > 1:
        _logger.info('\n'.join(_disk_log))

    # -------------------------------------------------------------------------
    # Data Integrity Tuning
    # Write-Ahead Logging
    _wal_log = ['\n ===== Data Integrity and Write-Ahead Log Tuning =====']
    _wal_tune(request, response, _wal_log)

    _wal_size_tune(request, response, _wal_log)

    _wal_integrity_tune(request, response, _wal_log)

    # Logging Tuning
    _logger_tune(request, response, _wal_log)

    if len(_wal_log) > 1:
        _logger.info('\n'.join(_wal_log))

    # -------------------------------------------------------------------------
    # Working Memory Tuning
    _wrk_mem_log = ['\n ===== Working Memory Tuning =====']
    _wrk_mem_tune(request, response, _wrk_mem_log)

    if len(_wrk_mem_log) > 1:
        _logger.info('\n'.join(_wrk_mem_log))

    # -------------------------------------------------------------------------
    if not WEB_MODE:
        _analyze(request, response)

    return None
