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
import { Ki, K10, Mi, Gi, APP_NAME_UPPER, DB_PAGE_SIZE, PG_ARCHIVE_DIR, DAY, MINUTE, HOUR, SECOND, PG_LOG_DIR,
    BASE_WAL_SEGMENT_SIZE, M10 } from './static_vars.js';
import { ceil, log, floor } from math;



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
    _logger.debug(`shared_buffers: ${bytesize_to_hr(shared_buffers)}`);
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
    _logger.debug(`temp_buffers: ${bytesize_to_hr(temp_buffers)}`);
    _logger.debug(`work_mem: ${bytesize_to_hr(work_mem)}`);
    
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
    console.debug("Effective cache size: ${bytesize_to_hr(effective_cache_size)}");
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
        'comment': 'Maximum size to let the WAL grow during automatic checkpoints (soft limit only); WAL size can '
                   'exceed :var:`max_wal_size` under special circumstances such as heavy load, a failing '
                   ':var:`archive_command` or :var:`archive_library`, or a high :var:`wal_keep_size` setting.',
        'partial_func': lambda value: f'{value // Mi}MB',
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
        'partial_func': lambda value: f'{value // DB_PAGE_SIZE * (DB_PAGE_SIZE // Ki)}kB',
        # 'partial_func': lambda value: f'{value // Mi}MB',   # No need high-precision result to translate as KiB
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
            'mini_default': 1 * HOUR,
            'mall_default': 30 * MINUTE,
            'bigt_default': 30 * MINUTE,
        },
        'default': 45 * MINUTE,
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
                   'general system and up to 1 hour on smaller scale.',
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

export default DB0_CONFIG_PROFILE



// ----------------------------------------------------------------------------------------------------------------
// Python code
from functools import partial
from pydantic import ByteSize
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.scope import PG_SCOPE, PGTUNER_SCOPE
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.pg_dataclass import PG_TUNE_RESPONSE
from src.tuner.profile.common import merge_extra_info_to_profile, type_validation
from src.utils.pydantic_utils import (bytesize_to_hr, realign_value, cap_value, )

