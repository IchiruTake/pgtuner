/*
This module contains how we applied the tuning profile for PostgreSQL server. This is a mimic translation of the 
Python source code from the `./src/tuner/profile/database/gtune_0.py` file and port it as Javascript under the 
path of `./js_src/tuner/profile/database/gtune_v0.js`. The layout is splited between category which shared 
this format:

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

*/

// ----------------------------------------------------------------------------------------------------------------
// Importing modules
import { Ki, K10, Mi, Gi, DB_PAGE_SIZE, DAY, MINUTE, HOUR, SECOND, PG_LOG_DIR,
    BASE_WAL_SEGMENT_SIZE, M10 } from '../../../static.js';
import { ceil, log, floor } from math;
import { merge_extra_info_to_profile, type_validation } from '../common.js';
import { realign_value, cap_value } from '../../../utils/numeric.js';
import { PG_WORKLOAD } from '../../data/workload.js';

from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.pg_dataclass import PG_TUNE_RESPONSE

// ----------------------------------------------------------------------------------------------------------------
// Constants
if (DB_PAGE_SIZE != 8 * Ki) {
    throw new Error("The PostgreSQL server page size must be 8 KiB");
}
// This could be increased if your database server is not under hypervisor and run under Xeon_v6, recent AMD EPYC 
// (2020) or powerful ARM CPU, or AMD Threadripper (2020+). But in most cases, the 4x scale factor here is enough 
// to be generalized. Even on PostgreSQL 14, the scaling is significant when the PostgreSQL server is not 
// virtualized and have a lot of CPU to use (> 32 - 96|128 cores).    
const __BASE_RESERVED_DB_CONNECTION = 3; 
const __SCALE_FACTOR_CPU_TO_CONNECTION = 4;
const __DESCALE_FACTOR_RESERVED_DB_CONNECTION = 4; // This is the descaling factor for reserved connections

function _GetNumConnections(options, response, use_reserved_connection = false, use_full_connection = false) {
    // This function is used to calculate the number of connections that can be used by the PostgreSQL server. The number
    // of connections is calculated based on the number of logical CPU cores available on the system and the scale factor.
    managed_cache = response.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG);
    try {
        let total_connections = managed_cache['max_connections'];
        let reserved_connections = managed_cache['reserved_connections'] + managed_cache['superuser_reserved_connections'];
    } catch (e) {
        throw new Error("This function required the connection must be triggered and placed in the managed cache: " + e);
    }
    if (!use_reserved_connection) {
        total_connections -= reserved_connections;
    } else {
        printf("The reserved mode is enabled (not recommended) as reserved connections are purposely different " + 
            "usage such as troubleshooting, maintenance, **replication**, sharding, cluster, ...");
    }
    if (!use_full_connection) {
        total_connections *= options.tuning_kwargs.effective_connection_ratio;
    }
    return ceil(total_connections);  
}

function _GetMemConnInTotal(options, response, use_reserved_connection = false, use_full_connection = false) {
    /* 
    The memory usage per connection is varied and some articles said it could range on scale 1.5 - 14 MiB,
    or 5 - 10 MiB so we just take this ratio. This memory is assumed to be on one connection without execute
    any query or transaction.
    References:
    - https://www.cybertec-postgresql.com/en/postgresql-connection-memory-usage/
    - https://cloud.ibm.com/docs/databases-for-postgresql?topic=databases-for-postgresql-managing-connections
    - https://techcommunity.microsoft.com/blog/adforpostgresql/analyzing-the-limits-of-connection-scalability-in-postgres/1757266
    - https://techcommunity.microsoft.com/blog/adforpostgresql/improving-postgres-connection-scalability-snapshots/1806462
    Here is our conclusion:
    - PostgreSQL apply one-process-per-connection TCP connection model, and the connection memory usage during idle
    could be significant on small system, especially during the OLTP workload.
    - Idle connections leads to more frequent context switches, harmful to the system with less vCPU core. And
    degrade not only the transaction throughput but also the latency.
    */
    let num_conns = _GetNumConnections(options, response, use_reserved_connection, use_full_connection);
    let mem_conn_overhead = options.tuning_kwargs.single_memory_connection_overhead;
    return num_conns * mem_conn_overhead;
}

