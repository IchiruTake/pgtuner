"""
This module include how the tuning items are aligned. The layout is splited between category which shared this
format:

_<Scope>_<Description>_PROFILE = {
    "<tuning_item_name>": {
        'tune_op': Callable(),          # Optional, used to define the function to calculate the value
        'default': <default_value>,     # Must have and a constant and not a function
        'comment': "<description>",     # An optional description
        'instructions': {
            "*_default": <default_value>,  # Optional, used to define the default value for each tuning profile
            "*": Callable(),               # Optional, used to define the function to calculate the value
        }

    }
}

"""

import logging
import math
from functools import partial
from math import ceil

from pydantic import ByteSize

from src.static.vars import Ki, K10, Mi, Gi, APP_NAME_UPPER, DB_PAGE_SIZE, PG_ARCHIVE_DIR, DAY, MINUTE, HOUR, \
    SECOND, PG_LOG_DIR, BASE_WAL_SEGMENT_SIZE, M10
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.pg_dataclass import PG_TUNE_RESPONSE
from src.tuner.profile.common import merge_extra_info_to_profile, type_validation
from src.utils.pydantic_utils import (bytesize_to_postgres_string, bytesize_to_postgres_unit, bytesize_to_hr,
                                      realign_value_to_unit, cap_value, )

__all__ = ['DB0_CONFIG_PROFILE', ]

_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# We don't support other value as it does not bring benefit on all cases
if DB_PAGE_SIZE != 8 * Ki:
    raise ValueError("The database page size is not 8 KiB. The PostgreSQL server do not use any page size differed "
                     "8 KiB or 8192 bytes")

# =============================================================================
# Don't change these constant
__BASE_RESERVED_DB_CONNECTION: int = 3
# This could be increased if your database server is not under hypervisor and run under Xeon_v6, recent AMD EPYC (2020)
# or powerful ARM CPU, or AMD Threadripper (2020+). But in most cases, the 4x scale factor here is enough to be
# generalized. Even on PostgreSQL 14, the scaling is significant when the PostgreSQL server is not virtualized and
# have a lot of CPU to use (> 32 - 96|128 cores).
__SCALE_FACTOR_CPU_TO_CONNECTION: int = 4
__DESCALE_FACTOR_RESERVED_DB_CONNECTION: int = 4


def __get_num_connections(
        options: PG_TUNE_USR_OPTIONS, response: PG_TUNE_RESPONSE,
        use_reserved_connection: bool = False, use_full_connection: bool = False
) -> int:
    """
    This function is used to calculate the number of connections that can be used by the PostgreSQL server. The number
    of connections is calculated based on the number of logical CPU cores available on the system and the scale factor.

    """
    managed_cache: dict = response.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG)
    try:
        total_connections: int = managed_cache['max_connections']
        reserved_connections = managed_cache['reserved_connections'] + managed_cache['superuser_reserved_connections']
    except KeyError as e:
        _logger.error(f"This function required the connection must be triggered and placed in the managed cache.")
        return -1
    if not use_reserved_connection:
        total_connections -= reserved_connections
    else:
        _logger.debug("The reserved mode is enabled (not recommended) as reserved connections are purposely different "
                      "usage such as troubleshooting, maintenance, **replication**, sharding, cluster, ...")
    if not use_full_connection:
        total_connections *= options.tuning_kwargs.effective_connection_ratio
    return ceil(total_connections)


def __get_mem_connections(
        options: PG_TUNE_USR_OPTIONS, response: PG_TUNE_RESPONSE,
        use_reserved_connection: bool = False, use_full_connection: bool = False
) -> int:
    # The memory usage per connection is varied and some articles said it could range on scale 1.5 - 14 MiB,
    # or 5 - 10 MiB so we just take this ratio. This memory is assumed to be on one connection without execute
    # any query or transaction.
    # References:
    # - https://www.cybertec-postgresql.com/en/postgresql-connection-memory-usage/
    # - https://cloud.ibm.com/docs/databases-for-postgresql?topic=databases-for-postgresql-managing-connections
    # - https://techcommunity.microsoft.com/blog/adforpostgresql/analyzing-the-limits-of-connection-scalability-in-postgres/1757266
    # - https://techcommunity.microsoft.com/blog/adforpostgresql/improving-postgres-connection-scalability-snapshots/1806462
    # Here is our conclusion:
    # - PostgreSQL apply one-process-per-connection TCP connection model, and the connection memory usage during idle
    # could be significant on small system, especially during the OLTP workload.
    # - Idle connections leads to more frequent context switches, harmful to the system with less vCPU core. And
    # degrade not only the transaction throughput but also the latency.
    num_conns: int = __get_num_connections(options, response, use_reserved_connection, use_full_connection)
    mem_conn_overhead = options.tuning_kwargs.single_memory_connection_overhead
    return int(num_conns * mem_conn_overhead)


def __shared_buffers(options: PG_TUNE_USR_OPTIONS) -> _SIZING:
    shared_buffers_ratio = options.tuning_kwargs.shared_buffers_ratio
    if shared_buffers_ratio < 0.25:
        _logger.warning('The shared_buffers_ratio is too low, which official PostgreSQL documentation recommended '
                        'the starting point is 25% of RAM or over. Please consider increasing the ratio.')

    shared_buffers: int = max(int(options.usable_ram_noswap * shared_buffers_ratio), 128 * Mi)
    if shared_buffers == 128 * Mi:
        _logger.warning('No benefit is found on tuning this variable')

    # If these two met conditions meant that your database server is hard to get any better performance
    if shared_buffers > options.usable_ram_noswap:
        _logger.error('The memory used for PostgreSQL or database would exceed the total memory.')

    # Re-align the number (always use the lower bound for memory safety) -> We can set to 32-128 pages, or
    # probably higher as when the system have much RAM, an extra 1 pages probably not a big deal
    shared_buffers = realign_value_to_unit(shared_buffers, page_size=DB_PAGE_SIZE)[options.align_index]
    _logger.debug(f'shared_buffers: {bytesize_to_hr(shared_buffers)}')
    return shared_buffers


def __temp_buffers_and_work_mem(group_cache, global_cache, options: PG_TUNE_USR_OPTIONS,
                                response: PG_TUNE_RESPONSE) -> tuple[_SIZING, _SIZING]:
    """
    There are some online documentations that gives you a generic formula for work_mem (not the temp_buffers), besides
    some general formulas. For example:
    - [25]: work_mem = (RAM - shared_buffers) / (16 * vCPU cores).
    - pgTune: work_mem = (RAM - shared_buffers) / (3 * max_connections) / max_parallel_workers_per_gather
    - Microsoft TechCommunity (*): RAM / max_connections / 16   (1/16 is conservative factors)

    Whilst these settings are good and bad, from Azure docs, "Unlike shared buffers, which are in the shared memory
    area, work_mem is allocated in a per-session or per-query private memory space. By setting an adequate work_mem
    size, you can significantly improve the efficiency of these operations and reduce the need to write temporary
    data to disk". Whilst this advice is good in general, I believe not every applications have the ability to
    change it on-the-fly due to the application design, database sizing, the number of connections and CPUs, and
    the change of data after time of usage before considering specific tuning. Unless it is under interactive
    sessions made by developers or DBA, those are not there.

    A good go-to setup way (if DB in use already) is to identify all queries and run EXPLAIN ANALYZE to calculate
    the work_mem. Pick the highest value and future-proof it with 20 - 50% depending on your data size, RAM capacity,
    or how long for your future-proofing before revise the value (obviously you will not revise it ...).

    From our rationale, when we target on first on-board database, we don't know how the application will behave
    on it wished queries, but we know its workload type, and it safeguard. So this is our solution.
    work_mem = ratio * (RAM - shared_buffers - overhead_of_os_conn) * threshold / effective_user_connections

    And then we cap it to below a 64 MiB - 1.5 GiB (depending on workload) to ensure our setup is don't
    exceed the memory usage.

    * https://techcommunity.microsoft.com/blog/adforpostgresql/optimizing-query-performance-with-work-mem/4196408

    """
    # Make minus here to correct the value and to ensure the memory is not overflow (minus shared_buffers).
    # Also, we encourage the use of not maximum of 100%, could be 99.5% instead to not overly estimate.
    # For the connection memory estimation, we assumed not all connections required work_mem, but idle connections
    # persist.
    pgmem_available = int(options.usable_ram_noswap)  # Copy the value
    pgmem_available -= int(group_cache['shared_buffers'])
    _mem_conns = __get_mem_connections(options, response, use_reserved_connection=False, use_full_connection=True)
    pgmem_available -= int(_mem_conns * options.tuning_kwargs.memory_connection_to_dedicated_os_ratio)
    if 'wal_buffers' in global_cache:
        pgmem_available -= global_cache['wal_buffers']

    max_work_buffer_ratio = options.tuning_kwargs.max_work_buffer_ratio
    active_connections: int = __get_num_connections(options, response, use_reserved_connection=False,
                                                    use_full_connection=False)
    total_buffers = int(pgmem_available * max_work_buffer_ratio) // active_connections

    # Minimum to 1 MiB and maximum is varied between workloads
    max_cap: int = 256 * Mi
    if options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG, PG_WORKLOAD.TSR_IOT):
        max_cap = 64 * Mi
    if options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.TSR_HTAP, PG_WORKLOAD.OLAP, PG_WORKLOAD.TSR_OLAP,
                                 PG_WORKLOAD.DATA_WAREHOUSE, PG_WORKLOAD.DATA_LAKE):
        # I don't think I will make risk beyond this number
        max_cap = 3 * Gi // 2

    temp_buffer_ratio = options.tuning_kwargs.temp_buffers_ratio
    temp_buffers = cap_value(int(total_buffers * temp_buffer_ratio), 1 * Mi, max_cap)
    work_mem = cap_value(int(total_buffers * (1 - temp_buffer_ratio) * options.tuning_kwargs.work_mem_scale_factor),
                         1 * Mi, max_cap)

    # Realign the number (always use the lower bound for memory safety)
    temp_buffers = realign_value_to_unit(temp_buffers, page_size=DB_PAGE_SIZE)[options.align_index]
    work_mem = realign_value_to_unit(work_mem, page_size=DB_PAGE_SIZE)[options.align_index]
    _logger.debug(f'temp_buffers: {bytesize_to_hr(temp_buffers)}')
    _logger.debug(f'work_mem: {bytesize_to_hr(work_mem)}')
    return temp_buffers, work_mem


def __temp_buffers(group_cache, global_cache, options: PG_TUNE_USR_OPTIONS,
                   response: PG_TUNE_RESPONSE) -> _SIZING:
    return __temp_buffers_and_work_mem(group_cache, global_cache, options, response)[0]


def __work_mem(group_cache, global_cache, options: PG_TUNE_USR_OPTIONS,
               response: PG_TUNE_RESPONSE) -> _SIZING:
    return __temp_buffers_and_work_mem(group_cache, global_cache, options, response)[1]


def __max_connections(options: PG_TUNE_USR_OPTIONS, group_cache: dict, min_user_conns: int, max_user_conns: int) -> int:
    total_reserved_connections: int = group_cache['reserved_connections'] + group_cache[
        'superuser_reserved_connections']
    if options.tuning_kwargs.user_max_connections != 0:
        _logger.debug('The max_connections variable is overridden by the user so no constraint here.')
        allowed_connections = options.tuning_kwargs.user_max_connections
        return allowed_connections + total_reserved_connections

    # Should I upscale here?
    # Make a small upscale here to future-proof database scaling, and reduce the number of connections
    _upscale: float = __SCALE_FACTOR_CPU_TO_CONNECTION  # / max(0.75, options.tuning_kwargs.effective_connection_ratio)
    _logger.debug(f'The max_connections variable is determined by the number of logical CPU count with the scale '
                  f'factor of {__SCALE_FACTOR_CPU_TO_CONNECTION:.1f}x.')
    _minimum = max(min_user_conns, total_reserved_connections)
    max_connections = cap_value(ceil(options.vcpu * _upscale), _minimum, max_user_conns) + total_reserved_connections
    _logger.debug(f'max_connections: {max_connections}')
    return max_connections