# =============================================================================



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
                   'default is 3. The value 0 means replication is disabled. Abrupt disconnection of a streaming '
                   'client might leave an orphaned connection slot behind until a timeout is reached, so this '
                   'parameter should be set slightly higher than the maximum number of expected clients so '
                   'disconnected clients can immediately reconnect.'
    },
    'max_replication_slots': {
        'default': 3,
        'hardware_scope': 'net',
        'comment': 'Specifies the maximum number of replication slots (see streaming-replication-slots) that the '
                   'server can support. The default is 3. This parameter can only be set at server start. Setting '
                   'it to a lower value than the number of currently existing replication slots will prevent the '
                   'server from starting. Also, wal_level must be set to replica or higher to allow replication '
                   'slots to be used.'
    },
    'wal_keep_size': {
        # Don't worry since if you use replication_slots, its default is -1 (keep all WAL); but if replication
        # for disaster recovery (not for offload READ queries or high-availability)
        'default': 25 * BASE_WAL_SEGMENT_SIZE,
        'comment': 'Specifies the minimum size of past WAL files kept in the pg_wal directory, in case a standby '
                   'server needs to fetch them for streaming replication. If a standby server connected to the '
                   'sending server falls behind by more than wal_keep_size megabytes, the sending server might '
                   'remove a WAL segment still needed by the standby (e.x pg_archivecleanup), resulting in downstream '
                   'connections will also eventually fail as a result. If you required DR server to catch up more with '
                   'latest data, reduce this value more. The default is maximum of 25 WAL files.',
        'partial_func': lambda value: f'{value // Mi}MB',
    },
    'max_slot_wal_keep_size': {
        'default': -1,
        'comment': 'Specify the maximum size of WAL files that replication slots are allowed to retain in the pg_wal '
                   'directory at checkpoint time for replication slots. If max_slot_wal_keep_size is -1 (the default), '
                   'replication slots may retain an unlimited amount of WAL files. Otherwise, if restart_lsn of a '
                   'replication slot falls behind the current LSN by more than the given size, the standby using the '
                   'slot may no longer be able to continue replication due to removal of required WAL files. You can '
                   'see the WAL availability of replication slots in pg_replication_slots.'
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
        realign_value(cap_value(global_cache['maintenance_work_mem'] // 8, 32 * Mi, 2 * Gi), page_size=DB_PAGE_SIZE)[options.align_index],
        'default': 64 * Mi,
        'comment': "Specifies the maximum amount of memory to be used by logical decoding, before some of the decoded "
                   "changes are written to local disk. This limits the amount of memory used by logical streaming "
                   "replication connections. It defaults to 64 megabytes (64MB). Since each replication connection "
                   "only uses a single buffer of this size, and an installation normally doesn't have many such "
                   "connections concurrently (as limited by max_wal_senders), it's safe to set this value significantly "
                   "higher than work_mem, reducing the amount of decoded changes written to disk. Note that this "
                   "variable is available on the subscribers or the receiving server, not the sending server.",
        'partial_func': lambda value: f'{value // Mi}MB',
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
        'partial_func': lambda value: f"{value // Mi}MB",
    },
    'default_statistics_target': {
        'instructions': {
            'large_default': 300,
            'mall_default': 400,
            'bigt_default': 500,
        },
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
        'default': 'log', # PG_LOG_DIR,
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
        'partial_func': lambda value: f"{value // Mi}MB",
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
        'default': 'auto_explain,pg_prewarm,pgstattuple,pg_stat_statements,pg_buffercache,pg_visibility',   # pg_repack, Not pg_squeeze
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
        realign_value(int(global_cache['log_min_duration_statement'] * 1.5), page_size=20)[options.align_index],
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
        'comment': 'auto_explain.log_settings controls whether the current settings are printed when an execution plan '
                   "is logged; it's equivalent to the SETTINGS option of EXPLAIN. This parameter has no effect unless "
                   'auto_explain.log_analyze is enabled.',
    },
    'auto_explain.log_triggers': {
        'default': 'off',
        'comment': 'auto_explain.log_triggers controls whether trigger statistics are printed when an execution plan '
                   "is logged; it's equivalent to the TRIGGER option of EXPLAIN. This parameter has no effect unless "
                   'auto_explain.log_analyze is enabled.',
    },
    'auto_explain.log_verbose': {
        'default': 'on',
        'comment': 'auto_explain.log_verbose controls whether the output of EXPLAIN VERBOSE is included in the '
                   'auto_explain output. The default is on.',
    },
    'auto_explain.log_format': {
        'default': 'text',
        'comment': 'auto_explain.log_format controls the format of the output of auto_explain. The allowed values are '
                   'text, xml, json, and yaml.',
    },
    'auto_explain.log_level': {
        'default': 'LOG',
        'comment': 'auto_explain.log_level controls the log level at which auto_explain messages are emitted. The '
                   'allowed values are DEBUG5 to DEBUG1, INFO, NOTICE, WARNING, ERROR, LOG, FATAL, and PANIC.',
    },
    'auto_explain.log_timing': {
        'default': 'on',
        'comment': 'auto_explain.log_timing controls whether per-node timing information is printed when an execution '
                   "plan is logged; it's equivalent to the TIMING option of EXPLAIN. The overhead of repeatedly "
                   'reading the system clock can slow down queries significantly on some systems, so it may be useful '
                   'to set this parameter to off when only actual row counts, and not exact times, are needed. This '
                   'parameter has no effect unless auto_explain.log_analyze is enabled.'
    },
    'auto_explain.log_nested_statements': {
        'default': 'off',
        'comment': 'auto_explain.log_nested_statements causes nested statements (statements executed inside a function) '
                   'to be considered for logging. When it is off, only top-level query plans are logged.',
    },
    'auto_explain.sample_rate': {
        'default': 1.0,
        'comment': 'auto_explain.sample_rate causes auto_explain to only explain a fraction of the statements in '
                   'each session. The default is 1, meaning explain all the queries. In case of nested statements, '
                   'either all will be explained or none.',
    },
    # PG_STAT_STATEMENTS
    'pg_stat_statements.max': {
        'instructions': {
            'large_default': 10 * K10,
            'mall_default': 15 * K10,
            'bigt_default': 20 * K10,
        },
        'default': 5 * K10,
        'comment': 'pg_stat_statements.max is the maximum number of statements tracked by the module (i.e., the '
                   'maximum number of rows in the pg_stat_statements view). If more distinct statements than that are '
                   'observed, information about the least-executed statements is discarded. The number of times such '
                   'information was discarded can be seen in the pg_stat_statements_info view. Default to 5K, reached '
                   'to 10-20K on large system.',
    },
    'pg_stat_statements.track': {
        'default': 'all',
        'comment': 'pg_stat_statements.track controls which statements are counted and reported in the pg_stat_statements '
                   'view. The allowed values are none, top, and all. top tracks only the top-level statements executed '
                   'by clients. all tracks all statements executed by clients. none disables tracking entirely. The '
                   'default is top.',
    },
    'pg_stat_statements.track_utility': {
        'default': 'on',
        'comment': 'pg_stat_statements.track_utility controls whether utility commands are tracked by the module. '
                   'Utility commands are all those other than SELECT, INSERT, UPDATE, DELETE, and MERGE. Default to on',
    },
    'pg_stat_statements.track_planning': {
        'default': 'off',
        'comment': 'pg_stat_statements.track_planning controls whether planning operations and duration are tracked '
                   'by the module. Enabling this parameter may incur a noticeable performance penalty, especially '
                   'when statements with identical query structure are executed by many concurrent connections which '
                   'compete to update a small number of pg_stat_statements entries.',
    },
    'pg_stat_statements.save': {
        'default': 'on',
        'comment': 'pg_stat_statements.save controls whether the statistics gathered by pg_stat_statements are saved '
                   'across server shutdowns and restarts. Default to on.',
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
    'maintenance': (PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, {'hardware_scope': 'overall'}),
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