function _CalcSharedBuffers(options) {
    let shared_buffers_ratio = options.tuning_kwargs.shared_buffers_ratio;
    if (shared_buffers_ratio < 0.25) {
        _logger.warning('The shared_buffers_ratio is too low, which official PostgreSQL documentation recommended ' +
            'the starting point is 25% of RAM or over. Please consider increasing the ratio.');
    }
    let shared_buffers = Math.max(options.usable_ram * shared_buffers_ratio, 128 * Mi);
    if (shared_buffers == 128 * Mi) {
        _logger.warning('No benefit is found on tuning this variable');
    }
    // Re-align the number (always use the lower bound for memory safety) -> We can set to 32-128 pages, or
    // probably higher as when the system have much RAM, an extra 1 pages probably not a big deal
    shared_buffers = realign_value(shared_buffers, page_size=DB_PAGE_SIZE)[options.align_index];
    _logger.debug(`shared_buffers: ${floor(shared_buffers / Mi)}MiB`);
    return shared_buffers;
}

function _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response) {
    /* 
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

    From our rationale, when we target on first on-board database, we don't know how the application will behave
    on it wished queries, but we know its workload type, and it safeguard. So this is our solution.
    work_mem = ratio * (RAM - shared_buffers - overhead_of_os_conn) * threshold / effective_user_connections

    And then we cap it to below a 64 MiB - 1.5 GiB (depending on workload) to ensure our setup is don't
    exceed the memory usage.
    - https://techcommunity.microsoft.com/blog/adforpostgresql/optimizing-query-performance-with-work-mem/4196408
    */
    let pgmem_available = int(options.usable_ram) - group_cache['shared_buffers'];
    let _mem_conns = _GetMemConnInTotal(options, response, use_reserved_connection=false, use_full_connection=true);
    pgmem_available -= _mem_conns * options.tuning_kwargs.memory_connection_to_dedicated_os_ratio;
    if ('wal_buffers' in global_cache) {   // I don't know if this make significant impact?
        pgmem_available -= global_cache['wal_buffers'];
    }
    let max_work_buffer_ratio = options.tuning_kwargs.max_work_buffer_ratio;
    let active_connections = _GetNumConnections(options, response, use_reserved_connection=false,
                                                use_full_connection=false);
    let total_buffers = int(pgmem_available * max_work_buffer_ratio) // active_connections;
    // Minimum to 1 MiB and maximum is varied between workloads
    let max_cap = int(1.5 * Gi);
    if (options.workload_type in (PG_WORKLOAD.SOLTP, PG_WORKLOAD.LOG, PG_WORKLOAD.TSR_IOT)) {
        max_cap = 256 * Mi;
    }
    if (options.workload_type in (PG_WORKLOAD.HTAP, PG_WORKLOAD.OLAP, PG_WORKLOAD.DATA_WAREHOUSE)) {
        // I don't think I will make risk beyond this number
        max_cap = 8 * Gi;
    }
    let temp_buffer_ratio = options.tuning_kwargs.temp_buffers_ratio;
    let temp_buffers = cap_value(total_buffers * temp_buffer_ratio, 1 * Mi, max_cap);
    let work_mem = cap_value(total_buffers * (1 - temp_buffer_ratio), 1 * Mi, max_cap);
    
    // Realign the number (always use the lower bound for memory safety)
    temp_buffers = realign_value(int(temp_buffers), page_size=DB_PAGE_SIZE)[options.align_index];
    work_mem = realign_value(int(work_mem), page_size=DB_PAGE_SIZE)[options.align_index];
    _logger.debug(`temp_buffers: ${floor(temp_buffers / Mi)}MiB`);
    _logger.debug(`work_mem: ${floor(work_mem / Mi)}MiB`);
    
    return [temp_buffers, work_mem];
}

function _CalcTempBuffers(group_cache, global_cache, options, response) {
    return _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[0];
}

function _CalcWorkMem(group_cache, global_cache, options, response) {
    return _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[1];
}

function _GetMaxConns(options, group_cache, min_user_conns, max_user_conns) {
    total_reserved_connections = group_cache['reserved_connections'] + group_cache['superuser_reserved_connections'];
    if (options.tuning_kwargs.user_max_connections != 0) {
        _logger.debug('The max_connections variable is overridden by the user so no constraint here.');
        allowed_connections = options.tuning_kwargs.user_max_connections;
        return allowed_connections + total_reserved_connections;
    }
    // Make a small upscale here to future-proof database scaling, and reduce the number of connections
    _upscale = __SCALE_FACTOR_CPU_TO_CONNECTION;  // / max(0.75, options.tuning_kwargs.effective_connection_ratio)
    console.debug("The max_connections variable is determined by the number of logical CPU count " + 
        "with the scale factor of ${__SCALE_FACTOR_CPU_TO_CONNECTION}x.");
    _minimum = Math.max(min_user_conns, total_reserved_connections);
    max_connections = cap_value(ceil(options.vcpu * _upscale), _minimum, max_user_conns) + total_reserved_connections;
    console.debug("max_connections: ${max_connections}");
    return max_connections;
}