def __reserved_connections(options: PG_TUNE_USR_OPTIONS, minimum: int, maximum: int,
                           superuser_mode: bool = False) -> int:
    # 1.5x here is heuristically defined to limit the number of superuser reserved connections
    if not superuser_mode:
        reserved_connections: int = options.vcpu // __DESCALE_FACTOR_RESERVED_DB_CONNECTION
    else:
        superuser_heuristic_percentage = options.tuning_kwargs.superuser_reserved_connections_scale_ratio
        descale_factor = __DESCALE_FACTOR_RESERVED_DB_CONNECTION * superuser_heuristic_percentage
        reserved_connections: int = int(options.vcpu / descale_factor)
    return cap_value(reserved_connections, minimum, maximum) + __BASE_RESERVED_DB_CONNECTION


def __effective_cache_size(group_cache, global_cache, options: PG_TUNE_USR_OPTIONS,
                           response: PG_TUNE_RESPONSE) -> _SIZING:
    # The following is following the setup made by the Azure PostgreSQL team. The reason is that their tuning
    # guideline are better as compared as what I see in AWS PostgreSQL. The Azure guideline is to take the available
    # memory (RAM - shared_buffers): https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/server-parameters-table-query-tuning-planner-cost-constants?pivots=postgresql-17#effective_cache_size
    # and https://dba.stackexchange.com/questions/279348/postgresql-does-effective-cache-size-includes-shared-buffers
    # Default is half of physical RAM memory on most tuning guideline
    pgmem_available = int(options.usable_ram_noswap)
    pgmem_available -= int(global_cache['shared_buffers'])

    # Add the memory used in connection setting here.
    _mem_conns = __get_mem_connections(options, response, use_reserved_connection=False, use_full_connection=True)
    pgmem_available -= int(_mem_conns * options.tuning_kwargs.memory_connection_to_dedicated_os_ratio)
    effective_cache_size = pgmem_available * options.tuning_kwargs.effective_cache_size_available_ratio

    # Re-align the number (always use the lower bound for memory safety)
    effective_cache_size = realign_value_to_unit(effective_cache_size, page_size=DB_PAGE_SIZE)[options.align_index]
    _logger.debug(f'effective_cache_size: {bytesize_to_hr(effective_cache_size)}')
    return effective_cache_size


def __wal_buffers(group_cache, global_cache, options: PG_TUNE_USR_OPTIONS, response: PG_TUNE_RESPONSE,
                  minimum: _SIZING, maximum: _SIZING) -> _SIZING:
    # See this article https://www.cybertec-postgresql.com/en/wal_level-what-is-the-difference/
    # It is only benefit when you use COPY instead of SELECT. For other thing, the spawning of
    # WAL buffers is not necessary.
    shared_buffers = global_cache['shared_buffers']
    usable_ram_noswap = options.usable_ram_noswap
    fn = lambda x: 1024 * (37.25 * math.log(x) + 2) * 0.90  # Measure in KiB
    if shared_buffers <= 512 * Mi or usable_ram_noswap <= 4 * Gi:
        oldstyle_wal_buffers = shared_buffers // 32  # Measured in bytes
        wal_buffers = max(oldstyle_wal_buffers, fn(usable_ram_noswap / Gi) * Ki)
    else:
        wal_buffers = fn(usable_ram_noswap / Gi) * Ki  # Measured in MiB

    precision: int = DB_PAGE_SIZE
    # With low server usage, we push it to exploited 1 page of precision
    if 2.5 * Gi < usable_ram_noswap <= 4 * Gi:
        precision = 4 * DB_PAGE_SIZE
    elif 4 * Gi < usable_ram_noswap <= 6 * Gi:
        precision = 8 * DB_PAGE_SIZE
    elif 6 * Gi < usable_ram_noswap <= 8 * Gi:
        precision = 16 * DB_PAGE_SIZE
    elif 8 * Gi < usable_ram_noswap <= 16 * Gi:
        precision = 24 * DB_PAGE_SIZE
    elif usable_ram_noswap > 16 * Gi:
        precision = 32 * DB_PAGE_SIZE
    return realign_value_to_unit(cap_value(ceil(wal_buffers), minimum, maximum), page_size=precision)[options.align_index]


# =============================================================================
_DB_CONN_PROFILE = {
    # Connections
    'superuser_reserved_connections': {
        'tune_op': lambda group_cache, global_cache, options, response:
        __reserved_connections(options, 0, 10, superuser_mode=True),
        'default': __BASE_RESERVED_DB_CONNECTION,
        'comment': f"Sets the number of connections reserved for superusers. The default is {__BASE_RESERVED_DB_CONNECTION} "
                   f"plus 1/{__DESCALE_FACTOR_RESERVED_DB_CONNECTION} of logical CPU, maximum at {10 + __BASE_RESERVED_DB_CONNECTION}",
    },
    'reserved_connections': {
        'tune_op': lambda group_cache, global_cache, options, response:
        __reserved_connections(options, 0, 10, superuser_mode=False),
        'default': __BASE_RESERVED_DB_CONNECTION,
        'comment': f"Sets the number of connections reserved for users. The default is {__BASE_RESERVED_DB_CONNECTION} "
                   f"plus 1/{__DESCALE_FACTOR_RESERVED_DB_CONNECTION} of logical CPU, maximum at {10 + __BASE_RESERVED_DB_CONNECTION}.",
    },
    'max_connections': {
        'instructions': {
            'mini': lambda group_cache, global_cache, options, response: __max_connections(options, group_cache, 10,
                                                                                           50),
            'medium': lambda group_cache, global_cache, options, response: __max_connections(options, group_cache, 20,
                                                                                             65),
            'large': lambda group_cache, global_cache, options, response: __max_connections(options, group_cache, 30,
                                                                                            100),
            'mall': lambda group_cache, global_cache, options, response: __max_connections(options, group_cache, 40,
                                                                                           175),
            'bigt': lambda group_cache, global_cache, options, response: __max_connections(options, group_cache, 50,
                                                                                           250),
        },
        'default': 50,
        'comment': "The maximum number of client connections allowed. The default is 50. But by testing and some "
                   "reference, it is best to keep the number of connections limited from 3 to 4 connections per "
                   "physical CPU core. Two articles are [03-04] and [06]. The main point is to prevent un-necessary"
                   "OS context switches for idle connections (which costs 5-10 MiB of memory), thus a good timeout"
                   "model must be applied. However, we re-adjust to follow the logical CPU core here as VM and "
                   "container/pod are usually don't have physical CPU core. The 50 connections by default here "
                   "are simply good enough for you to opt for (according to OnGres) unless in a scenario where "
                   "hundred of users query the on multiple different tables, with different queries access to pages "
                   "independently with different application purposes on different data files with short "
                   "query/transaction time, then you can increase more. However, that scenario is typically rare even"
                   "even on OLTP/OLAP, Power Bi workload, and not a real-world scenario.",
    },
    'listen_addresses': {
        'default': '*',  # '127.0.0.1/32, ::1/128, 192.168.0.0/16, 172.18.0.0/12, 10.0.0.0/8, 127.0.0.0/8',
        'comment': 'Specifies the TCP/IP address(es) on which the server is to listen for connections from client '
                   'applications. The value takes the form of a comma-separated list of host names and/or numeric '
                   'IP addresses. The special entry * corresponds to all available IP interfaces. The entry 0.0.0.0 '
                   'allows listening for all IPv4 addresses and :: allows listening for all IPv6 addresses. While '
                   'client authentication (client-authentication) allows fine-grained control over who can access '
                   'the server, listen_addresses controls which interfaces accept connection attempts, which can '
                   'help prevent repeated malicious connection requests on insecure network interfaces. This '
                   'parameter can only be set at server start.'
    },
}

_DB_RESOURCE_PROFILE = {
    'shared_buffers': {
        'tune_op': lambda group_cache, global_cache, options, sys_record: __shared_buffers(options),
        'default': 128 * Mi,
        'comment': "Sets the amount of memory the database server uses for shared memory buffers. If you have a "
                   "dedicated database server with 1GB or more of RAM, a reasonable starting value for shared_buffers "
                   "is 25% of the memory in your system. There are some workloads where even larger settings for "
                   "shared_buffers are effective, but because PostgreSQL also relies on the operating system cache, "
                   "it is unlikely that an allocation of more than 40% of RAM to shared_buffers will work better than "
                   "a smaller amount. Larger settings for shared_buffers usually require a corresponding increase in "
                   "max_wal_size, in order to spread out the process of writing large quantities of new or changed data "
                   "over a longer period of time.",
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, unit=Mi)}MB',
    },
    'temp_buffers': {
        'tune_op': __temp_buffers,
        'default': 4 * Mi,
        'comment': "Sets the maximum amount of memory used for temporary buffers within each database session. These "
                   "are session-local buffers used only for access to temporary tables. A session will allocate "
                   "temporary buffers as needed up to the limit given by temp_buffers. The cost of setting a large "
                   "value in sessions that do not actually need many temporary buffers is only a buffer descriptor, "
                   "or about 64 bytes, per increment in temp_buffers. However if a buffer is actually used an "
                   "additional 8192 bytes will be consumed for it (or in general, BLCKSZ bytes). If you worked with "
                   "OLAP/HTAP or any window function or CTE results in large value, you can increase this value but "
                   "remind",
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, unit=Mi)}MB',
    },
    'work_mem': {
        'tune_op': __work_mem,
        'default': 4 * Mi,
        'comment': "Sets the base maximum amount of memory to be used by a query operation (such as a sort or hash "
                   "table) before writing to temporary disk files. If this value is specified without units, it is "
                   "taken as kilobytes. By Radiant logic, it corresponds to the size of the available memory (not "
                   "accounted OS used memory and shared_buffers) divided by the number of connections expected in "
                   "parallel. For the best value, find your greatest query returns and multiply by 1.5 of its return."
                   "For best practice, when either hash or sort such as ORDER BY, making sure it is the last value.",
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, unit=Mi)}MB',
    },
    'hash_mem_multiplier': {
        'default': 2.0,
        'comment': "Used to compute the maximum amount of memory that hash-based operations can use. The final limit is "
                   "determined by multiplying work_mem by hash_mem_multiplier. The default value is 2.0, which makes "
                   "hash-based operations use twice the usual work_mem base amount. Consider increasing this value "
                   "in environments where spilling by query operations is a regular occurrence, especially when simply "
                   "increasing work_mem results in memory pressure. The default setting of 2.0 is often effective "
                   "with mixed workloads. Higher settings in the range of 2.0 - 8.0 or more may be effective in "
                   "environments where work_mem has already been increased to 40 MiB or more. Otherwise, just increase "
                   "the work_mem value.",
    },
}

