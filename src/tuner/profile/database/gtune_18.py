import logging
from copy import deepcopy

from pydantic import ByteSize

from src.tuner.data.scope import PG_SCOPE
from src.tuner.profile.common import merge_extra_info_to_profile, rewrite_items, type_validation
from src.tuner.profile.database.gtune_17 import DB17_CONFIG_PROFILE
from src.utils.pydantic_utils import cap_value
from src.utils.static import APP_NAME_UPPER, Ki, G10

__all__ = ['DB18_CONFIG_PROFILE']
_SIZING = ByteSize | int | float
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
_DB_ASYNC_DISK_PROFILE = {
    # io_max_combine_limit can be seen as the threshold per process, and is capped by the multiple
    # value in src/backend/storage/aio/aio_init.c (You can find all the definition in here)
    # mul_size(s1, s2): This function is returning the product of two size_t values, s1 and s2; with overflow checking.
    # AioProcs: Calculate the number of allowed AsyncIO processes, at `MaxBackends` + `NUM_AUXILIARY_PROCS`. See below
    # for more info

    # In this function the total allowance is capped at MaxBackends + NUM_AUXILIARY_PROCS (=6 base processes + 32 max).
    # The MaxBackends here is the number of processes managed by PostgreSQL postmaster and is up to 1024 in total.
    # Detail: src/include/storage/aio_internal.h
    # AioBackendShmemSize = AioProcs() * sizeof(PgAioBackend)
    # AioHandleShmemSize = AioProcs() * io_max_concurrency * sizeof(PgAioHandle)
    # AioHandleIOVShmemSize = sizeof(iovec) * AioProcs() * io_max_concurrency * io_max_combine_limit
    # AioHandleDataShmemSize = AioProcs() * io_max_concurrency * sizeof(PgAioHandle)

    # Meanwhile the MaxBackends is defined at InitializeMaxBackends() in src/backend/utils/init/postinit.c at line 560
    # In src/include/storage/proc.h
    # NUM_AUXILIARY_PROCS = 6 + MAX_IO_WORKERS = 6 + 32 (for bgwriter, checkpointer, WAL writer, WAL summarizer,
    # archiver in normal process. Startup process and WAL receiver also consume 2 slots each, but WAL writer is
    # launched only after startup has exited, so we only need 6 slots).

    # MaxBackends = MaxConnections + autovacuum_worker_slots + max_worker_processes + max_wal_senders + NUM_SPECIAL_WORKER_PROCS;
    # The NUM_SPECIAL_WORKER_PROCS is 2 at line 448 in src/include/storage/proc.h (slotsync worker and autovacuum launcher)

    # This is combined with BackendShmem (
    'io_max_combine_limit': {
        'default': 128 * Ki,
        'comment': 'Controls the largest I/O size in operations that combine I/O, and silently limits the '
                   'user-settable parameter io_combine_limit. or on the server command line. The maximum possible '
                   'size depends on the operating system and block size, but is typically 1MB on Unix and 128kB on '
                   'Windows. The default is 128kB.',
        'partial_func': lambda value: f'{value}s',
    },
    # Take notice that the io_combine_limit when having a large IO fetcher, it is capped by the ring_size_kb of
    # effective_io_concurrency in the line 595 at src/backend/storage/buffer/freelist.c
    # io_combine_limit is already supported in PostgreSQL 17 but since it does not bump to 1 MiB
    # For this see the function AioChooseMaxConcurrency in aio_init.c
    # At -1, you would have cap_value((shared_buffers_in_bytes / DB_PAGE_SIZE) / (MaxBackends + NUM_AUXILIARY_PROCS), 1, 64)
    # For example with 2 GiB of shared_buffers and assume with 50 connections total, it would be 2978 io_max_concurrency
    # without capping so unless you want it to be larger than 64, you can set from 64 -> 1024 to have different.
    # Unless with default shared_buffers of 128 MiB and 100 connections (total), it would still be at 100 so don't worry
    'io_max_concurrency': {
        'default': -1,
        'comment': 'Controls the maximum number of I/O operations that one process can execute simultaneously. The '
                   'default setting of -1 selects a number based on shared_buffers and the maximum number of '
                   'processes (max_connections, guc-autovacuum-worker-slots, max_worker_processes and max_wal_senders), '
                   'but not more than 64.',
    },
    'io_method': {
        'default': 'io_uring',
        'comment': 'Selects the method for executing asynchronous I/O. Possible values are: `worker` (execute '
                   'asynchronous I/O using worker processes), `io_uring` (execute asynchronous I/O using io_uring, '
                   'requires a build with --with-liburing / -Dliburing), and `sync` (execute asynchronous-eligible '
                   'I/O synchronously)',
        # https://pganalyze.com/blog/postgres-18-async-io
        #
    },
    'io_workers': {
        'default': cap_value(3, 1, 32),
        'comment': 'Selects the number of I/O worker processes to use. The default is 3. Only has an effect '
                   'if io_method is set to worker.'
    },
}

_DB_VACUUM_PROFILE = {
    'autovacuum_vacuum_max_threshold': {
        'default': cap_value(100 * G10, -1, 2^31 - 1),
        'comment': 'Specifies the maximum number of updated or deleted tuples needed to trigger a VACUUM in any one '
                   'table, i.e., a limit on the value calculated with autovacuum_vacuum_threshold and '
                   'autovacuum_vacuum_scale_factor. The default is 100,000,000 tuples. If -1 is specified, autovacuum '
                   'will not enforce a maximum number of updated or deleted tuples that will trigger a VACUUM '
                   'operation. This parameter can only be set in the postgresql.conf file or on the server command '
                   'line; but the setting can be overridden for individual tables by changing storage parameters.',
    },
    'autovacuum_worker_slots': {

    },
}

idle_replication_slot_timeout
log_lock_failure
max_active_replication_origins
md5_password_warnings
track_cost_delay_timing
vacuum_max_eager_freeze_failure_rate
vacuum_truncate

# =============================================================================
# Trigger the merge
DB18_CONFIG_MAPPING = {
    'asynchronous-disk': (PG_SCOPE.OTHERS, _DB_ASYNC_DISK_PROFILE, {'hardware_scope': 'disk'}),
    'maintenance': (PG_SCOPE.MAINTENANCE, _DB_VACUUM_PROFILE, {'hardware_scope': 'overall'}),
}
merge_extra_info_to_profile(DB18_CONFIG_MAPPING)
type_validation(DB18_CONFIG_MAPPING)
DB18_CONFIG_PROFILE = deepcopy(DB17_CONFIG_PROFILE)
for k, v in DB18_CONFIG_MAPPING.items():
    if k in DB18_CONFIG_PROFILE:
        # deepmerge(DB18_CONFIG_PROFILE[k][1], v[1], inline_source=True, inline_target=True)
        src_conf = DB18_CONFIG_PROFILE[k][1]
        dst_conf = v[1]
        for k0, v0 in dst_conf.items():
            src_conf[k0] = v0
rewrite_items(DB18_CONFIG_PROFILE)