function _GetReservedConns(options, minimum, maximum, superuser_mode = false, base_reserved_connection = null) {
    if (base_reserved_connection == null) {
        base_reserved_connection = __BASE_RESERVED_DB_CONNECTION;
    }
    // 1.5x here is heuristically defined to limit the number of superuser reserved connections
    if (!superuser_mode) {
        reserved_connections = options.vcpu / __DESCALE_FACTOR_RESERVED_DB_CONNECTION;
    } else { 
        superuser_heuristic_percentage = options.tuning_kwargs.superuser_reserved_connections_scale_ratio;
        descale_factor = __DESCALE_FACTOR_RESERVED_DB_CONNECTION * superuser_heuristic_percentage;
        reserved_connections = int(options.vcpu / descale_factor);
    }
    return cap_value(reserved_connections, minimum, maximum) + base_reserved_connection;
}

function _CalcEffectiveCacheSize(group_cache, global_cache, options, response) {
    /*
    The following setup made by the Azure PostgreSQL team. The reason is that their tuning guideline are better as 
    compared as what I see in AWS PostgreSQL. The Azure guideline is to take the available 
    memory (RAM - shared_buffers):
    https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/server-parameters-table-query-tuning-planner-cost-constants?pivots=postgresql-17#effective_cache_size
    and https://dba.stackexchange.com/questions/279348/postgresql-does-effective-cache-size-includes-shared-buffers
    Default is half of physical RAM memory on most tuning guideline
    */
    pgmem_available = int(options.usable_ram);    // Make a copy
    pgmem_available -= global_cache['shared_buffers'];
    _mem_conns = _GetMemConnInTotal(options, response, use_reserved_connection=false, use_full_connection=true);
    pgmem_available -= _mem_conns * options.tuning_kwargs.memory_connection_to_dedicated_os_ratio;

    // Re-align the number (always use the lower bound for memory safety)
    effective_cache_size = pgmem_available * options.tuning_kwargs.effective_cache_size_available_ratio;
    effective_cache_size = realign_value(int(effective_cache_size), page_size=DB_PAGE_SIZE)[options.align_index];
    console.debug("Effective cache size: ${floor(effective_cache_size / Mi)}MiB");
    return effective_cache_size;
}

function _CalcWalBuffers(group_cache, global_cache, options, response, minimum, maximum) {
    /*
    See this article: https://www.cybertec-postgresql.com/en/wal_level-what-is-the-difference/
    It is only benefit when you use COPY instead of SELECT. For other thing, the spawning of
    WAL buffers is not necessary. We don't care the large of one single WAL file 
    */
    shared_buffers = global_cache['shared_buffers'];
    usable_ram_noswap = options.usable_ram;
    function fn(x) {
        return 1024 * (37.25 * log(x) + 2) * 0.90;  // Measure in KiB
    } 
    oldstyle_wal_buffers = min(floor(shared_buffers / 32), options.tuning_kwargs.wal_segment_size);  // Measured in bytes
    wal_buffers = max(oldstyle_wal_buffers, fn(usable_ram_noswap / Gi) * Ki);
    return realign_value(cap_value(ceil(wal_buffers), minimum, maximum), page_size=DB_PAGE_SIZE)[options.align_index];
}

// ----------------------------------------------------------------------------------------------------------------
_DB_CONN_PROFILE = {
    // Connections
    'superuser_reserved_connections': {
        'instructions': {
            'mini': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 3, superuser_mode=true, base_reserved_connection=1),
            'medium': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 5, superuser_mode=true, base_reserved_connection=2),
        },
        'tune_op': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 10, superuser_mode=true),
        'default': __BASE_RESERVED_DB_CONNECTION,
    },
    'reserved_connections': {
        'instructions': {
            'mini': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 3, superuser_mode=false, base_reserved_connection=1),
            'medium': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 5, superuser_mode=false, base_reserved_connection=2),
        },
        'tune_op': (group_cache, global_cache, options, response) => _GetReservedConns(options, 0, 10, superuser_mode=false),
        'default': __BASE_RESERVED_DB_CONNECTION,
    },
    'max_connections': {
        'instructions': {
            'mini': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 10, 30),
            'medium': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 15, 65),
            'large': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 30, 100),
            'mall': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 40, 175),
            'bigt': (group_cache, global_cache, options, response) => _GetMaxConns(options, group_cache, 50, 250),
        },
        'default': 30,
    },
    'listen_addresses': {
        'default': '*',
    }
}