_DB_VACUUM_PROFILE = {
    # Memory and Worker
    'autovacuum': {
        'default': 'on',
        'comment': 'Enables the autovacuum daemon. The default is on. This parameter can only be set in the '
                   'postgresql.conf file or on the server command line.',
    },
    'autovacuum_naptime': {
        'instructions': {
            'mini_default': 5 * MINUTE,  # If you have too little resources and low workload also, so decrease frequency
            'small_default': 5 * MINUTE // 2,
        },
        'default': 3 * MINUTE // 2,
        'comment': "Specifies the minimum delay between autovacuum runs on any given database. In each round the "
                   "daemon examines the database and issues VACUUM and ANALYZE commands as needed for tables in that "
                   "database. If this value is specified without units, it is taken as seconds. Default is one "
                   "minute (1.5 min). Recommendation: If you have a large number of tables or database, decrease this "
                   "to 30s or 15s, or if you otherwise see from pg_stat_user_tables that autovacuum is not keeping "
                   "up. See https://www.postgresql.org/docs/17/routine-vacuuming.html for more information. If you "
                   "have a large number of databases, you may want to increase this value.",
        'partial_func': lambda value: f'{value}s',
    },
    'autovacuum_max_workers': {
        'instructions': {
            'mini_default': 1,
            'medium_default': 2,
            'large': lambda group_cache, global_cache, options, response: cap_value(options.vcpu // 4 + 1, 2, 5),
            'mall': lambda group_cache, global_cache, options, response: cap_value(int(options.vcpu / 3.5) + 1, 3, 6),
            'bigt': lambda group_cache, global_cache, options, response: cap_value(options.vcpu // 3 + 1, 3, 8),
        },
        'default': 3,
        'hardware_scope': 'cpu',
        'comment': "Specifies the maximum number of autovacuum worker processes that may be running at any one time. "
                   "The default is 3. Best options should be less than the number of CPU cores. Increase this if "
                   "you have a large number of databases and you have a lot of CPU to spare",
    },
    'maintenance_work_mem': {
        'tune_op': lambda group_cache, global_cache, options, response: realign_value_to_unit(cap_value(
            options.usable_ram_noswap // 16, 64 * Mi, 8 * Gi), page_size=DB_PAGE_SIZE)[options.align_index],
        'default': 64 * Mi,
        'hardware_scope': 'mem',
        'post-condition-group': lambda value, cache, options:
        value * cache['autovacuum_max_workers'] < int(options.usable_ram_noswap // 2),
        'comment': "Specifies the maximum amount of memory to be used by maintenance operations, such as VACUUM, CREATE "
                   "INDEX, and ALTER TABLE ADD FOREIGN KEY. Since only one of these operations can be executed at a "
                   "time by a database session, and an installation normally doesn't have many of them running "
                   "concurrently, it's safe to set this value significantly larger than work_mem. Larger settings might "
                   "improve performance for vacuuming and for restoring database dumps. Note that when autovacuum runs, "
                   "up to autovacuum_max_workers times this memory may be allocated, so be careful not to set the "
                   "default value too high. From Azure, if the task is VACUUM, the PostgreSQL implementation will only "
                   "use maximum 1 GiB (which is the same as one datafile). If the task is CREATE INDEX, the PostgreSQL "
                   "would use as much as autovacuum_work_mem with multiplier. By recommendation, it is best to keep at "
                   "around 5 - 10% of physical memory (Amazon is 25%, Azure is restrained around 97 MiB to 577 MiB, "
                   "but our is 8.33 %). This default is good enough and capped at maximum 8 GiB of RAM. "
                   "Sets the limit for the amount that autovacuum, manual vacuum, bulk index build and other "
                   "maintenance routines are permitted to use. Applications which perform large ETL operations may "
                   "need to allocate up to 1/4 of RAM to support large bulk vacuums. Note that each autovacuum "
                   "worker may use this much, so if using multiple autovacuum workers you may want to decrease this "
                   "value so that they can't claim over 1/8 or 1/4 of available RAM (our is capped at 1/3).",
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, unit=Mi)}MB',
    },
    'autovacuum_work_mem': {
        'default': -1,
        'comment': "Specifies the maximum amount of memory to be used by each autovacuum worker process. If this value "
                   "is specified without units, it is taken as kilobytes. It defaults to -1, indicating that the value "
                   "of maintenance_work_mem should be used instead. The setting has no effect on the behavior of "
                   "VACUUM when run in other contexts.",
    },
    # Threshold: For the information, I would use the [08] as the base optimization profile and could be applied
    # on most scenarios, except that you are having an extremely large table where 0.1% is too large.
    'autovacuum_vacuum_threshold': {
        'instructions': {
            'mini_default': 200,
            'bigt_default': 3 * K10,
        },
        'hardware_scope': 'overall',
        'default': K10,
        'comment': "Specifies the minimum number of updated or deleted tuples needed to trigger a VACUUM in any one "
                   "table. Default is 1000 tuples and 1K-3K tuples on a larger system.",
    },
    'autovacuum_vacuum_scale_factor': {
        'instructions': {
            'mini_default': 0.0250,
            'mall_default': 0.0050,
            'bigt_default': 0.0025,
        },
        'hardware_scope': 'overall',
        'default': 0.0125,
        'comment': 'Specifies a fraction of the table size to add to autovacuum_vacuum_threshold when deciding whether '
                   'to trigger a VACUUM. Default is 0.0125 (or 1.25%, or 1/80); and can be reduced to 0.25% on an '
                   'extreme large system',
    },
    'autovacuum_vacuum_insert_threshold; autovacuum_analyze_threshold': {
        'instructions': {
            'mini_default': 200,
            'mall_default': 2 * K10,
            'bigt_default': 5 * K10,
        },
        'hardware_scope': 'overall',
        'default': K10,
        'comment': "Specifies the minimum number of inserted tuples needed to trigger a VACUUM in any one table. "
                   "or the minimum number of inserted, updated or deleted tuples needed to trigger an ANALYZE "
                   "in any one table. Default is 1000 tuples and 2K-5K tuples on a larger system. This is twice "
                   "compared to the normal VACUUM/ANALYZE since UPDATE/DELETE cause data bloating and index "
                   "fragmentation more.",
    },
    'autovacuum_vacuum_insert_scale_factor; autovacuum_analyze_scale_factor': {
        'instructions': {
            'mini_default': 0.050,
            'mall_default': 0.010,
            'bigt_default': 0.005,
        },
        'hardware_scope': 'overall',
        'default': 0.025,
        'comment': "Specifies a fraction of the table size to add to autovacuum_vacuum_insert_threshold when deciding "
                   "whether to trigger a VACUUM or ANALYZE. Default is 0.025 (or 2.5%, or 1/40); and can be reduced "
                   "to 0.5% on an extreme large system. This is twice compared to the normal VACUUM/ANALYZE as it cause "
                   "less data bloating and index fragmentation.",
    },
    # Cost Delay, Limit, and Naptime (Naptime would not be changed)
    'autovacuum_vacuum_cost_delay': {
        'default': 2,
        'comment': "Specifies the cost delay value that will be used in automatic VACUUM operations. If -1 is "
                   "specified, the regular vacuum_cost_delay value will be used. The default value is 2 milliseconds "
                   "to follow the official PostgreSQL documentation. With 2ms value, it meant that the wake-up "
                   "operation costs 2ms, resulting in a 500 wake-up per second. See [10] for more information. We "
                   "want auto-vacuum behave same with manual vacuum but different delay.",
        'partial_func': lambda value: f'{value}ms' if isinstance(value, int) else f'{value:.4f}ms',
    },
    'autovacuum_vacuum_cost_limit': {
        'default': -1,
        'comment': "Specifies the cost limit value that will be used in automatic VACUUM operations. If -1 is specified "
                   "(which is the default), the regular vacuum_cost_limit value will be used. Note that the value is "
                   "distributed proportionally among the running autovacuum workers, if there is more than one, so that "
                   "the sum of the limits for each worker does not exceed the value of this variable. In our tuning"
                   "model, we would focus on the vacuum_cost_limit instead.",
    },
    'vacuum_cost_delay': {
        'default': 0,
        'comment': "The amount of time that the process will sleep when the cost limit has been exceeded. If this value "
                   "is specified without units, it is taken as milliseconds. The default value is zero, which disables "
                   "the cost-based vacuum delay feature. Positive values enable cost-based vacuuming. When using "
                   "cost-based vacuuming, appropriate values for vacuum_cost_delay are usually quite small, perhaps "
                   "less than 1 millisecond. While vacuum_cost_delay can be set to fractional-millisecond values, such "
                   "delays may not be measured accurately on older platforms. Most of the time, you will want manual "
                   "vacuum to execute without vacuum_delay, especially if you're using it as part of ETL. If for some "
                   "reason you can't use autovacuum on an OLTP database, however, you may want to increase this to "
                   "20ms to decrease the impact vacuum has on currently running queries. Will cause vacuum to take up "
                   "to twice as long to complete. In our tuning model, we want to let autovacuum to do everything "
                   "unless something is wrong. Supported range is 0 and 100 ms.",
        'partial_func': lambda value: f'{value}ms' if isinstance(value, int) else f'{value:.4f}ms',
    },
    'vacuum_cost_limit': {
        'instructions': {
            'large_default': 500,
            'mall_default': K10,
            'bigt_default': K10,
        },
        'default': 200,
        'comment': 'The cost limit value that will be used in vacuum operations. If -1 is specified, the regular '
                   'vacuum_cost_limit value will be used. We set the default value to 500 for normal server, 10K '
                   'for large server, and 1K for mini server. This default is genuinely good enough unless you work '
                   'on the HDD disk. The cost limit is used to determine the maximum disk/memory throughput when to '
                   'start the cost-based vacuum delay to prevent throttle. If you have much RAM and using SSD, '
                   'increase this factor can make the vacuum faster, but only at maximum to the shared_buffers size. '
                   'Supported range is 0 and 10000. However, on different version, the cost on buffer_hit, '
                   'buffer_miss, and dirty_page are different.',
        'partial_func': lambda value: f'{value}',
    },
    'vacuum_cost_page_hit': {
        'default': 1,
        'hardware_scope': 'mem',
        'comment': "The cost of a page found in the buffer cache. The default value is 1. This value is used to "
                   "determine the cost of a page hit in the buffer cache. The cost of a page hit is added to the total "
                   "cost of a vacuum operation.",
    },
    'vacuum_cost_page_miss': {
        'default': 2,
        'comment': "The cost of a page not found in the buffer cache. The default value is 2 (followed by PostgreSQL "
                   "14+). This value is used to determine the cost of a page miss in the buffer cache. The cost of a "
                   "page miss is added to the total cost of a vacuum operation.",
    },
    'vacuum_cost_page_dirty': {
        'default': 20,
        'comment': "The cost of a page that is dirty. The default value is 20. This value is used to determine "
                   "the cost of a dirty page in the buffer cache. The cost of a dirty page is added to the total "
                   "cost of a vacuum operation.",
    },
    # Transaction ID and MultiXact
    'autovacuum_freeze_max_age': {
        # See here: https://postgresqlco.nf/doc/en/param/autovacuum_freeze_max_age/
        # And https://www.youtube.com/watch?v=vtjjaEVPAb8 at (30:02)
        'default': 500 * M10,
        'comment': "Specifies the maximum age (in transactions) that a table's pg_class.relfrozenxid field can attain "
                   "before a VACUUM operation is forced to prevent transaction ID wraparound within the table. Note "
                   "that the system will launch autovacuum processes to prevent wraparound even when autovacuum is "
                   "otherwise disabled. Vacuum also allows removal of old files from the pg_xact subdirectory, which "
                   "is why the default is a relatively low 200 million transactions."
    },
    'vacuum_freeze_table_age': {
        'tune_op': lambda group_cache, global_cache, options, response:
            realign_value_to_unit(int(group_cache['autovacuum_freeze_max_age'] * 0.80),
                                  page_size=M10)[options.align_index],
        'default': 150 * M10,
        'comment': "VACUUM performs an aggressive scan if the table's pg_class.relfrozenxid field has reached the age "
                   "specified by this setting. An aggressive scan differs from a regular VACUUM in that it visits every "
                   "page that might contain unfrozen XIDs or MXIDs, not just those that might contain dead tuples. The "
                   "default is 150 million transactions. "
    },
    'vacuum_freeze_min_age': {
        'default': 50 * M10,
        'comment': "Specifies the cutoff age (in transactions) that VACUUM should use to decide whether to trigger "
                   "freezing of pages that have an older XID. The default is 50 million transactions."
    },

    'autovacuum_multixact_freeze_max_age': {
        'default': 850 * M10,
        'comment': "Specifies the maximum age (in multixacts) that a table's pg_class.relminmxid field can attain "
                   "before a VACUUM operation is forced to prevent multixact ID wraparound within the table. Note "
                   "that the system will launch autovacuum processes to prevent wraparound even when autovacuum is "
                   "otherwise disabled. Vacuuming multixacts also allows removal of old files from the "
                   "pg_multixact/members and pg_multixact/offsets subdirectories, which is why the default is a "
                   "relatively low 400 million multixacts. "
    },
    'vacuum_multixact_freeze_table_age': {
        'tune_op': lambda group_cache, global_cache, options, response:
            realign_value_to_unit(int(group_cache['autovacuum_multixact_freeze_max_age'] * 0.80),
                                  page_size=M10)[options.align_index],
        'default': 150 * M10,
        'comment': "VACUUM performs an aggressive scan if the table's pg_class.relminmxid field has reached the age "
                   "specified by this setting. An aggressive scan differs from a regular VACUUM in that it visits "
                   "every page that might contain unfrozen XIDs or MXIDs, not just those that might contain dead "
                   "tuples. The default is 150 million multixacts. Although users can set this value anywhere from "
                   "zero to two billion, VACUUM will silently limit the effective value to 95% of "
                   "autovacuum_multixact_freeze_max_age, so that a periodic manual VACUUM has a chance to run before "
                   "an anti-wraparound is launched for the table"
    },
    'vacuum_multixact_freeze_min_age': {
        'default': 5 * M10,
        'comment': "Specifies the cutoff age (in multixacts) that VACUUM should use to decide whether to trigger "
                   "freezing of pages with an older multixact ID. The default is 5 million multixacts. "
    },

}

_DB_BGWRITER_PROFILE = {
    # We don't tune the bgwriter_flush_after = 512 KiB as it is already optimal and PostgreSQL said we don't need
    # to tune it
    'bgwriter_delay': {
        'instructions': {
            'mini_default': 5 * K10,  # Make it big as we don't need actually a lot of write here
            'medium_default': 500,
            'mall_default': 150,
            'bigt_default': 100,
        },
        'default': 200,
        'hardware_scope': 'overall',
        'comment': "Specifies the delay between activity rounds for the background writer. In each round the writer "
                   "issues writes for some number of dirty buffers (controllable by the following parameters). It "
                   "then sleeps for the length of :var:`bgwriter_delay`, and repeats. When there are no dirty buffers "
                   "in the buffer pool, though, it goes into a longer sleep regardless of :var:`bgwriter_delay`. "
                   "Default value is 200 milliseconds (200ms) on large server and 0.5 - 5 second on small server",
        'partial_func': lambda value: f"{value}ms",
    },
    'bgwriter_lru_maxpages': {
        'instructions': {
            'mall_default': 400,
            'bigt_default': 500,
        },
        'default': 300,
        'comment': "In each round, no more than this many buffers will be written by the background writer. Setting "
                   "this to zero disables background writing. (Note that checkpoints, which are managed by a separate, "
                   "dedicated auxiliary process, are unaffected.) The default value is 300 pages but it would be "
                   "changed based on your data disk IOPs. On strong servers, especially with SSD, we can have "
                   "a stronger write here.",
    },
    'bgwriter_lru_multiplier': {
        'default': 2.0,
        'comment': "The number of dirty buffers written in each round is based on the number of new buffers that have "
                   "been needed by server processes during recent rounds. The average recent need is multiplied by "
                   "bgwriter_lru_multiplier to arrive at an estimate of the number of buffers that will be needed "
                   "during the next round. Dirty buffers are written until there are that many clean, reusable "
                   "buffers available. (However, no more than bgwriter_lru_maxpages buffers will be written per "
                   "round.) Thus, a setting of 1.0 represents a “just in time” policy of writing exactly the number "
                   "of buffers predicted to be needed. Larger values provide some cushion against spikes in demand, "
                   "while smaller values intentionally leave writes to be done by server processes. The default "
                   "is 2.0.",
    },
    'bgwriter_flush_after': {
        'default': 512 * Ki,
        'comment': "Whenever more than this amount of data has been written by the background writer, attempt to "
                   "force the OS to issue these writes to the underlying storage. Doing so will limit the amount of "
                   "dirty data in the kernel's page cache, reducing the likelihood of stalls when an fsync is issued "
                   "at the end of a checkpoint, or when the OS writes data back in larger batches in the background. "
                   "Often that will result in greatly reduced transaction latency, but there also are some cases, "
                   "especially with workloads that are bigger than shared_buffers, but smaller than the OS's page "
                   "cache, where performance might degrade.",
        'partial_func': lambda value: f"{bytesize_to_postgres_unit(value, unit=Ki)}kB",
    },
}

_DB_ASYNC_DISK_PROFILE = {
    'effective_io_concurrency': {
        'default': 16,
        'comment': "Sets the number of concurrent disk I/O operations that PostgreSQL expects can be executed "
                   "simultaneously. Raising this value will increase the number of I/O operations that any individual "
                   "PostgreSQL session attempts to initiate in parallel. The allowed range is 1 to 1000, or zero to "
                   "disable issuance of asynchronous I/O requests. Currently, this setting only affects bitmap heap "
                   "scans. For magnetic drives, a good starting point for this setting is the number of separate "
                   "drives comprising a RAID 0 stripe or RAID 1 mirror being used for the database. A value higher "
                   "than needed to keep the disks busy will only result in extra CPU overhead. SSDs and other "
                   "memory-based storage can often process many concurrent requests, so the best value might be in "
                   "the hundreds. However, a search on PostgreSQL issue at reference [30-32] showing that even a "
                   "higher value can bring more benefit with due to the cheaper prefetch operation even on HDD. "
                   "However, it is strongly related to the disk controller and queue length. For your concern, we set "
                   "the default value is 16 on HDD and 128 for SATA SSD (legacy). For a more modern SATA SSD, a good "
                   "setting is 192 or 256 (up to the queue length). For NVMe PCIe v3+ SSD, a good default setting is "
                   "512 or above (but it is limited by PostgreSQL constraint). If you think these values are bad "
                   "during bitmap heap scan, disable it by setting it to 0. Note that this parameter is only beneficial "
                   "for the bitmap heap scan and not a big gamechanger. ",
    },
    'maintenance_io_concurrency': {
        'default': 10,
        'comment': "Similar to :var:`effective_io_concurrency`, but used for maintenance work that is done on behalf "
                   "of many client sessions. The default is 10 on supported systems, otherwise 0. During maintenance, "
                   "since the operation is mostly involved in sequential disk read and write during vacuuming and "
                   "index creation; thus, increasing this value may not benefit much.",
    },
}

_DB_ASYNC_CPU_PROFILE = {
    'max_worker_processes': {
        'tune_op': lambda group_cache, global_cache, options, response:
        cap_value(int(options.vcpu * 1.5) + 2, 4, 512),
        'default': 8,
        'comment': 'Sets the maximum number of background processes that the system can support. The supported range '
                   'is [4, 512], with default to 1.5x + 2 of the logical CPU count (8 by official documentation). We do '
                   'not have intention on the worst case with > 128 vCPU for PostgreSQL since beyond that, the '
                   'benefit gained is quite minimal due to OS context switching.',
    },
    'max_parallel_workers': {
        'tune_op': lambda group_cache, global_cache, options, response:
        min(cap_value(int(options.vcpu * 1.125), 4, 512), group_cache['max_worker_processes']),
        'default': 8,
        'comment': 'Sets the maximum number of workers that the cluster can support for parallel operations. The '
                   'supported range is [4, 512], with default to 1.125x of the logical CPU count (8 by official '
                   'documentation). When increasing or decreasing this value, consider also adjusting '
                   'max_parallel_maintenance_workers and max_parallel_workers_per_gather. Also, note that these '
                   'workers are retrieved from max_parallel_workers so higher value than max_worker_processes will '
                   'have no effect. See Ref [05] for more information.',
    },
    'max_parallel_workers_per_gather': {
        'tune_op': lambda group_cache, global_cache, options, response:
        min(cap_value(int(options.vcpu // 3), 2, 32), group_cache['max_parallel_workers']),
        'default': 2,
        'comment': 'Sets the maximum number of workers that can be started by a single Gather or Gather Merge node. '
                   'Parallel workers are taken from the pool of processes established by max_worker_processes, limited '
                   'by max_parallel_workers. However, there are no guarantee from Ref video [33] saying that increase '
                   'more is better due to the algorithm, lock contention and memory usage. Thus by TimescaleDB, it is '
                   'best to keep it below 1/2 of number of CPUs or 1/2 of max_parallel_workers to allow at least 2 '
                   '*Gather* queries to be run. The supported range is [2, 32], with default to 1/3x of the logical '
                   'CPU count (2 by official documentation).',
    },

    'max_parallel_maintenance_workers': {
        'tune_op': lambda group_cache, global_cache, options, response:
        min(cap_value(int(options.vcpu // 2), 2, 32), group_cache['max_parallel_workers']),
        'default': 2,
        'comment': "Sets the maximum number of parallel workers that can be started by a single utility command. "
                   "Currently, the parallel utility commands that support the use of parallel workers are CREATE INDEX "
                   "only when building a B-tree index, and VACUUM without FULL option. Parallel workers are taken from "
                   "the pool of processes established by max_worker_processes, limited by max_parallel_workers. Note "
                   "that the requested number of workers may not actually be available at run time. If this occurs, "
                   "the utility operation will run with fewer workers than expected. The default value is 2. Note that "
                   "parallel utility commands should not consume substantially more memory than equivalent non-parallel "
                   "operations. This strategy differs from that of parallel query, where resource limits generally "
                   "apply per worker process. Parallel utility commands treat the resource limit maintenance_work_mem "
                   "as a limit to be applied to the entire utility command, regardless of the number of parallel worker "
                   "processes. However, parallel utility commands may still consume substantially more CPU resources "
                   "and I/O bandwidth. The supported range is [2, 16], with default to 1/2x of the logical CPU count "
                   "(2 by official documentation). See Ref [05] for more information.",
    },
    'min_parallel_table_scan_size': {
        'instructions': {
            "medium_default": 16 * Mi,
            "large_default": 24 * Mi,
            "mall_default": 32 * Mi,
            "bigt_default": 32 * Mi,
        },
        'default': 8 * Mi,
        'comment': "Sets the minimum amount of table data that must be scanned in order for a parallel scan to be "
                   "considered. For a parallel sequential scan, the amount of table data scanned is always equal to "
                   "the size of the table, but when indexes are used the amount of table data scanned will normally "
                   "be less. The default is 8 megabytes (8MB). But you can see the 'driving' rule in video [34] to "
                   "benefit better when your server is large. This variable is set to ensure that the parallel scan"
                   "query plan only benefit with table or index with this size or larger.",
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, unit=Mi)}MB',
    },
    'min_parallel_index_scan_size': {
        'tune_op': lambda group_cache, global_cache, options, response:
        max(group_cache['min_parallel_table_scan_size'] // 16, 512 * Ki),
        'default': 512 * Ki,
        'comment': "Sets the minimum amount of index data that must be scanned in order for a parallel scan to be "
                   "considered. Note that a parallel index scan typically won't touch the entire index; it is the "
                   "number of pages which the planner believes will actually be touched by the scan which is relevant. "
                   "This variable is set to be the maximum of 1/16 of min_parallel_table_scan_size or 512 KiB (by "
                   "default of official PostgreSQL documentation).",
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, unit=Ki)}kB',
    },
}

_DB_WAL_PROFILE = {
    # ============================== WAL ==============================
    # For these settings, please refer to the [13] and [14] for more information
    'wal_level': {
        'default': 'replica',
        'comment': "wal_level determines how much information is written to the WAL. The default value is "
                   ":enum:`replica`, which writes enough data to support WAL archiving and replication, including "
                   "running read-only queries on a standby server. :enum:`minimal` removes all logging except the "
                   "information required to recover from a crash or immediate shutdown. Finally, :enum:`logical` adds "
                   "information necessary to support logical decoding."
    },
    'synchronous_commit': {
        'default': 'on',
        'comment': 'Specifies how much WAL processing must complete before the database server returns a “success” '
                   'indication to the client. Valid values are :enum:`remote_apply`, :enum:`on` (the default), '
                   'enum:`remote_write`, :enum:`local`, and :enum:`off`.'
    },
    'full_page_writes': {
        'default': 'on',
        'comment': 'When this parameter is on, the PostgreSQL server writes the entire content of each disk page to '
                   'WAL during the first modification of that page after a checkpoint. This is needed because a page '
                   'write that is in process during an operating system crash might be only partially completed, '
                   'leading to an on-disk page that contains a mix of old and new data. The row-level change data '
                   'normally stored in WAL will not be enough to completely restore such a page during post-crash '
                   'recovery. Storing the full page image guarantees that the page can be correctly restored, but at '
                   'the price of increasing the amount of data that must be written to WAL. (Because WAL replay always '
                   'starts from a checkpoint, it is sufficient to do this during the first change of each page after a '
                   'checkpoint. Therefore, one way to reduce the cost of full-page writes is to increase the checkpoint '
                   'interval parameters.)',
    },
    'fsync': {
        'default': 'on',
        'comment': 'If this parameter is on, the PostgreSQL server will try to make sure that updates are physically '
                   'written to disk, by issuing fsync() system calls or equivalent methods at :var:`wal_sync_method`). '
                   'This ensures that the database cluster can recover to a consistent state after an operating system '
                   'or hardware crash. While turning off fsync is often a performance benefit, this can result in '
                   'unrecoverable data corruption in the event of a power failure or system crash. Thus it is only '
                   'advisable to turn off fsync if you can easily recreate your entire database from external data. '
                   'Examples of safe circumstances for turning off fsync include the initial loading of a new database '
                   'cluster from a backup file, using a database cluster for processing a batch of data after which the '
                   'database will be thrown away and recreated, or for a read-only database clone which gets recreated '
                   'frequently and is not used for failover. High quality hardware alone is not a sufficient '
                   'justification for turning off fsync. For reliable recovery when changing fsync off to on, it is '
                   'necessary to force all modified buffers in the kernel to durable storage. This can be done while '
                   'the cluster is shutdown or while fsync is on by running initdb --sync-only, running sync, '
                   'unmounting the file system, or rebooting the server. In many situations, turning off '
                   ':var:`synchronous_commit` for noncritical transactions can provide much of the potential '
                   'performance benefit of turning off fsync, without the attendant risks of data corruption.'
    },
    'wal_compression': {
        'default': 'pglz',
        'comment': 'This parameter enables compression of WAL using the specified compression method. When enabled, '
                   'the PostgreSQL server compresses full page images written to WAL when full_page_writes is on or '
                   'during a base backup. A compressed page image will be decompressed during WAL replay.'
    },
    'wal_init_zero': {
        'default': 'on',
        'comment': 'If this parameter is on (default), the PostgreSQL server will initialize new WAL files with zeros. '
                   'On some file systems, this ensures that space is allocated before we need to write WAL records. '
                   'However, Copy-On-Write (COW) file systems may not benefit from this technique, so the option is '
                   'given to skip the unnecessary work. If set to off, only the final byte is written when the file '
                   'is created so that it has the expected size.'
    },
    'wal_recycle': {
        'default': 'on',
        'comment': 'If set to on (default), this option causes WAL files to be recycled by renaming them, avoiding '
                   'the need to create new ones. On COW file systems, it may be faster to create new ones, '
                   'so the option is given to disable this behavior.'
    },

    'wal_log_hints': {
        'default': 'on',
        'comment': "When this parameter is on, the PostgreSQL server writes the entire content of each disk page to "
                   "WAL during the first modification of that page after a checkpoint, even for non-critical "
                   "modifications of so-called hint bits. If data checksums are enabled, hint bit updates are always "
                   "WAL-logged and this setting is ignored. You can use this setting to test how much extra WAL-logging "
                   "would occur if your database had data checksums enabled."
    },
    # See Ref [16-19] for tuning the wal_writer_delay and commit_delay
    'wal_writer_delay': {
        'instructions': {
            "mini_default": K10,
        },
        'default': 200,
        'comment': 'Specifies how often the WAL writer flushes WAL, in time terms. After flushing WAL the writer '
                   'sleeps for the length of time given by :var:`wal_writer_delay`, unless woken up sooner by an '
                   'asynchronously committing transaction. If the last flush happened less than :var:`wal_writer_delay` '
                   'ago and less than :var:`wal_writer_flush_after` worth of WAL has been produced since, then WAL is '
                   'only written to the operating system, not flushed to disk. Default to 200 milliseconds (200ms), '
                   'and 1 second on mini system, followed by the official PostgreSQL documentation.',
        'partial_func': lambda value: f"{value}ms",
    },
    'wal_writer_flush_after': {
        'default': 1 * Mi,
        'comment': 'Specifies how often the WAL writer flushes WAL, in volume terms. If the last flush happened less '
                   'than :var:`wal_writer_delay` ago and less than :var:`wal_writer_flush_after` worth of WAL has been '
                   'produced since, then WAL is only written to the operating system, not flushed to disk. If '
                   ':var:`wal_writer_flush_after` is set to 0 then WAL data is always flushed immediately. Default to '
                   '1 MiB followed by the official PostgreSQL documentation.',
        'partial_func': bytesize_to_postgres_string,
    },
    # This setting means that when you have at least 5 transactions in pending, the delay (interval by commit_delay)
    # would be triggered (assuming maybe more transactions are coming from the client or application level)
    # ============================== CHECKPOINT ==============================
    # Checkpoint tuning are based on [20-23]: Our wishes is to make the database more reliable and perform better,
    # but reducing un-necessary read/write operation
    'checkpoint_timeout': {
        'instructions': {
            'mini_default': 60 * MINUTE,
            'medium_default': 30 * MINUTE,
            'mall_default': 15 * MINUTE,
            'bigt_default': 15 * MINUTE,
        },
        'default': 20 * MINUTE,
        'hardware_scope': 'overall',
        'comment': 'Specifies the maximum amount of time between automatic WAL checkpoints. Default to 20 minutes'
                   'on normal system and 15 minutes on large system. However, if you care about data consistency with '
                   'minimal data loss, consider the replication as you just need to failover to the standby server '
                   'as the checkpoint section is more focused on un-cleaned PostgreSQL crash or shutdown.',
        'partial_func': lambda value: f"{value // MINUTE}min",
    },
    'checkpoint_flush_after': {
        'default': 512 * Ki,
        'comment': "Whenever more than this amount of data has been written while performing a checkpoint, attempt to "
                   "force the OS to issue these writes to the underlying storage. Doing so will limit the amount of "
                   "dirty data in the kernel's page cache, reducing the likelihood of stalls when an fsync is issued "
                   "at the end of the checkpoint, or when the OS writes data back in larger batches in the background. "
                   "Often that will result in greatly reduced transaction latency, but there also are some cases, "
                   "especially with workloads that are bigger than shared_buffers, but smaller than the OS's page "
                   "cache, where performance might degrade.",
        'partial_func': lambda value: f"{bytesize_to_postgres_unit(value, unit=Ki)}kB",
    },
    'checkpoint_completion_target': {
        'default': 0.9,
        'comment': 'Specifies the target of checkpoint completion, as a fraction of total time between checkpoints. '
                   'The default is 0.9, which spreads the checkpoint across almost all of the available interval, '
                   'providing fairly consistent I/O load while also leaving some time for checkpoint completion '
                   'overhead. Reducing this parameter is not recommended because it causes the checkpoint to complete '
                   'faster. This results in a higher rate of I/O during the checkpoint followed by a period of less I/O '
                   'between the checkpoint completion and the next scheduled checkpoint.'
    },
    'checkpoint_warning': {
        'default': 30,
        'comment': 'Write a message to the server log if checkpoints caused by the filling of WAL segment files happen '
                   'closer together than this amount of time (which suggests that :var:`max_wal_size` ought to be '
                   'raised). Default is 30 seconds (30s).',
        'partial_func': lambda value: f"{value}s",
    },
    # ============================== WAL SIZE ==============================
    'min_wal_size': {
        'tune_op': lambda group_cache, global_cache, options, response: 10 * options.tuning_kwargs.wal_segment_size,
        'default': 80 * Mi,
        'comment': 'As long as WAL disk usage stays below this setting, old WAL files are always recycled for future '
                   'use at a checkpoint, rather than removed. This can be used to ensure that enough WAL space is '
                   'reserved to handle spikes in WAL usage, for example when running large batch jobs. If this value '
                   'is specified without units, it is taken as megabytes. The default is 80 MiB, scaled to 160 MiB on '
                   'larger system.',
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, Mi)}MB',
    },
    'max_wal_size': {
        'instructions': {
            'mini_default': 2 * Gi,
            'medium_default': 8 * Gi,
            'large_default': 24 * Gi,
            'mall_default': 40 * Gi,
            'bigt_default': 64 * Gi,
        },
        'default': 8 * Gi,
        'comment': 'Maximum size to let the WAL grow during automatic checkpoints (soft limit only); WAL size can '
                   'exceed :var:`max_wal_size` under special circumstances such as heavy load, a failing '
                   ':var:`archive_command` or :var:`archive_library`, or a high :var:`wal_keep_size` setting.',
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, Mi)}MB',
    },
    'wal_buffers': {
        'tune_op': partial(__wal_buffers, minimum=BASE_WAL_SEGMENT_SIZE // 2, maximum=BASE_WAL_SEGMENT_SIZE * 16),
        'default': 2 * BASE_WAL_SEGMENT_SIZE,
        'hardware_scope': 'mem',
        'comment': 'The amount of shared memory used for WAL data that has not yet been written to disk. The default '
                   'setting of -1 selects a size equal to 1/32nd (about 3%) of shared_buffers, but not less than 64kB '
                   'nor more than the size of one WAL segment, typically 16MB. This value can be set manually if the '
                   'automatic choice is too large or too small, but any positive value less than 32kB will be treated '
                   'as 32kB. The default of -1 meant that it is capped between 64 KiB and 2 GiB following the website '
                   'https://postgresqlco.nf/doc/en/param/wal_buffers/. But if you having a large write in OLAP workload '
                   'then it is best to increase this attribute. Our auto-tuning are set to be range from 16-128 MiB on '
                   'small servers and 32-512 MiB on large servers (ratio from shared_buffers are varied).',
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, unit=Mi)}MB',
    },

    # ============================== ARCHIVE && RECOVERY ==============================
    'archive_mode': {
        'default': 'on',
        'comment': 'When archive_mode is enabled, completed WAL segments are sent to archive storage by setting '
                   ':var:`archive_command` or :var:`archive_library`. In addition to :enum:`off`, to disable, there '
                   'are two modes: :enum:`on`, and :enum:`always`. During normal operation, there is no difference '
                   'between the two modes, but when set to always the WAL archiver is enabled also during archive '
                   'recovery or standby mode. In :enum:`always` mode, all files restored from the archive or streamed '
                   'with streaming replication will be archived (again)'
    },
    "archive_command": {
        # See benchmark of pg_dump here: https://www.cybertec-postgresql.com/en/lz4-zstd-pg_dump-compression-postgresql-16/
        # But since we have enabled wal_compression already, we don't need too high compression
        'default': rf"""
  
#!/bin/sh
set -euox pipefail

if [ "$PG_ENABLED_ARCHIVE" == "true" ]; then
    if [ "$PG_ENABLED_ARCHIVE_COMPRESSION" == "gzip" && command -v gzip &> /dev/null ]; then
        alias gzip = "$(command -v gzip)"
        gzip -k -v -c "%p" > {PG_ARCHIVE_DIR}/%f.gz
    elif [ "$PG_ENABLED_ARCHIVE_COMPRESSION" == "lz4" && command -v lz4 &> /dev/null ]; then
        alias lz4 = "$(command -v lz4)"
        lz4 -k -v "%p" {PG_ARCHIVE_DIR}/%f.lz4
    elif [ "$PG_ENABLED_ARCHIVE_COMPRESSION" == "zstd" && command -v zstd &> /dev/null ]; then
        alias zstd = "$(command -v zstd)"
        zstd -k -v "%p" -o {PG_ARCHIVE_DIR}/%f.zst
    else
        cp "%p" {PG_ARCHIVE_DIR}/%f
    fi
fi
exit 0
        """,
        'comment': "The local shell command to execute to archive a completed WAL file segment. Any %p in the string "
                   "is replaced by the path name of the file to archive, and any %f is replaced by only the file name. "
                   "(The path name is relative to the working directory of the server, i.e., the cluster's data "
                   "directory.) Use %% to embed an actual % character in the command. It is important for the command "
                   "to return a zero exit status only if it succeeds."
    },
    'archive_timeout': {
        'instructions': {
            'mall_default': 10 * MINUTE,  # 10 minutes
            'bigt_default': int(7.5 * MINUTE),  # 7.5 minutes
        },
        'default': 15 * MINUTE,
        'hardware_scope': 'overall',  # But based on data rate
        'comment': 'The :var:`archive_command` or :var:`archive_library` is only invoked for completed WAL segments. '
                   'Hence, if your server generates little WAL traffic, there could be a long delay between the '
                   'completion of a transaction and its safe recording in archive storage. To limit how old unarchived '
                   'data can be, you can set archive_timeout to force the server to switch to a new WAL segment file '
                   'periodically. When this parameter is greater than zero, the server will switch to a new segment '
                   'file whenever this amount of time has elapsed since the last segment file switch, and there has '
                   'been any database activity, including a single checkpoint (checkpoints are skipped if there is no '
                   'database activity). Note that archived files that are closed early due to a forced switch are '
                   'still the same length as completely full files. Therefore, it is unwise to use a very short '
                   ':var:`archive_timeout` — it will bloat your archive storage. In general this parameter is used for '
                   'safety and long PITR and want to revert back to a far time in the past. Default to 15 minutes on '
                   'small system and 10 minutes or less on larger system. For the higher critical system with shorter '
                   'RTO, you can set to 5 minutes (preferred) or less (but it could bloat your data storage, and '
                   'putting additional constraint on the archive storage system).',
        'partial_func': lambda value: f"{value}s",
    },
    'restore_command': {
        'default': rf""" 
#!/bin/sh
set -euox pipefail

if [ "$PG_ENABLED_ARCHIVE" == "true" ]; then
    if [ "$PG_ENABLED_ARCHIVE_COMPRESSION" == "gzip" && command -v gzip &> /dev/null ]; then
        alias gzip = "$(command -v gzip)"
        gzip -d -c -k -v {PG_ARCHIVE_DIR}/%f.gz > "%p"
    elif [ "$PG_ENABLED_ARCHIVE_COMPRESSION" == "lz4" && command -v lz4 &> /dev/null ]; then
        alias lz4 = "$(command -v lz4)"
        lz4 -d -k -v {PG_ARCHIVE_DIR}/%f.lz4 "%p"
    elif [ "$PG_ENABLED_ARCHIVE_COMPRESSION" == "zstd" && command -v zstd &> /dev/null ]; then
        alias zstd = "$(command -v zstd)"
        zstd -d -k -v {PG_ARCHIVE_DIR}/%f.zst -o "%p"
    else
        cp {PG_ARCHIVE_DIR}/%f "%p"
    fi
fi
exit 0
""",
        'comment': "The local shell command to execute to restore a file from the archive. Any %p in the string is "
                   "replaced by the path name of the file to restore, and any %f is replaced by only the file name. "
                   "(The path name is relative to the working directory of the server, i.e., the cluster's data "
                   "directory.) Use %% to embed an actual % character in the command. It is important for the command "
                   "to return a zero exit status only if it succeeds."
    },
    "archive_cleanup_command": {
        'default': f'pg_archivecleanup {PG_ARCHIVE_DIR} %r',
        'comment': "This optional parameter specifies a shell command that will be executed at every restart point. "
                   "The purpose of :var:`archive_cleanup_command` is to provide a mechanism for cleaning up old "
                   "archived WAL files that are no longer needed by the standby server. Any %r is replaced by the "
                   "name of the file containing the last valid restart point. That is the earliest file that must be "
                   "kept to allow a restore to be restartable, and so all files earlier than %r may be safely removed. "
                   "This information can be used to truncate the archive to just the minimum required to support "
                   "restart from the current restore. "
    },
}

# This is not used as the usage is different: promote standby to primary, recover with pg_rewind, failover, ...
_DB_RECOVERY_PROFILE = {
    'recovery_end_command': {
        'default': 'pg_ctl stop -D $PGDATA',
        'comment': "This parameter specifies a shell command that will be executed once only at the end of recovery. "
                   "This parameter is optional. The purpose of the :var:`recovery_end_command` is to provide a "
                   "mechanism for cleanup after replication or recovery. Any %r is replaced by the name of the "
                   "file containing the last valid restart point, like in :var:`archive_cleanup_command`."

    },
}

_DB_REPLICATION_PROFILE = {
    # Sending Servers
    'max_wal_senders': {
        'default': 3,
        'hardware_scope': 'net',
        'comment': 'Specifies the maximum number of concurrent connections from standby servers or streaming base '
                   'backup clients (i.e., the maximum number of simultaneously running WAL sender processes). The '
                   'default is 10. The value 0 means replication is disabled. Abrupt disconnection of a streaming '
                   'client might leave an orphaned connection slot behind until a timeout is reached, so this '
                   'parameter should be set slightly higher than the maximum number of expected clients so '
                   'disconnected clients can immediately reconnect.'
    },
    'max_replication_slots': {
        'default': 3,
        'hardware_scope': 'net',
        'comment': 'Specifies the maximum number of replication slots (see streaming-replication-slots) that the '
                   'server can support. The default is 10. This parameter can only be set at server start. Setting '
                   'it to a lower value than the number of currently existing replication slots will prevent the '
                   'server from starting. Also, wal_level must be set to replica or higher to allow replication '
                   'slots to be used.'
    },
    'wal_keep_size': {
        'tune_op': lambda group_cache, global_cache, options, response:
        realign_value_to_unit(
            cap_value(global_cache['max_wal_size'] // 20, 10 * options.tuning_kwargs.wal_segment_size,
                      options.wal_spec.disk_usable_size // 10),
            page_size=options.tuning_kwargs.wal_segment_size)[options.align_index],
        'default': 10 * BASE_WAL_SEGMENT_SIZE,
        'comment': 'Specifies the minimum size of past WAL files kept in the pg_wal directory, in case a standby '
                   'server needs to fetch them for streaming replication. If a standby server connected to the '
                   'sending server falls behind by more than wal_keep_size megabytes, the sending server might '
                   'remove a WAL segment still needed by the standby, in which case the replication connection '
                   'will be terminated. Downstream connections will also eventually fail as a result. (However, '
                   'the standby server can recover by fetching the segment from archive, if WAL archiving is in use). '
                   'We set this value to be 5% of the max_wal_size instead of zero in official PostgreSQL '
                   'documentation.',
        'partial_func': lambda value: f'{bytesize_to_postgres_unit(value, unit=Mi)}MB',
    },
    'wal_sender_timeout': {
        'instructions': {
            'mall_default': 2 * MINUTE,
            'bigt_default': 2 * MINUTE,
        },
        'default': MINUTE,
        'hardware_scope': 'net',
        'comment': 'Terminate replication connections that are inactive for longer than this amount of time. This is '
                   'useful for the sending server to detect a standby crash or network outage. Default to 60 seconds '
                   'on normal server and 120 seconds for large server. Setting to zero to disable the timeout '
                   'mechanism. With a cluster distributed across multiple geographic locations, using different '
                   'values per location brings more flexibility in the cluster management. A smaller value is useful '
                   'for faster failure detection with a standby having a low-latency network connection, and a larger '
                   'value helps in judging better the health of a standby if located on a remote location, with a '
                   'high-latency network connection.',
        'partial_func': lambda value: f"{value}s",
    },
    'track_commit_timestamp': {
        'default': 'on',
        'comment': 'Enables tracking of commit timestamps, which can be used to determine the age of transaction '
                   'snapshots. This parameter is required for logical replication. The default is on (customized by us '
                   'but the default is off in the official PostgreSQL documentation). When enabled, the system will '
                   'track the commit time of transactions, which can be used to determine the age of transaction '
                   'snapshots. This information is required for logical replication, and is also used by the '
                   'pg_xact_commit_timestamp() function.'
    },

    # Generic
    'logical_decoding_work_mem': {
        'tune_op': lambda group_cache, global_cache, options, response:
        realign_value_to_unit(cap_value(global_cache['maintenance_work_mem'] // 8, 32 * Mi, 2 * Gi),
                              page_size=DB_PAGE_SIZE)[options.align_index],
        'default': 64 * Mi,
        'comment': "Specifies the maximum amount of memory to be used by logical decoding, before some of the decoded "
                   "changes are written to local disk. This limits the amount of memory used by logical streaming "
                   "replication connections. It defaults to 64 megabytes (64MB). Since each replication connection "
                   "only uses a single buffer of this size, and an installation normally doesn't have many such "
                   "connections concurrently (as limited by max_wal_senders), it's safe to set this value significantly "
                   "higher than work_mem, reducing the amount of decoded changes written to disk. Note that this "
                   "variable is available on the subscribers or the receiving server, not the sending server.",
        'partial_func': lambda value: f"{bytesize_to_postgres_unit(value, unit=Mi)}MB",
    },

}

_DB_QUERY_PROFILE = {
    'seq_page_cost': {
        'default': 1.0,
        'comment': "Sets the planner's estimate of the cost of a disk page fetch that is part of a series of sequential "
                   "fetches. The default is 1.0."
    },
    'random_page_cost': {
        'default': 2.60,
        'comment': "Sets the planner's estimate of the cost of a non-sequentially fetched disk page. The default is "
                   "2.60. Reducing this value relative to seq_page_cost will cause the system to prefer index scans; "
                   "raising it will make index scans look relatively more expensive. You can raise or lower both values "
                   "together to change the importance of disk I/O costs relative to CPU costs, which are described by "
                   "the following parameters. Random access to mechanical disk storage is normally much more expensive "
                   "than four times sequential access. However, a lower default is used (4.0) because the majority of "
                   "random accesses to disk, such as indexed reads, are assumed to be in cache. The default value can "
                   "be thought of as modeling random access as 40 times slower than sequential, while expecting 90% of "
                   "random reads to be cached."
    },
    'cpu_tuple_cost': {
        'default': 0.03,
        'comment': "Sets the planner's estimate of the cost of processing each tuple (row). The default is 0.02, "
                   "which is larger than PostgreSQL's default of 0.01."
    },
    'cpu_index_tuple_cost': {
        'default': 0.005,
        'comment': "Sets the planner's estimate of the cost of processing each index entry during an index scan. The "
                   "default is 0.006, which is smaller than PostgreSQL's default of 0.005."
    },
    'cpu_operator_cost': {
        'default': 0.001,
        'comment': "Sets the planner's estimate of the cost of processing each operator or function. The default is "
                   "0.001, which is smaller than PostgreSQL's default of 0.0025."
    },
    'effective_cache_size': {
        'tune_op': __effective_cache_size,
        'default': 4 * Gi,
        'comment': "Sets the planner's assumption about the effective size of the disk cache that is available to a "
                   "single query. This is factored into estimates of the cost of using an index; a higher value makes "
                   "it more likely index scans will be used, a lower value makes it more likely sequential scans will "
                   "be used. When setting this parameter you should consider both PostgreSQL's shared buffers and the "
                   "portion of the kernel's disk cache that will be used for PostgreSQL data files, though some data "
                   "might exist in both places. Also, take into account the expected number of concurrent queries on "
                   "different tables, since they will have to share the available space. This parameter has no effect "
                   "on the size of shared memory allocated by PostgreSQL, nor does it reserve kernel disk cache; it is "
                   "used only for estimation purposes. The system also does not assume data remains in the disk cache "
                   "between queries.",
        'partial_func': lambda value: f"{bytesize_to_postgres_unit(value, unit=Mi)}MB",
    },
    'default_statistics_target': {
        'default': 100,
        'hardware_scope': 'overall',
        'comment': "Sets the default statistics target for table columns that have not been otherwise set via ALTER "
                   "TABLE SET STATISTICS. The default is 100. Increasing this value will increase the time to do "
                   "ANALYZE, but it will also increase the quality of the query planner's estimates. A default of 100"
                   "meant a 30000 rows (300x) is processed for 1M rows with 0.5 maximum relative error bin size and "
                   "1% error probability. For very small/simple databases, decrease to 10 or 50. Data warehousing "
                   "applications generally need to use 500 to 1000.",
    },

    # Parallelism
    'parallel_setup_cost': {
        'instructions': {
            'mall_default': 750,
            "bigt_default": 500,
        },
        'default': 1000,
        'comment': "Sets the planner's estimate of the cost of launching parallel worker processes. The default is 1000."
                   "But if you allocate a lot of CPU in the server, we assume it is the enterprise-grade CPU such "
                   "as Intel Xeon or AMD EPYC, thus the cost of launching parallel worker processes is not that high. "
                   "Thus we prefer a better parallel plan by reducing this value to 500."
    },
    'parallel_tuple_cost': {
        'instructions': {
            'large': lambda group_cache, global_cache, options, response: min(group_cache['cpu_tuple_cost'] * 10, 0.1),
            'mall': lambda group_cache, global_cache, options, response: min(group_cache['cpu_tuple_cost'] * 10, 0.1),
            'bigt': lambda group_cache, global_cache, options, response: min(group_cache['cpu_tuple_cost'] * 10, 0.1),
        },
        'default': 0.1,
        'comment': "Sets the planner's estimate of the cost of transferring a tuple from a parallel worker process to "
                   "another process. The default is 0.1, but if you have a lot of CPU in the database server, then we "
                   "believe the cost of tuple transfer would be reduced but still maintained its ratio compared to "
                   "the single CPU execution (0.01 vs 0.1). "
    },
    # Commit Behaviour
    'commit_delay': {
        'instructions': {
            'large_default': 500,
            'mall_default': 500,
            'bigt_default': 200,
        },
        'default': 1 * K10,
        'hardware_scope': 'overall',
        'comment': 'Setting :var:`commit_delay` adds a time delay before a WAL flush is initiated. This can improve '
                   'group commit throughput by allowing a larger number of transactions to commit via a single WAL '
                   'flush, if system load is high enough that additional transactions become ready to commit within '
                   'the given interval. However, it also increases latency by up to the :var:`commit_delay` for each WAL '
                   'flush. Because the delay is just wasted if no other transactions become ready to commit, a delay is '
                   'only performed if at least :var:`commit_siblings` other transactions are active when a flush is '
                   'about to be initiated. Also, no delays are performed if fsync is disabled. The default is 1ms, '
                   'and 0.2-0.5ms on large system. See the reference [27] for more information.',
        'partial_func': lambda value: f'{value}us',
    },
    'commit_siblings': {
        'instructions': {
            "large_default": 8,
            "mall_default": 10,
            "bigt_default": 10,
        },
        'default': 5,
        'hardware_scope': 'overall',
        'comment': 'Minimum number of concurrent open transactions to require before performing the :var:`commit_delay` '
                   'delay. A larger value makes it more probable that at least one other transaction will become ready '
                   'to commit during the delay interval. Default to 5 commits in transaction, up to 10 commits in '
                   'transaction on large system.  See the reference [27] for more information.',
    },

    # Statistics
    'track_activity_query_size': {
        'default': 2 * Ki,
        'comment': "Specifies the number of bytes reserved to track the currently executing command for each active "
                   "session, for the pg_stat_activity.query field. The default value is 2 KiB (as 1 KiB of official "
                   "documentation).",
        'partial_func': lambda value: f'{value}B',
    },
    'track_counts': {
        'default': 'on',
        'comment': 'Enables collection of statistics on database activity. This parameter is on by default, because '
                   'the autovacuum daemon needs the collected information.',

    },
    'track_io_timing': {
        'default': 'on',
        'hardware_scope': 'cpu',
        'comment': 'Enables timing of database I/O calls. This parameter is off (by official PostgreSQL default, but '
                   'on in our tuning guideline), as it will repeatedly query the operating system for the current '
                   'time, which may cause significant overhead on some platforms. You can use the pg_test_timing tool '
                   'to measure the overhead of timing on your system. I/O timing is displayed in pg_stat_database, '
                   'pg_stat_io, in the output of EXPLAIN when the BUFFERS option is used, in the output of VACUUM when '
                   'the VERBOSE option is used, by autovacuum for auto-vacuums and auto-analyzes, when '
                   'log_autovacuum_min_duration is set and by pg_stat_statements.',
    },
}

_DB_LOG_PROFILE = {
    # Where to Log
    'logging_collector': {
        'default': 'on',
        'comment': 'This parameter enables the logging collector, which is a background process that captures log '
                   'messages sent to stderr and redirects them into log files. This approach is often more useful than '
                   'logging to syslog, since some types of messages might not appear in syslog output. (One common '
                   'example is dynamic-linker failure messages; another is error messages produced by scripts such as '
                   ':var:`archive_command`.)'
    },
    'log_destination': {
        'default': 'stderr',
        'comment': 'This parameter determines the destination of log output. Valid values are combinations of stderr, '
                   'csvlog, syslog, and eventlog, depending on the platform. csvlog is only available if '
                   ':var:`logging_collector` is also enabled.'
    },
    'log_directory': {
        'default': PG_LOG_DIR,
        'comment': 'When :var:`logging_collector` is enabled, this parameter determines the directory in which log '
                   'files will be created. It can be specified as an absolute path, or relative to the cluster data '
                   'directory. '
    },
    'log_filename': {
        'default': 'postgresql-%Y-%m-%d_%H%M.log',
        'comment': "When :var:`logging_collector` is enabled, this parameter sets the file names of the created log "
                   "files. The value is treated as a strftime pattern, so %-escapes can be used to specify time-varying "
                   "file names. (Note that if there are any time-zone-dependent %-escapes, the computation is done in "
                   "the zone specified by log_timezone.) The supported %-escapes are similar to those listed in the "
                   "Open Group's strftime specification."
    },
    'log_rotation_age': {
        # For best-case it is good to make the log rotation happens by time-based rather than size-based
        'instructions': {
            'mini_default': 3 * DAY,
            'mall_default': 6 * HOUR,
            'bigt_default': 4 * HOUR,
        },
        'default': 1 * DAY,
        'comment': 'When :var:`logging_collector` is enabled, this parameter determines the maximum amount of time to '
                   'use an individual log file, after which a new log file will be created. Default to 4,6-24 hours on '
                   'large system and 3 days on small system. This depends on your log volume and retention so you can '
                   'dynamically adjust it and use compression when archiving the log if needed.',
        'partial_func': lambda value: f"{value // HOUR}h",
    },
    'log_rotation_size': {
        'instructions': {
            'mini_default': 32 * Mi,
            'medium_default': 64 * Mi,
        },
        'default': 256 * Mi,
        'comment': 'When :var:`logging_collector` is enabled, this parameter determines the maximum size of an '
                   'individual log file. After this amount of data has been emitted into a log file, a new log file '
                   'will be created. Default to 256 MiB on large system and 32 MiB on smaller system. This depends on '
                   'your log volume and retention so you can dynamically adjust it and use compression when archiving '
                   'the log if needed. We dont expect the log file to reach by this size (thus we are in more favor of'
                   'time-based rotation) but this size is normally enough to accommodate most scenarios, even when a '
                   'lot of transactions or DB-DDoS attack can help us. ',
        'partial_func': lambda value: f"{bytesize_to_postgres_unit(value, unit=Mi)}MB",
    },
    'log_truncate_on_rotation': {
        'default': 'on',
        'comment': 'When :var:`logging_collector` is enabled, this parameter will cause PostgreSQL to truncate '
                   '(overwrite), rather than append to, any existing log file of the same name. However, truncation '
                   'will occur only when a new file is being opened due to time-based rotation, not during server '
                   'startup or size-based rotation. When off, pre-existing files will be appended to in all cases.'
    },
    # What to log
    'log_autovacuum_min_duration': {
        'default': 300 * K10,
        'comment': 'Causes each action and each statement to be logged if their duration is equal to or longer than '
                   'the specified time in milliseconds. Setting this to zero logs all statements and actions. A '
                   'negative value turns this feature off. PostgreSQL default to -1 (off) and we set to 5 minutes.',
        'partial_func': lambda value: f"{value // K10}s",
    },
    'log_checkpoints': {
        'default': 'on',
        'comment': 'Causes checkpoints and restartpoints to be logged in the server log. Some statistics are included '
                   'in the log messages, including the number of buffers written and the time spent writing them.'
    },
    'log_connections': {
        'default': 'on',
        'comment': 'Causes each attempted connection to the server to be logged, as well as successful completion of '
                   'both client authentication (if necessary) and authorization.'
    },
    'log_disconnections': {
        'default': 'on',
        'comment': 'Causes session terminations to be logged. The log output provides information similar to '
                   ':var:`log_connections`, plus the duration of the session.'
    },
    'log_duration': {
        'default': 'on',
        'comment': 'Causes the duration of every completed statement to be logged. For clients using extended query '
                   'protocol, durations of the Parse, Bind, and Execute steps are logged independently.',
    },
    'log_error_verbosity': {
        'default': 'VERBOSE',
        'comment': 'Controls the amount of detail written in the server log for each message that is logged. Valid '
                   'values are :enum:`TERSE`, :enum:`DEFAULT`, and :enum:`VERBOSE`, each adding more fields to '
                   'displayed messages. :enum:`TERSE` excludes the logging of DETAIL, HINT, QUERY, and CONTEXT error '
                   'information. :enum:`VERBOSE` output includes the SQLSTATE error code. See more at '
                   'https://www.postgresql.org/docs/current/errcodes-appendix.html'
    },
    'log_line_prefix': {
        'default': '%m [%p] %quser=%u@%r@%a_db=%d,backend=%b,xid=%x %v,log=%l',
        'comment': 'This is a printf-style string that is output at the beginning of each log line. The following '
                   'format specifiers are recognized (note that %r is not supported in this parameter): %a, %u, %d, %r, '
                   '%p, %t, %m, %i, %e, %c, %l, %s, %v, %x, %q, %%. The PostgreSQL default is %m [%p], but our is '
                   '%m [%p] %quser=%u@%r@%a_db=%d,backend=%b,xid=%x %v,log=%l. Description is as follows: '
                   'https://www.postgresql.org/docs/current/runtime-config-logging.html'
    },
    'log_lock_waits': {
        'default': 'on',
        'comment': 'Controls whether a log message is produced when a session waits longer than :var:`deadlock_timeout` '
                   'to acquire a lock. This is useful in determining if lock waits are causing poor performance.'
    },
    'log_recovery_conflict_waits': {
        'default': 'on',
        'comment': 'Controls whether a log message is produced when the startup process waits longer than '
                   ':var:`deadlock_timeout` for recovery conflicts. This is useful in determining if recovery conflicts '
                   'prevent the recovery from applying WAL.'
    },
    'log_statement': {
        'default': 'mod',
        'comment': 'Controls which SQL statements are logged. Valid values are :enum:`none`, :enum:`ddl`, :enum:`mod`, '
                   'and :enum:`all`. :enum:`ddl` logs all data definition statements, such as CREATE, ALTER, and DROP '
                   'statements. :enum:`mod` logs all ddl statements, plus data-modifying statements such as INSERT, '
                   'UPDATE, DELETE, TRUNCATE, and COPY FROM. Note that statements that contain simple syntax errors are '
                   'not logged even by the :var:`log_statement` = :enum:`all` setting, because the log message is '
                   'emitted only after basic parsing has been done to determine the statement type. '
    },
    'log_replication_commands': {
        'default': 'on',
        'comment': "Causes each replication command and walsender process's replication slot acquisition/release to be "
                   "logged in the server log. See Section 53.4 for more information about replication command. The "
                   "default value is on.",
    },
    # 'log_timezone': {
    #     'default': 'UTC',
    # }, # See here: https://www.postgresql.org/docs/current/datatype-datetime.html#DATATYPE-TIMEZONES

    'log_min_duration_statement': {
        'default': int(2 * K10),
        'comment': 'Causes the duration of each completed statement to be logged if the statement ran for at least the '
                   'specified amount of time. The default is 2000 ms (but PostgreSQL disable this feature with -1). '
                   'However, this attribute should be subjected to your business requirement rather than trust 100% '
                   'at this setting. ',
        'partial_func': lambda value: f"{value}ms",
    },
    'log_min_error_statement': {
        'default': 'ERROR',
        'comment': 'Controls which SQL statements that cause an error condition are recorded in the server log. Each '
                   'level includes all the levels that follow it. The later the level, the fewer messages are sent to '
                   'the log. Valid values are :enum:`DEBUG5` to :enum:`DEBUG1`, :enum:`INFO`, :enum:`NOTICE`, '
                   ':enum:`WARNING`, :enum:`ERROR`, :enum:`LOG`, :enum:`FATAL`, :enum:`PANIC`. The default is '
                   ':enum:`ERROR`, which means statements causing errors, log messages, fatal errors, and panics are '
                   'logged.',
    },
    'log_parameter_max_length': {
        'tune_op': lambda group_cache, global_cache, options, response: global_cache['track_activity_query_size'],
        'default': -1,
        'comment': 'Sets the maximum length in bytes of data logged for bind parameter values when logging statements. '
                   'If greater than zero, each bind parameter value logged with a non-error statement-logging message '
                   'is trimmed to this many bytes. Zero disables logging of bind parameters for non-error statement '
                   'logs. -1 (the default) allows bind parameters to be logged in full. If this value is specified '
                   'without units, it is taken as bytes. Only superusers and users with the appropriate SET privilege '
                   'can change this setting. This setting only affects log messages printed as a result of '
                   'log_statement, log_duration, and related settings.',
        'partial_func': lambda value: f"{value}B",
    },
    'log_parameter_max_length_on_error': {
        'tune_op': lambda group_cache, global_cache, options, response: global_cache['track_activity_query_size'],
        'default': -1,
        'comment': 'Sets the maximum length in bytes of data logged for bind parameter values when logging statements, '
                   'on error. If greater than zero, each bind parameter value reported in error messages is trimmed to '
                   'this many bytes. Zero (the default) disables including bind parameters in error messages. -1 '
                   'allows bind parameters to be printed in full. Non-zero values of this setting add overhead, as '
                   'PostgreSQL will need to store textual representations of parameter values in memory at the start '
                   'of each statement, whether or not an error eventually occurs.',
        'partial_func': lambda value: f"{value}B",
    },
}

_DB_TIMEOUT_PROFILE = {
    # Transaction Timeout should not be moved away from default, but we can customize the statement_timeout and
    # lock_timeout
    # Add +1 seconds to avoid checkpoint_timeout happens at same time as idle_in_transaction_session_timeout
    'idle_in_transaction_session_timeout': {
        'default': 5 * MINUTE + 1,
        'comment': 'Terminate any session that has been idle (that is, waiting for a client query) within an open '
                   'transaction for longer than the specified amount of time. A value of zero (default by official '
                   'PostgreSQL documentation) disables the timeout. This option can be used to ensure that idle '
                   'sessions do not hold locks for an unreasonable amount of time. Even when no significant locks '
                   'are held, an open transaction prevents vacuuming away recently-dead tuples that may be visible '
                   'only to this transaction; so remaining idle for a long time can contribute to table bloat. See '
                   'routine-vacuuming for more details.',
        'partial_func': lambda value: f'{value}s',
    },
    'statement_timeout': {
        'default': 0,
        'comment': 'Abort any statement that takes more than the specified amount of time. If log_min_error_statement '
                   'is set to ERROR or lower, the statement that timed out will also be logged. A value of zero (the '
                   'default) disables the timeout. The timeout is measured from the time a command arrives at the '
                   'server until it is completed by the server. If multiple SQL statements appear in a single '
                   'simple-query message, the timeout is applied to each statement separately. (PostgreSQL versions '
                   'before 13 usually treated the timeout as applying to the whole query string.) In extended query '
                   'protocol, the timeout starts running when any query-related message (Parse, Bind, Execute, '
                   'Describe) arrives, and it is canceled by completion of an Execute or Sync message. Setting '
                   'statement_timeout in postgresql.conf is not recommended because it would affect all sessions. '
                   'For best tuning, find the longest running query, if on the application side, set it to 2-3x that '
                   'amount; if on the database side, including the one in the pg_dump output, set it to 8-10x that '
                   'amount in the postgresql.conf.',
        'partial_func': lambda value: f"{value}s",
    },
    'lock_timeout': {
        'default': 0,
        'comment': 'Abort any statement that waits longer than the specified amount of time while attempting to acquire '
                   'a lock on a table, index, row, or other database object. The time limit applies separately to each '
                   'lock acquisition attempt. The limit applies both to explicit locking requests (such as LOCK TABLE, '
                   'or SELECT FOR UPDATE without NOWAIT) and to implicitly-acquired locks. A value of zero (the '
                   'default) disables the timeout. Unlike statement_timeout, this timeout can only occur while waiting '
                   'for locks. Note that if statement_timeout is nonzero, it is rather pointless to set lock_timeout '
                   'to the same or larger value, since the statement timeout would always trigger first. If '
                   'log_min_error_statement is set to ERROR or lower, the statement that timed out will be logged. '
                   'Setting lock_timeout in postgresql.conf is not recommended because it would affect all sessions ... '
                   'but consider setting this per application or per query for any explicit locking attempts.',
        'partial_func': lambda value: f"{value}s",
    },
    'deadlock_timeout': {
        'default': 1 * SECOND,
        'comment': "This is the amount of time to wait on a lock before checking to see if there is a deadlock "
                   "condition. The check for deadlock is relatively expensive, so the server doesn't run it every "
                   "time it waits for a lock. We optimistically assume that deadlocks are not common in production "
                   "applications and just wait on the lock for a while before checking for a deadlock. Increasing "
                   "this value reduces the amount of time wasted in needless deadlock checks, but slows down reporting "
                   "of real deadlock errors. The default is one second (1s), which is probably about the smallest "
                   "value you would want in practice. On a heavily loaded server you might want to raise it. Ideally "
                   "the setting should exceed your typical transaction time, so as to improve the odds that a lock "
                   "will be released before the waiter decides to check for deadlock. When log_lock_waits is set, this "
                   "parameter also determines the amount of time to wait before a log message is issued about the "
                   "lock wait. If you are trying to investigate locking delays you might want to set a shorter than "
                   "normal deadlock_timeout. Default is fine, except when you are troubleshooting/monitoring locks. "
                   "In that case, you may want to lower it to as little as 50ms.",
        'partial_func': lambda value: f"{value}s",
    },

}

# ========================= #
# Library (You don't need to tune these variable as they are not directly related to the database performance)
_DB_LIB_PROFILE = {
    'shared_preload_libraries': {
        'default': 'auto_explain,pg_prewarm,pgstattuple,pg_stat_statements,pg_buffercache,pg_repack',   # Not pg_squeeze
        'comment': 'A comma-separated list of shared libraries to load into the server. The list of libraries must be '
                   'specified by name, not with file name or path. The libraries are loaded into the server during '
                   'startup. If a library is not found when the server is started, the server will fail to start. '
                   'The default is empty. The libraries are loaded in the order specified. If a library depends on '
                   'another library, the library it depends on must be loaded earlier in the list. The libraries are '
                   'loaded into the server process before the server process starts accepting connections. This '
                   'parameter can only be set in the postgresql.conf file or on the server command line. It is not '
                   'possible to change this setting after the server has started.',

    },
    # Auto Explain
    'auto_explain.log_min_duration': {
        'tune_op': lambda group_cache, global_cache, options, response:
        realign_value_to_unit(int(global_cache['log_min_duration_statement'] * 1.5), page_size=20)[options.align_index],
        'default': -1,
        'comment': "auto_explain.log_min_duration is the minimum statement execution time, in milliseconds, that will "
                   "cause the statement's plan to be logged. Setting this to 0 logs all plans. -1 (the default) "
                   "disables logging of plans. For example, if you set it to 250ms then all statements that run "
                   "250ms or longer will be logged.",
        'partial_func': lambda value: f"{value}ms",
    },
    'auto_explain.log_analyze': {
        'default': 'off',
        'comment': "If set to on, this parameter causes the output of EXPLAIN to include information about the "
                   "actual run time of each plan node. This is equivalent to setting the EXPLAIN option ANALYZE. "
                   "The default is off.",
    },
    'auto_explain.log_buffers': {
        'default': 'on',
        'comment': "auto_explain.log_buffers controls whether buffer usage statistics are printed when an execution "
                   "plan is logged; it's equivalent to the BUFFERS option of EXPLAIN. This parameter has no effect "
                   "unless auto_explain.log_analyze is enabled.",
    },
    'auto_explain.log_wal': {
        'default': 'on',
        'comment': "auto_explain.log_wal controls whether WAL usage statistics are printed when an execution plan is "
                   "logged; it's equivalent to the WAL option of EXPLAIN. This parameter has no effect unless "
                   "auto_explain.log_analyze is enabled. "
    },
    'auto_explain.log_settings': {
        'default': 'off',
        'comment': "auto_explain.log_settings controls whether the current settings are printed when an execution plan "
                   "is logged; it's equivalent to the SETTINGS option of EXPLAIN. This parameter has no effect unless "
                   "auto_explain.log_analyze is enabled.",
    },
    'auto_explain.log_triggers': {
        'default': 'off',
        'comment': "auto_explain.log_triggers controls whether trigger statistics are printed when an execution plan "
                   "is logged; it's equivalent to the TRIGGER option of EXPLAIN. This parameter has no effect unless "
                   "auto_explain.log_analyze is enabled.",
    },
    'auto_explain.log_verbose': {
        'default': 'on',
        'comment': "auto_explain.log_verbose controls whether the output of EXPLAIN VERBOSE is included in the "
                   "auto_explain output. The default is on.",
    },
    'auto_explain.log_format': {
        'default': 'text',
        'comment': "auto_explain.log_format controls the format of the output of auto_explain. The allowed values are "
                   "text, xml, json, and yaml.",
    },
    'auto_explain.log_level': {
        'default': 'LOG',
        'comment': "auto_explain.log_level controls the log level at which auto_explain messages are emitted. The "
                   "allowed values are DEBUG5 to DEBUG1, INFO, NOTICE, WARNING, ERROR, LOG, FATAL, and PANIC.",
    },
    'auto_explain.log_timing': {
        'default': 'on',
        'comment': "auto_explain.log_timing controls whether per-node timing information is printed when an execution "
                   "plan is logged; it's equivalent to the TIMING option of EXPLAIN. The overhead of repeatedly "
                   "reading the system clock can slow down queries significantly on some systems, so it may be useful "
                   "to set this parameter to off when only actual row counts, and not exact times, are needed. This "
                   "parameter has no effect unless auto_explain.log_analyze is enabled."
    },
    'auto_explain.log_nested_statements': {
        'default': 'off',
        'comment': "auto_explain.log_nested_statements causes nested statements (statements executed inside a function) "
                   "to be considered for logging. When it is off, only top-level query plans are logged.",
    },
    'auto_explain.sample_rate': {
        'default': 1.0,
        'comment': "auto_explain.sample_rate causes auto_explain to only explain a fraction of the statements in "
                   "each session. The default is 1, meaning explain all the queries. In case of nested statements, "
                   "either all will be explained or none.",
    },
    # PG_STAT_STATEMENTS
    'pg_stat_statements.max': {
        'instructions': {
            'large_default': 10 * K10,
            'mall_default': 15 * K10,
            'bigt_default': 20 * K10,
        },
        'default': 5 * K10,
        'comment': "pg_stat_statements.max is the maximum number of statements tracked by the module (i.e., the "
                   "maximum number of rows in the pg_stat_statements view). If more distinct statements than that are "
                   "observed, information about the least-executed statements is discarded. The number of times such "
                   "information was discarded can be seen in the pg_stat_statements_info view. Default to 5K, reached "
                   "to 10-20K on large system.",
    },
    'pg_stat_statements.track': {
        'default': 'all',
        'comment': "pg_stat_statements.track controls which statements are counted and reported in the pg_stat_statements "
                   "view. The allowed values are none, top, and all. top tracks only the top-level statements executed "
                   "by clients. all tracks all statements executed by clients. none disables tracking entirely. The "
                   "default is top.",
    },
    'pg_stat_statements.track_utility': {
        'default': 'on',
        'comment': "pg_stat_statements.track_utility controls whether utility commands are tracked by the module. "
                   "Utility commands are all those other than SELECT, INSERT, UPDATE, DELETE, and MERGE. Default to on",
    },
    'pg_stat_statements.track_planning': {
        'default': 'off',
        'comment': "pg_stat_statements.track_planning controls whether planning operations and duration are tracked "
                   "by the module. Enabling this parameter may incur a noticeable performance penalty, especially "
                   "when statements with identical query structure are executed by many concurrent connections which "
                   "compete to update a small number of pg_stat_statements entries.",
    },
    'pg_stat_statements.save': {
        'default': 'on',
        'comment': "pg_stat_statements.save controls whether the statistics gathered by pg_stat_statements are saved "
                   "across server shutdowns and restarts. Default to on.",
    },
}

# Validate and remove the invalid library configuration
preload_libraries = set(_DB_LIB_PROFILE['shared_preload_libraries']['default'].split(','))
for key in list(_DB_LIB_PROFILE.keys()):
    if '.' in key and key.split('.')[0] not in preload_libraries:
        _DB_LIB_PROFILE.pop(key)

# ========================= #
DB0_CONFIG_PROFILE = {
    'connection': (PG_SCOPE.CONNECTION, _DB_CONN_PROFILE, {'hardware_scope': 'cpu'}),
    'memory': (PG_SCOPE.MEMORY, _DB_RESOURCE_PROFILE, {'hardware_scope': 'mem'}),
    'maintenance': (PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, {'hardware_scope': 'disk'}),
    'background_writer': (PG_SCOPE.OTHERS, _DB_BGWRITER_PROFILE, {'hardware_scope': 'disk'}),
    'asynchronous-disk': (PG_SCOPE.OTHERS, _DB_ASYNC_DISK_PROFILE, {'hardware_scope': 'disk'}),
    'asynchronous-cpu': (PG_SCOPE.OTHERS, _DB_ASYNC_CPU_PROFILE, {'hardware_scope': 'cpu'}),
    'wal': (PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_WAL_PROFILE, {'hardware_scope': 'disk'}),
    'query': (PG_SCOPE.QUERY_TUNING, _DB_QUERY_PROFILE, {'hardware_scope': 'cpu'}),
    'log': (PG_SCOPE.LOGGING, _DB_LOG_PROFILE, {'hardware_scope': 'disk'}),
    'replication': (PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_REPLICATION_PROFILE, {'hardware_scope': 'disk'}),
    'timeout': (PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, {'hardware_scope': 'overall'}),
    'lib': (PG_SCOPE.EXTRA, _DB_LIB_PROFILE, {'hardware_scope': 'overall'}),
}
merge_extra_info_to_profile(DB0_CONFIG_PROFILE)
type_validation(DB0_CONFIG_PROFILE)