_DB_RESOURCE_PROFILE = {
    // Memory and CPU
    'shared_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcSharedBuffers(options),
        'default': 128 * Mi,
        'partial_func': (value) => "${floor(value / Mi)}MB",
    },
    'temp_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcTempBuffers(group_cache, global_cache, options, response),
        'default': 8 * Mi,
        'partial_func': (value) => "${floor(value / DB_PAGE_SIZE) * floor(DB_PAGE_SIZE / Ki)}kB",
    },
    'work_mem': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcWorkMem(group_cache, global_cache, options, response),
        'default': 4 * Mi,
        'partial_func': (value) => "${floor(value / DB_PAGE_SIZE) * floor(DB_PAGE_SIZE / Ki)}kB",
    },
    'hash_mem_multiplier': {
        'default': 2.0,
    },
}

_DB_VACUUM_PROFILE = {
    // Memory and Worker
    'autovacuum': {
        'default': 'on',
    },
    'autovacuum_max_workers': {
        'instructions': {
            'mini_default': 1,
            'medium_default': 2,
            'large': (group_cache, global_cache, options, response) => cap_value(floor(options.vcpu / 4) + 1, 2, 5),
            'mall': (group_cache, global_cache, options, response) => cap_value(floor(options.vcpu / 3.5) + 1, 3, 6),
            'bigt': (group_cache, global_cache, options, response) => cap_value(floor(options.vcpu / 3) + 1, 3, 8),
        },
        'default': 3,
        'hardware_scope': 'cpu',
    },
    'autovacuum_naptime': {
        'tune_op': (group_cache, global_cache, options, response) => SECOND * (15 + 30 * (group_cache['autovacuum_max_workers'] - 1)),
        'default': 1 * MINUTE,
        'partial_func': (value) => "${floor(value / SECOND)}s",
    },
    'maintenance_work_mem': {
        'tune_op': (group_cache, global_cache, options, response) => _CalcTempBuffersAndWorkMem(group_cache, global_cache, options, response)[1],
        'default': 64 * Mi,
        'post-condition-group': (value, cache, options) => value * cache['autovacuum_max_workers'] < floor(options.usable_ram / 2),
        'partial_func': (value) => "${floor(value / Mi)}MB",
    },
    'autovacuum_work_mem': {
        'default': -1,
    },
    // Threshold and Scale Factor: For the information, I would use the [08] as the base optimization profile and could 
    // be applied on most scenarios, except that you are having an extremely large table where 0.1% is too large.
    'autovacuum_vacuum_threshold; autovacuum_vacuum_insert_threshold; autovacuum_analyze_threshold': {
        'instructions': {
            'mini_default': floor(K10 / 2),
        },
        'hardware_scope': 'overall',
        'default': 2 * K10,
    },
    'autovacuum_vacuum_scale_factor; autovacuum_vacuum_insert_scale_factor; autovacuum_analyze_scale_factor': {
        'instructions': {
            'mini_default': 0.010,
            'mall_default': 0.002,
            'bigt_default': 0.002,
        },
        'hardware_scope': 'overall',
        'default': 0.005,
    },
    'autovacuum_vacuum_cost_delay': {
        'default': 2,
        'partial_func': (value) => "${value}ms",
    },
    'autovacuum_vacuum_cost_limit': {
        'default': -1,
    },
    'vacuum_cost_delay': {
        'default': 0,
        'partial_func': (value) => "${value}s",
    },
    'vacuum_cost_limit': {
        'instructions': {
            'large_default': 500,
            'mall_default': K10,
            'bigt_default': K10,
        },
        'default': 200,
    },
    'vacuum_cost_page_hit': {
        'default': 1,
    },
    'vacuum_cost_page_miss': {
        'default': 2,
    },
    'vacuum_cost_page_dirty': {
        'default': 20,
    },
    // Transaction ID and MultiXact
    // See here: https://postgresqlco.nf/doc/en/param/autovacuum_freeze_max_age/
    // and https://www.youtube.com/watch?v=vtjjaEVPAb8 at (30:02)
    'autovacuum_freeze_max_age': {
        'default': 500 * M10,
    },
    'vacuum_freeze_table_age': {
        'tune_op': (group_cache, global_cache, options, response) => realign_value(ceil(group_cache['autovacuum_freeze_max_age'] * 0.85), page_size=250 * K10)[options.align_index],
        'default': 150 * M10,
    },
    'vacuum_freeze_min_age': {
        'default': 50 * M10,
    },
    'autovacuum_multixact_freeze_max_age': {
        'default': 850 * M10,
    },
    'vacuum_multixact_freeze_table_age': {
        'tune_op': (group_cache, global_cache, options, response) => realign_value(ceil(group_cache['autovacuum_multixact_freeze_max_age'] * 0.85), page_size=250 * K10)[options.align_index],
        'default': 150 * M10,
    },
    'vacuum_multixact_freeze_min_age': {
        'default': 5 * M10,
    },
}

_DB_BGWRITER_PROFILE = {
    // We don't tune the bgwriter_flush_after = 512 KiB as it is already optimal and PostgreSQL said we don't need
    // to tune it
    'bgwriter_delay': {
        'default': 300,
        'hardware_scope': 'overall',
        'partial_func': (value) => "${value}ms",
    },
    'bgwriter_lru_maxpages': {
        'instructions': {
            'large_default': 350,
            'mall_default': 425,
            'bigt_default': 500,
        },
        'default': 300,
    },
    'bgwriter_lru_multiplier': {
        'default': 2.0,
    },
    'bgwriter_flush_after': {
        'default': 512 * Ki,
        'partial_func': (value) => "${floor(value / Ki)}kB",
    },
}

_DB_ASYNC_DISK_PROFILE = {
    'effective_io_concurrency': {
        'default': 16,
    },
    'maintenance_io_concurrency': {
        'default': 10,
    },
    'backend_flush_after': {
        'default': 0,
    },
}

_DB_ASYNC_CPU_PROFILE = {
    'max_worker_processes': {
        'tune_op': (group_cache, global_cache, options, response) => cap_value(ceil(options.vcpu * 1.5) + 2, 4, 512),
        'default': 8,
    },
    'max_parallel_workers': {
        'tune_op': (group_cache, global_cache, options, response) => min(cap_value(ceil(options.vcpu * 1.125), 4, 512), group_cache['max_worker_processes']),
        'default': 8,
    },
    'max_parallel_workers_per_gather': {
        'tune_op': (group_cache, global_cache, options, response) => min(cap_value(ceil(options.vcpu / 3), 2, 32), group_cache['max_parallel_workers']),
        'default': 2,
    },
    'max_parallel_maintenance_workers': {
        'tune_op': (group_cache, global_cache, options, response) => min(cap_value(ceil(options.vcpu / 2), 2, 32), group_cache['max_parallel_workers']),
        'default': 2,
    },
    'min_parallel_table_scan_size': {
        'instructions': {
            'medium_default': 16 * Mi,
            'large_default': 24 * Mi,
            'mall_default': 32 * Mi,
            'bigt_default': 32 * Mi,
        },
        'default': 8 * Mi,
        'partial_func': (value) => '${floor(value / DB_PAGE_SIZE) * floor(DB_PAGE_SIZE / Ki)}kB',
    },
    'min_parallel_index_scan_size': {
        'tune_op': (group_cache, global_cache, options, response) => max(group_cache['min_parallel_table_scan_size'] / 16, 512 * Ki),
        'default': 512 * Ki,
        'partial_func': (value) => '${floor(value / DB_PAGE_SIZE) * floor(DB_PAGE_SIZE / Ki)}kB',
    },
}

_DB_WAL_PROFILE = {
    // For these settings, please refer to the [13] and [14] for more information
    'wal_level': {
        'default': 'replica',
    },
    'synchronous_commit': {
        'default': 'on',
    },
    'full_page_writes': {
        'default': 'on',
    },
    'fsync': {
        'default': 'on',
    },
    'wal_compression': {
        'default': 'pglz',
    },
    'wal_init_zero': {
        'default': 'on',
    },
    'wal_recycle': {
        'default': 'on',
    },
    'wal_log_hints': {
        'default': 'on',

    },
    // See Ref [16-19] for tuning the wal_writer_delay and commit_delay
    'wal_writer_delay': {
        'instructions': {
            "mini_default": K10,
        },
        'default': 200,
        'partial_func': (value) => "${value}ms",
    },
    'wal_writer_flush_after': {
        'default': 1 * Mi,
        'partial_func': (value) => "${floor(value / Mi)}MB",
    },
    // This setting means that when you have at least 5 transactions in pending, the delay (interval by commit_delay)
    // would be triggered (assuming maybe more transactions are coming from the client or application level)
    // ============================== CHECKPOINT ==============================
    // Checkpoint tuning are based on [20-23]: Our wishes is to make the database more reliable and perform better,
    // but reducing un-necessary read/write operation
    'checkpoint_timeout': {
        'instructions': {
            'mini_default': 30 * MINUTE,
            'mall_default': 10 * MINUTE,
            'bigt_default': 10 * MINUTE,
        },
        'default': 15 * MINUTE,
        'hardware_scope': 'overall',
        'partial_func': (value) => '${floor(value / MINUTE)}min',
    },
    'checkpoint_flush_after': {
        'default': 256 * Ki,
        'partial_func': (value) => '${floor(value / Ki)}kB',
    },
    'checkpoint_completion_target': {
        'default': 0.9,
    },
    'checkpoint_warning': {
        'default': 30,
        'partial_func': (value) => "${value}s",
    },
    // ============================== WAL SIZE ==============================
    'min_wal_size': {
        'tune_op': (group_cache, global_cache, options, response) => 10 * options.tuning_kwargs.wal_segment_size,
        'default': 10 * BASE_WAL_SEGMENT_SIZE,
        'partial_func': (value) => '${floor(value / Mi)}MB',
    },
    'max_wal_size': {
        'instructions': {
            'mini_default': 2 * Gi,
            'medium_default': 4 * Gi,
            'large_default': 8 * Gi,
            'mall_default': 16 * Gi,
            'bigt_default': 32 * Gi,
        },
        'default': 8 * Gi,
        'partial_func': (value) => '${floor(value / Mi)}MB',
    },
    'wal_buffers': {
        'tune_op': (group_cache, global_cache, options, response) => 
            _CalcWalBuffers(group_cache, global_cache, options, response, minimum=floor(BASE_WAL_SEGMENT_SIZE / 2), 
                            maximum=BASE_WAL_SEGMENT_SIZE * 16),
        'default': 2 * BASE_WAL_SEGMENT_SIZE,
        'hardware_scope': 'mem',
    },
    // ============================== ARCHIVE && RECOVERY ==============================
    'archive_mode': {
        'default': 'on',
    },
    'archive_timeout': {
        'instructions': {
            'mini_default': 1 * HOUR,
            'mall_default': 30 * MINUTE,
            'bigt_default': 30 * MINUTE,
        },
        'default': 45 * MINUTE,
        'hardware_scope': 'overall',
        'partial_func': (value) => '${value}s',
    },
}

_DB_RECOVERY_PROFILE = {
    'recovery_end_command': {
        'default': 'pg_ctl stop -D $PGDATA',
    },
}

_DB_REPLICATION_PROFILE = {
    // Sending Servers
    'max_wal_senders': {
        'default': 3,
        'hardware_scope': 'net',
    },
    'max_replication_slots': {
        'default': 3,
        'hardware_scope': 'net',
    },
    'wal_keep_size': {
        // Don't worry since if you use replication_slots, its default is -1 (keep all WAL); but if replication
        // for disaster recovery (not for offload READ queries or high-availability)
        'default': 25 * BASE_WAL_SEGMENT_SIZE,
        'partial_func': (value) => '${floor(value / Mi)}MB',
    },
    'max_slot_wal_keep_size': {
        'default': -1,
    },
    'wal_sender_timeout': {
        'instructions': {
            'mall_default': 2 * MINUTE,
            'bigt_default': 2 * MINUTE,
        },
        'default': MINUTE,
        'hardware_scope': 'net',
        'partial_func': (value) => '${value}s',
    },
    'track_commit_timestamp': {
        'default': 'on',
    },
    'logical_decoding_work_mem': {
        'tune_op': (group_cache, global_cache, options, response) => 
            realign_value(cap_value(floor(group_cache['maintenance_work_mem'] / 8), 32 * Mi, 2 * Gi), 
        page_size=DB_PAGE_SIZE)[options.align_index],
        'default': 64 * Mi,
    },
}

_DB_QUERY_PROFILE = {
    // Query tuning
    'seq_page_cost': {
        'default': 1.0,
    },
    'random_page_cost': {
        'default': 2.60,
    },
    'cpu_tuple_cost': {
        'default': 0.03,
    },
    'cpu_index_tuple_cost': {
        'default': 0.005,
    },
    'cpu_operator_cost': {
        'default': 0.001,
    },
    'effective_cache_size': {
        'tune_op': _CalcEffectiveCacheSize,
        'default': 4 * Gi,
        'partial_func': (value) => "${floor(value / Mi)}MB",
    },
    'default_statistics_target': {
        'instructions': {
            'large_default': 300,
            'mall_default': 400,
            'bigt_default': 500,
        },
        'default': 100,
    },
    // Join and Parallelism (TODO)
    'join_collapse_limit': {
        'instructions': {
            'large_default': 12,
            'mall_default': 16,
            'bigt_default': 20,
        },
        'default': 8,
    },
    'from_collapse_limit': {
        'instructions': {
            'large_default': 12,
            'mall_default': 16,
            'bigt_default': 20,
        },
        'default': 8,
    },
    'plan_cache_mode': {
        'default': 'auto',
    },
    'geqo': {
        'default': 'on',
    },
    'geqo_threshold': {
        'instructions': {
            'large_default': 12,
            'mall_default': 16,
            'bigt_default': 20,
        },
        'default': 8,
    },
    'geqo_effort': {
        'instructions': {
            'large_default': 4,
            'mall_default': 5,
            'bigt_default': 6,
        },
        'default': 3,
    },
    'geqo_pool_size': {
        'default': 0,
    },
    'geqo_generations': {
        'default': 0,
    },
    'geqo_selection_bias': {
        'default': 2.0,
    },
    'geqo_seed': {
        'default': 0,
    },
    // Parallelism
    'parallel_setup_cost': {
        'instructions': {
            'mall_default': 750,
            "bigt_default": 500,
        },
        'default': 1000,
    },
    'parallel_tuple_cost': {
        'instructions': {
            'large': (group_cache, global_cache, options, response) => min(group_cache['cpu_tuple_cost'] * 10, 0.1),
            'mall': (group_cache, global_cache, options, response) => min(group_cache['cpu_tuple_cost'] * 10, 0.1),
            'bigt': (group_cache, global_cache, options, response) => min(group_cache['cpu_tuple_cost'] * 10, 0.1),
        },
        'default': 0.1,
    },
    // Commit Behaviour
    'commit_delay': {
        'instructions': {
            'large_default': 500,
            'mall_default': 500,
            'bigt_default': 200,
        },
        'default': 1 * K10,
        'hardware_scope': 'overall',
    },
    'commit_siblings': {
        'instructions': {
            "large_default": 8,
            "mall_default": 10,
            "bigt_default": 10,
        },
        'default': 5,
        'hardware_scope': 'overall',
    },
    // Statistics
    'track_activity_query_size': {
        'default': 2 * Ki,
        'partial_func': (value) => '${value}B',
    },
    'track_counts': {
        'default': 'on',
    },
    'track_io_timing': {
        'default': 'on',
        'hardware_scope': 'cpu',
    },
}

_DB_LOG_PROFILE = {
    // Where to Log
    'logging_collector': {
        'default': 'on',
    },
    'log_destination': {
        'default': 'stderr',
    },
    'log_directory': {
        'default': 'log',
    },
    'log_filename': {
        'default': 'postgresql-%Y-%m-%d_%H%M.log',
    },
    'log_rotation_age': {
        // For best-case it is good to make the log rotation happens by time-based rather than size-based
        'instructions': {
            'mini_default': 3 * DAY,
            'mall_default': 6 * HOUR,
            'bigt_default': 4 * HOUR,
        },
        'default': 1 * DAY,
        'partial_func': (value) => "${floor(value / HOUR)}h",
    },
    'log_rotation_size': {
        'instructions': {
            'mini_default': 32 * Mi,
            'medium_default': 64 * Mi,
        },
        'default': 256 * Mi,
        'partial_func': (value) => "${floor(value / Mi)}MB",
    },
    'log_truncate_on_rotation': {
        'default': 'on',
    },
    // What to log
    'log_autovacuum_min_duration': {
        'default': 300 * K10,
        'partial_func': (value) => "${floor(value / K10)}s",
    },
    'log_checkpoints': {
        'default': 'on',
    },
    'log_connections': {
        'default': 'on',
    },
    'log_disconnections': {
        'default': 'on',
    },
    'log_duration': {
        'default': 'on',
    },
    'log_error_verbosity': {
        'default': 'VERBOSE',
    },
    'log_line_prefix': {
        'default': '%m [%p] %quser=%u@%r@%a_db=%d,backend=%b,xid=%x %v,log=%l',
    },
    'log_lock_waits': {
        'default': 'on',
    },
    'log_recovery_conflict_waits': {
        'default': 'on',
    },
    'log_statement': {
        'default': 'mod',
    },
    'log_replication_commands': {
        'default': 'on',
    },
    'log_min_duration_statement': {
        'default': 2 * K10,
        'partial_func': (value) => "{value}ms",
    },
    'log_min_error_statement': {
        'default': 'ERROR',
    },
    'log_parameter_max_length': {
        'tune_op': (group_cache, global_cache, options, response) => global_cache['track_activity_query_size'],
        'default': -1,
        'partial_func': (value) => "${value}B",
    },
    'log_parameter_max_length_on_error': {
        'tune_op': (group_cache, global_cache, options, response) => global_cache['track_activity_query_size'],
        'default': -1,
        'partial_func': (value) => "${value}B",
    },
}

_DB_TIMEOUT_PROFILE = {
    // Transaction Timeout should not be moved away from default, but we can customize the statement_timeout and
    // lock_timeout
    // Add +1 seconds to avoid checkpoint_timeout happens at same time as idle_in_transaction_session_timeout
    'idle_in_transaction_session_timeout': {
        'default': 5 * MINUTE + 1,
        'partial_func': (value) => "${value}s",
    },
    'statement_timeout': {
        'default': 0,
        'partial_func': (value) => "${value}s",
    },
    'lock_timeout': {
        'default': 0,
        'partial_func': (value) => "${value}s",
    },
    'deadlock_timeout': {
        'default': 1 * SECOND,
        'partial_func': (value) => "${value}s",
    },
}

// Library (You don't need to tune these variable as they are not directly related to the database performance)
_DB_LIB_PROFILE = {
    'shared_preload_libraries': {
        'default': 'auto_explain,pg_prewarm,pgstattuple,pg_stat_statements,pg_buffercache,pg_visibility',   // pg_repack, Not pg_squeeze
    },
    // Auto Explain
    'auto_explain.log_min_duration': {
        'tune_op': (group_cache, global_cache, options, response) => 
            realign_value(int(global_cache['log_min_duration_statement'] * 1.5), page_size=20)[options.align_index],
        'default': -1,
        'partial_func': (value) => "${value}ms",
    },
    'auto_explain.log_analyze': {
        'default': 'off',
    },
    'auto_explain.log_buffers': {
        'default': 'on',
    },
    'auto_explain.log_wal': {
        'default': 'on',
    },
    'auto_explain.log_settings': {
        'default': 'off',
    },
    'auto_explain.log_triggers': {
        'default': 'off',
    },
    'auto_explain.log_verbose': {
        'default': 'on',
    },
    'auto_explain.log_format': {
        'default': 'text',
    },
    'auto_explain.log_level': {
        'default': 'LOG',
    },
    'auto_explain.log_timing': {
        'default': 'on',
    },
    'auto_explain.log_nested_statements': {
        'default': 'off',
    },
    'auto_explain.sample_rate': {
        'default': 1.0,
    },
    // PG_STAT_STATEMENTS
    'pg_stat_statements.max': {
        'instructions': {
            'large_default': 10 * K10,
            'mall_default': 15 * K10,
            'bigt_default': 20 * K10,
        },
        'default': 5 * K10,
    },
    'pg_stat_statements.track': {
        'default': 'all',
    },
    'pg_stat_statements.track_utility': {
        'default': 'on',
    },
    'pg_stat_statements.track_planning': {
        'default': 'off',
    },
    'pg_stat_statements.save': {
        'default': 'on',
    },
}

// Validate and remove the invalid library configuration
const preload_libraries = new Set(_DB_LIB_PROFILE['shared_preload_libraries']['default'].split(','));
for (const key of Object.keys(_DB_LIB_PROFILE)) {
    if (key.includes('.') && !preload_libraries.has(key.split('.')[0])) {
        delete _DB_LIB_PROFILE[key];
    }
}

export const DB0_CONFIG_PROFILE = {
    "connection": [PG_SCOPE.CONNECTION, _DB_CONN_PROFILE, { hardware_scope: 'cpu' }],
    "memory": [PG_SCOPE.MEMORY, _DB_RESOURCE_PROFILE, { hardware_scope: 'mem' }],
    "maintenance": [PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, { hardware_scope: 'overall' }],
    "background_writer": [PG_SCOPE.OTHERS, _DB_BGWRITER_PROFILE, { hardware_scope: 'disk' }],
    "asynchronous_disk": [PG_SCOPE.OTHERS, _DB_ASYNC_DISK_PROFILE, { hardware_scope: 'disk' }],
    "asynchronous_cpu": [PG_SCOPE.OTHERS, _DB_ASYNC_CPU_PROFILE, { hardware_scope: 'cpu' }],
    "wal": [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_WAL_PROFILE, { hardware_scope: 'disk' }],
    "query": [PG_SCOPE.QUERY_TUNING, _DB_QUERY_PROFILE, { hardware_scope: 'cpu' }],
    "log": [PG_SCOPE.LOGGING, _DB_LOG_PROFILE, { hardware_scope: 'disk' }],
    "replication": [PG_SCOPE.ARCHIVE_RECOVERY_BACKUP_RESTORE, _DB_REPLICATION_PROFILE, { hardware_scope: 'disk' }],
    "timeout": [PG_SCOPE.OTHERS, _DB_TIMEOUT_PROFILE, { hardware_scope: 'overall' }],
    "lib": [PG_SCOPE.EXTRA, _DB_LIB_PROFILE, { hardware_scope: 'overall' }],
};
merge_extra_info_to_profile(DB0_CONFIG_PROFILE);
type_validation(DB0_CONFIG_PROFILE);
