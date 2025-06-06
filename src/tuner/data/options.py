import logging
from functools import cached_property
from math import ceil
from typing import Any, Literal
from pydantic import BaseModel, Field, ByteSize
from pydantic.types import PositiveInt, PositiveFloat

from src.utils.static import Gi, Mi, APP_NAME_UPPER, K10, M10, Ki, BASE_WAL_SEGMENT_SIZE
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.workload import PG_WORKLOAD, PG_PROFILE_OPTMODE, PG_BACKUP_TOOL, PG_SIZING
from src.utils.pydantic_utils import bytesize_to_hr

__all__ = ['PG_TUNE_USR_OPTIONS', 'PG_TUNE_USR_KWARGS']
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
# The collection of advanced tuning options
class PG_TUNE_USR_KWARGS(BaseModel):
    """
    This class stored some tuning user|app-defined keywords that could be used to adjust the tuning phase.
    Parameters:
    """
    # Connection
    user_max_connections: int = Field(
        default=0, ge=0, le=1000, frozen=True,
        description='The maximum number of client connections allowed (override by user). Unless necessary required '
                    'to have large number of connections, it is best to use default (set to 0) and if the number of '
                    'user connections exceed 75 then it is better to use connection pooling to minimize connection '
                    'latency, overhead, and memory usage.'
    )
    # This could be increased if your database server is not under hypervisor and run under Xeon_v6, recent AMD EPYC (2020)
    # or powerful ARM CPU, or AMD Threadripper (2020+). But in most cases, the 4x scale factor here is enough to be
    # generalized. Even on PostgreSQL 14, the scaling is significant when the PostgreSQL server is not virtualized and
    # have a lot of CPU to use (> 32 - 96|128 cores).
    cpu_to_connection_scale_ratio: PositiveFloat = Field(
        default=5, ge=2.5, le=10, frozen=True,
        description='The scale ratio of the CPU to the number of connections. The supported range is [2.5, 10], default '
                    'is 5. This value is used to estimate the number of connections that can be handled by the server '
                    'based on the number of CPU cores. The higher value means more connections can be handled by the '
                    'server. From modern perspective, the good ratio is between 4-6, but default to 5 for balanced ' \
                    'performance with less risk for idle connection overhead.'
    )
    cpu_to_parallel_scale_ratio: PositiveFloat = Field(
        default=2.0, ge=1.5, le=3.0, frozen=True,
        description='The scale ratio of the CPU to the number of parallel workers. The supported range is [1.5, 3.0], '
                    'default is 2.0. Since with later version and Linux kernel, the performance of parallelism under '
                    'IO-bound workload is improved, especially the asynchronous parallelism of IO (io_uring), the '
                    'default scale factor may seems weird at first glance., but it is there for a reason. '
    )

    superuser_reserved_connections_scale_ratio: PositiveFloat = Field(
        default=1.5, ge=1, le=3, frozen=True,
        description='The de-scale ratio for the reserved superuser connections over the normal reserved connection. '
                    'The supported range is [1, 3], default is 1.5. Higher value means less superuser reserved '
                    'connection as compared to the normal reserved connection.'
    )
    single_memory_connection_overhead: ByteSize | PositiveInt = Field(
        default=5 * Mi, ge=2 * Mi, le=12 * Mi, frozen=True,
        description='The memory overhead for a single connection at idle state. The supported range is [2 MiB, 12 MiB], '
                    'default is 5 MiB in total. This value is used to estimate the memory usage for each connection; '
                    'and it is advised to not set it too high or change it as it could make the estimation to be '
                    'incorrect (recommend to be between 4 - 8 MiB).'
    )
    memory_connection_to_dedicated_os_ratio: float = Field(
        default=0.7, ge=0.0, le=1.0, frozen=True,
        description='The ratio of the memory connection to the dedicated OS memory rather than shared_buffers of '
                    'the PostgreSQL memory. The supported range is [0, 1], default is 0.7 or 70%. '
    )
    # Memory Utilization (Basic)
    effective_cache_size_available_ratio: PositiveFloat = Field(
        default=0.985, ge=0.95, le=1.0, frozen=True,
        description='The percentage of effective_cache_size over the total PostgreSQL available memory excluding the '
                    'shared_buffers and others. The supported range is [0.95, 1.0], default is 0.985 (98.5%). It is '
                    'recommended to set this value higher than 0.975 but not too close to 1.0 for OS memory page '
                    'reservation against the worst extreme case.'
    )
    shared_buffers_ratio: PositiveFloat = Field(
        default=0.25, ge=0.15, le=0.60, frozen=False,
        description='The starting ratio of shared_buffers to the total non-database memory. The supported range is '
                    '[0.15, 0.60), default is 0.25. If you prioritize the *simple* query that perform more READ '
                    '(SELECT) than WRITE (INSERT/UPDATE/DELETE) between two WRITE interval in the *same* table, '
                    'than you can think of increasing **slowly** this value (1-2% increment change). However, we '
                    'recommend that this value should be below 0.40 to prevent double caching unless you are making a '
                    'read-only database, in-memory database, or a not-good synthetic benchmark. However, if you '
                    'enable the correction_tuning, you should ignore this value.'
    )
    max_work_buffer_ratio: PositiveFloat = Field(
        default=0.1, gt=0, le=0.50, frozen=False,
        description='The starting ratio of the maximum PostgreSQL available memory (after excluding shared_buffers and '
                    'others) to be used in the session-based variable: temp_buffers and work_mem (globally managed). '
                    'The supported range is (0, 0.50], default is 0.1. The algorithm is temp_buffers + work_mem = '
                    '(pgmem_available * max_work_buffer_ratio) / active_user_connections. However, if you enable the '
                    'correction_tuning, you can adjust this value *slowly* to increase the memory budget for query '
                    'operation. Under correction tuning, the absolute difference between :attr:`shared_buffers_ratio` '
                    'and this is maintained consistently and widen/narrow based on the :attr:`mem_pool_tuning_ratio`. '
    )
    effective_connection_ratio: PositiveFloat = Field(
        default=0.75, ge=0.25, le=1.0, frozen=True,
        description='The percentage of the maximum non-reserved connection used to tune temp_buffers and work_mem. '
                    'The supported range is [0.25, 1], default is 0.75. Set to 1 meant that we assume all the normal '
                    'connections use the same temp_buffers and work_mem. Reduce this ratio would increase the '
                    'temp_buffers and work_mem allowed for each connection by assuming not all active connections '
                    'are running complex queries that requires high work_mem or temp_buffers.'
    )
    temp_buffers_ratio: PositiveFloat = Field(
        default=0.25, ge=0.05, le=0.95, frozen=True,
        description='The ratio of temp_buffers to the :attr:`max_work_buffer_ratio` pool above. The supported range is '
                    '[0.05, 0.95], default is 0.25. Increase this value make the temp_buffers larger than the work_mem. '
                    'If you have query that use much temporary object (temporary table, CTE, ...), then increase this '
                    'value; and query involving more WRITE and/or the WRITE query plan is complex involving HASH, '
                    'JOIN, MERGE, ... then decrease this value.'
    )

    # Memory Utilization (Advanced)
    max_normal_memory_usage: PositiveFloat = Field(
        default=0.45, ge=0.35, le=0.80,
        description='The maximum memory usage under normal PostgreSQL operation over the usable memory. This holds as '
                    'the upper bound to increase the variable before reaching the limit. The supported range is [0.35, '
                    '0.80], default is 0.45. Increase this ratio meant you are expecting your server would have more '
                    'headroom for the tuning and thus for database workload. It is not recommended to set this value '
                    'too high, as there are multiple constraints that prevent further tuning to keep your server '
                    'function properly without unknown incident such as parallelism, maintenance, and other '
                    'background tasks.'
    )
    mem_pool_tuning_ratio: float = Field(
        default=0.45, ge=0.0, le=1.0, frozen=True,
        description='The memory tuning ratio in correction tuning between shared_buffers and work_buffers. Supported '
                    'value is [0, 1] and default is 0.4; Higher value meant that the tuning would prefer the '
                    ':arg`shared_buffers` over the :arg:`work_buffers`, and vice versa.'
    )
    # A too small or too large bound can lead to number overflow
    hash_mem_usage_level: int = Field(
        default=-5, ge=-50, le=50, frozen=True,
        description='The *average* hash memory usage level to determine the average work_mem in use by multiply with '
                    ':func:`generalized_mean(1, hash_mem, level=hash_mem_usage_level)`. Higher value would assume that '
                    'all PostgreSQL connections, on average, do more hash-based operations than normal operations, and '
                    'vice versa. The supported range is [-50, 50], default is -6. The recommended range is around '
                    '-10 to 6, as beyond this level results in incorrect estimation and so on.'
    )   # Maximum float allowed is [-60, 60] under 64-bit system
    mem_pool_parallel_estimate: bool = Field(
        default=True, frozen=True,
        description='Set to True (default) will switch the memory consumption estimation in parallelism by assuming '
                    'all *query* workers are consumed (based on number of available workers per connection). This '
                    'would result a lower :arg:`max_work_buffer_ratio` can get.'
    )

    # Tune logging behaviour (query size, and query runtime)
    max_query_length_in_bytes: ByteSize | PositiveInt = Field(
        default=2 * Ki, ge=64, le=64 * Mi, multiple_of=32, frozen=True,
        description='The maximum query length in bytes. The supported range is [64 B, 64 MiB], default to 2 KiB. '
                    'Default on PostgreSQL is 1 KiB. It is recommended to not set this value too high to prevent the '
                    'server write too many logs. This would be re-aligned with 32-bytes.'
    )
    max_runtime_ms_to_log_slow_query: PositiveInt = Field(
        default=2 * K10, ge=20, le=100 * K10, frozen=True,
        description='The maximum runtime of the query in milliseconds to be logged as a slow query. The supported '
                    'range is [20, 100K], default is 2000 ms (or 2 seconds). We recommend and enforce you should '
                    'know your average runtime query and its distribution and pivot the timerange to log the *slow* '
                    'query based on the database sizing and business requirements. This value is re-aligned by 20 ms '
                    'to support some old system with high time-resolution.'
    )
    max_runtime_ratio_to_explain_slow_query: PositiveFloat = Field(
        default=1.5, ge=0.1, le=10.0, frozen=True,
        description='The ratio of the query runtime to be logged as a slow query and bring to the 3rd library '
                    'auto_explain. The value must be at least 0.1, default to 1.5. We recommend and enforce this '
                    'value should be equal to higher than the variable max_runtime_ms_to_log_slow_query to prevent '
                    'excessive and repetitive logging of query planing.',
    )

    # WAL control parameters -> Change this when you initdb with custom wal_segment_size (not recommended)
    # https://postgrespro.com/list/thread-id/1898949
    # TODO: Whilst PostgreSQL allows up to 2 GiB, my recommendation is to limited below 128 MiB
    # Either I enforce constraint to prevent non optimal configuration or I let user to do it.
    # TODO: Update docs
    wal_segment_size: PositiveInt = Field(
        default=BASE_WAL_SEGMENT_SIZE, ge=BASE_WAL_SEGMENT_SIZE, le=BASE_WAL_SEGMENT_SIZE * (2 ** 7), frozen=True,
        multiple_of=BASE_WAL_SEGMENT_SIZE,
        description='The WAL segment size in PostgreSQL (in MiB). Whilst theoretically, PostgreSQL allows up to 2 GiB, '
                    'The tuning of this value is '
                    'not recommended as mentioned in [36-39] due to some hard-coded in 3rd-party tools, slow WAL '
                    'recovery on empty-large WAL files, archiving-transferring, etc; unless for high WRITE-intensive '
                    'workload with large concurrent connections. The supported range is [16 MiB (default), 128 MiB]. '
                    'The benchmark from PostgreSQL team only show improvement on synthetic benchmark with *high* '
                    'concurrent connections that write in large batch beyond a base value of 16 MiB. In a simple word, '
                    'increment only benefits when (1) you have a lot of incoming WRITE beyond 16 MiB per transaction, '
                    '(2) high WAL file rotation time (usually at old kernel and old PostgreSQL version), (3) high '
                    'archive transfer due to small files (a lot of 16 MiB files) and filesystem limitation that impact '
                    'recovery time (a lot of metadata IO reading). When change this value, adjust the max_wal_size, '
                    'archive_timeout, wal_buffers, and checkpoint_timeout to better suit your workload. '
    )
    min_wal_size_ratio: PositiveFloat = Field(
        default=0.025, ge=0.0, le=0.10, frozen=True,
        description='The ratio of the min_wal_size against the total WAL volume. The supported range is [0.0, 0.10], '
                    'default to 0.025 (2.5% of the WAL volume), meaning that 5% of the WAL volume is reserved to handle '
                    'spikes in WAL usage, allowing time for CHECKPOINT and ARCHIVE to run to cleanup WAL archive, '
                    'ensuring the non-full WAL (for SATA/NVME SSD to have write cache) and updated data files. '
                    'Internally, the :arg:`min_wal_size` has an internal lower bound of 32 WAL files or 2 GiB and an '
                    'upper bound of 1.05x of :arg:`max_wal_size` (since the :arg:`max_wal_size` is a soft limit). '
    )
    max_wal_size_ratio: PositiveFloat = Field(
        default=0.04, ge=0.0, le=0.20, frozen=True,
        description='The ratio of the max_wal_size against the total WAL volume. The supported range is [0.0, 0.20], '
                    'default to 0.04 (4% of WAL volume). But internally, the max_wal_size has an internal lower bound '
                    'of 64 WAL files or 4 GiB (prevent the default running too frequently during burst, causing the '
                    'WAL spike); and the upper bound of 64 GiB to ensure fast recovery on burst at large scale.'
    )
    wal_keep_size_ratio: PositiveFloat = (
        Field(default=0.05, ge=0.0, le=0.20, frozen=True,
              description='The ratio of the wal_keep_size against the total WAL volume. The supported range is '
                          '[0.0, 0.20], default to 0.04 (4% of WAL volume). This value is used to ensure that the '
                          'WAL archive is kept for a certain period of time before it is removed. Azure uses 400 MiB '
                          'of WAL which is 25 WAL files. Internally, the wal_keep_size has an internal lower bound '
                          'of 32 WAL files or 2 GiB to ensure a good time for retrying the WAL streaming and an upper '
                          'bound of 64 GiB. Beyond this value, whilst you cannot retry downstream connections but can '
                          'recovery from the WAL archive disk, beyond our upper bound; it is best to re-use a later '
                          'base backup and retry the WAL streaming from the beginning to avoid headache of fixing '
                          'the server (usually when dealing that large server.')
    )

    # Vacuum Tuning
    autovacuum_utilization_ratio: PositiveFloat = (
        Field(default=0.80, ge=0.30, le=0.95, frozen=True,
              description='The utilization ratio of the random IOPS of data volume used for the autovacuum process. '
                          'Note that this is based on the efficient estimated READ/WRITE IOPs and may not be reflected '
                          'in your real-world scenario. Our intention is to reduce the un-necessary time of running '
                          'autovacuum, but be able to serve a small portion of user who want to fetch the data from '
                          'database. Unless you are using the NVME as data disk (and currently have lots of IOPS), '
                          'it is not recommended to set this beyond 0.90. The supported range is (0.30, 0.95], default '
                          'is 0.80.')
    )
    vacuum_safety_level: PositiveInt = (
        Field(default=2, ge=0, le=12, frozen=True,
              description='The safety level of the vacuum process. Higher level would increase the risk during vacuum '
                          'process (by pushing its limit). Non-zero value would not protect from pure READ page during '
                          'the vacuum process, but ensuring never throttle on WRITE page(s) during VACUUM, and protect '
                          'the server under balanced distribution of READ/WRITE page from disks. Unless you lower the '
                          ':var:`autovacuum_utilization_ratio`, it is recommended to set this value low to zero to when '
                          'you do not know how your application access pattern and VACUUM behaves. The supported range '
                          'is [0, 12], default is 2. This parameter is feasible only due to the use of optimized '
                          'autovacuum configuration and visibility map, and is recommended a zero value if your '
                          'PostgreSQL is at version 12 or older.')
    )



# =============================================================================
class PG_TUNE_USR_OPTIONS(BaseModel):
    # The basic profile for the system tuning for profile-guided tuning
    workload_profile: PG_SIZING = Field(
        default=PG_SIZING.LARGE,
        description=f'The workload profile to be used for tuning. The associated value meant for the workload scale, '
                    f'amount of data in/out, ...'
    )
    pgsql_version: PositiveInt = Field(
        default=17, ge=13, le=18,
        description='The PostgreSQL version to be used for tuning. The supported range is [13, 18]. The default '
                    'is 17. The version is used to determine the tuning options and the risk level.'
    )
    # Disk options for data partitions
    data_index_spec: PG_DISK_PERF = Field(..., description='The disk specification for the data and index partition.')
    wal_spec: PG_DISK_PERF = Field(..., description='The disk specification for the WAL partition.')

    # Data Integrity, Transaction, Crash Recovery, and Replication
    max_backup_replication_tool: PG_BACKUP_TOOL = Field(
        default=PG_BACKUP_TOOL.PG_BASEBACKUP,
        description='The backup tool level to be used for the PostgreSQL server. Default is pg_basebackup. This '
                    'argument is also helps to set WAL-related configuration, including the replication tool, number '
                    'of replicas, data-transaction integrity choice.'
    )
    opt_transaction_lost: PG_PROFILE_OPTMODE = Field(
        default=PG_PROFILE_OPTMODE.NONE,
        description='The PostgreSQL mode for allow the transaction loss to tune the transaction loss recovery '
                    'mechanism. If you are working in on the mission-critical system where the atomicity and '
                    'consistency are the top priorities, then set to NONE (default) to not allow the lost transaction '
                    'loss by change the synchronous_commit. Set to SPIDEY would convert the synchronous_commit to off, '
                    'local, or remote_write (depending on the wal_level and number of replicas). Set to OPTIMUS_PRIME '
                    'would convert the full_page_writes to off. Set to PRIMORDIAL would convert the fsync to off. '
                    'Use with your own risk and caution. ',
    )
    opt_wal_buffers: PG_PROFILE_OPTMODE = Field(
        default=PG_PROFILE_OPTMODE.SPIDEY,
        description='The optimization mode for the WAL buffers to ensure the WAL buffers in the correction '
                    'tuning phase during outage lose data less than the maximum time of lossy transaction. '
                    'Set to PRIMORDIAL ensure 2x WAL buffers can be written to disk in our estimation. Similarly '
                    'with OPTIMUS_PRIME at 1.5x and SPIDEY at 1.0x. Set to NONE would not tune the WAL setting. '
                    'Only set to NONE when you feel the maximum of data integrity is not required integrity. '
                    'Otherwise, this would be enforced to SPIDEY.',
    )
    # Don't set this too high or too low as they don't guarantee stability and consistency
    max_time_transaction_loss_allow_in_millisecond: PositiveInt = Field(
        default=650, ge=100, le=10000, frozen=True,
        description='The maximum time (in milli-second) that user allow for transaction loss, to flush the page '
                    'in memory to WAL partition by WAL writer. The supported range is [100, 10000] and default '
                    'is 650 (translated to the default 200ms or 3.25x of wal_writer_delay). The lost ratio is '
                    'twice the value and three times in worst case (so we buffer to 3.25x) because the WAL writer '
                    'is designed to favor writing whole pages at a time during busy periods. The wal_writer_delay '
                    'can only be impacted when wal_level is set to replica and higher.',
    )
    max_num_stream_replicas_on_primary: int = Field(
        default=0, ge=0, le=32, frozen=True,
        description='The maximum number of streaming replicas for the PostgreSQL primary server. The supported '
                    'range is [0, 32], default is 0. If you are deployed on replica or receiving server, set '
                    'this number as low. ',
    )
    max_num_logical_replicas_on_primary: int = Field(
        default=0, ge=0, le=32, frozen=True,
        description='The maximum number of logical replicas for the PostgreSQL primary server. The supported '
                    'range is [0, 32], default is 0. If you are deployed on replica or receiving server, set '
                    'this number as low. ',
    )
    offshore_replication: bool = Field(
        default=False, frozen=True,
        description='If set it to True, you are wishing to have an geo-replicated replicas in the offshore country '
                    'or continent. Enable it would increase the wal_sender_timeout to 2 minutes or more',
    )

    # These are for the database tuning options
    workload_type: PG_WORKLOAD = Field(
        default=PG_WORKLOAD.HTAP,
        description='The PostgreSQL workload type. This would affect the tuning options and the risk level, '
                    'and many other options. Default is HTAP (Hybrid Transactional/Analytical Processing).'
    )
    opt_mem_pool: PG_PROFILE_OPTMODE = Field(
        default=PG_PROFILE_OPTMODE.OPTIMUS_PRIME,
        description='If not NONE, it would proceed the extra tuning to increase the memory buffer usage to reach to '
                    'your expectation (shared_buffers, work_mem, temp_buffer). Set to SPIDEY use the worst case of '
                    'memory usage by assuming all connections are under high load. Set to OPTIMUS_PRIME (default) '
                    'take the average between normal (active connections) and worst case as the stopping condition. '
                    'Set to PRIMORDIAL take the normal case as the stopping condition.'
    )
    tuning_kwargs: PG_TUNE_USR_KWARGS = Field(
        default=PG_TUNE_USR_KWARGS(),
        description='The PostgreSQL tuning keywords/options for the user to customize or perform advanced '
                    'tuning control; which is not usually available in the general tuning phase (except some '
                    'specific tuning options). '
    )
    # These are for the estimation of anti-wraparound vacuum tuning
    database_size_in_gib: int = Field(
        default=0, ge=0, le=32 * Ki,
        description='The largest database size (in GiB), including the data files and index files. This value is used '
                    'to estimate the maximum database size for anti-wraparound vacuum. If this field is zero, the '
                    'assumption is about 60 % usage of the data volume. The supported range is [0, 32768], default is '
                    '0 (GiB); but its maximum threshold silently capped at 90% of the data volume'
    )
    num_write_transaction_per_hour_on_workload: PositiveInt = Field(
        default=int(50 * K10), ge=K10, le=20 * M10, frozen=True,
        description='The peak number of workload WRITE transaction per hour (including sub-transactions, accounting '
                    'all attempts to make data changes (not SELECT) regardless of COMMIT and ROLLBACK). Note that '
                    'this number requires you to have good estimation on how much your server can be handled during '
                    'its busy workload and idle workload. It is best to collect your real-world data pattern before '
                    'using this value.'
    )   # https://www.postgresql.org/docs/13/functions-info.html -> pg_current_xact_id_if_assigned

    # ========================================================================
    # This is used for analyzing the memory available.
    operating_system: Literal['linux', 'windows', 'macos', 'containerd', 'PaaS'] = Field(
        default='linux', frozen=True,
        description='The operating system that the PostgreSQL server is running on. Default is Linux.'
    )

    vcpu: PositiveInt = Field(
        default=4, ge=1, frozen=True,
        description='The number of vCPU (logical CPU) that the PostgreSQL server is running on. Default is 4 vCPUs.'
    )
    total_ram: ByteSize | PositiveInt = Field(
        default=16 * Gi, ge=2 * Gi, multiple_of=256 * Mi, frozen=True,
        description='The amount of RAM capacity that the PostgreSQL server is running on (measured by bytes). Default '
                    'is 16 GiB, but minimum amount is 2 GiB. PostgreSQL would performs better when your server has '
                    'more RAM available. Note that the amount of RAM on the server must be larger than the in-place '
                    'kernel and monitoring memory usage. The value must be a multiple of 256 MiB.'
    )
    base_kernel_memory_usage: ByteSize | int = Field(
        default=-1, ge=-1, le=8 * Gi, frozen=False, allow_inf_nan=False,
        description='The PostgreSQL base kernel memory during when idle. This value is used to estimate the impact '
                    'during memory-related tuning configuration and server as a safeguard against memory overflow. '
                    'Default value is -1 to meant that this application would assume the kernel memory is taken 768 '
                    'MiB (3/4 of 1 GiB) during idle and 0 MiB if the system is not user-managed. Maximum allowed value '
                    'is 8 GiB and the input must be a multiple of 2 MiB. The 768 MiB is taken from Ubuntu 24.10 during '
                    'idle.'
    )
    base_monitoring_memory_usage: ByteSize | int = Field(
        default=-1, ge=-1, le=4 * Gi, frozen=False, allow_inf_nan=False,
        description='The PostgreSQL base monitoring memory when idle. This value is used to estimate the impact during '
                    'memory-related tuning configuration and server as a safeguard against memory overflow. Default '
                    'value is -1 meant that this application would assume the monitoring memory is taken 256 MiB '
                    'if user-managed OS, and 64 MiB to 0 MiB depending on the self-hosted container or 3rd-party DB '
                    'server. Note that this value is not limited to the monitoring only, but also antivirus, ...',
    )

    # ========================================================================
    # We may not have this at end-user on the website
    # Questions of System Management and Operation to be done
    enable_sysctl_general_tuning: bool = Field(
        default=False, frozen=False,
        description='Set to True would enable general tuning on the system kernel parameters (sysctl). If you '
                    'host your database on a managed service or container, this value is recommended to be '
                    'False. Default to False.'
    )
    enable_sysctl_correction_tuning: bool = Field(
        default=False, frozen=False,
        description='Set to True would enable correction tuning on the system kernel parameters (sysctl). If you '
                    'host your database on a managed service or container, this value is recommended to be '
                    'False. Default to False. Only valid when :attr:`enable_sysctl_general_tuning` is True.'
    )
    enable_database_general_tuning: bool = Field(
        default=True, frozen=False,
        description='Set to True would enable general tuning on the PostgreSQL database parameters. Default to True.'
    )
    enable_database_correction_tuning: bool = Field(
        default=True, frozen=False,
        description='Set to True would enable correction tuning on the PostgreSQL database parameters. Default to '
                    'True. Only valid when :attr:`enable_database_general_tuning` is True.'
    )
    align_index: Literal[0, 1] = Field(
        default=0, ge=0, le=1,
        description='This is the index used to pick the value during number alignment. Default is 0 meant a lower '
                    'value is preferred. Set to 1 would prefer a higher value. '
    )

    # ========================================================================
    # Revert some invalid options as described in :attr:`is_os_user_managed`
    def model_post_init(self, __context: Any) -> None:
        if self.operating_system != 'linux':
            self.enable_sysctl_general_tuning = False   # Not supported for other OS

        if not self.enable_sysctl_general_tuning:
            self.enable_sysctl_correction_tuning = False
        if not self.enable_database_general_tuning:
            self.enable_database_correction_tuning = False

        # Set back memory usage in non user-managed system
        if self.base_monitoring_memory_usage == -1:
            self.base_monitoring_memory_usage = ByteSize(256 * Mi)
            if self.operating_system == 'containerd':
                self.base_monitoring_memory_usage = ByteSize(64 * Mi)
            elif self.operating_system == 'PaaS':
                self.base_monitoring_memory_usage = ByteSize(0 * Mi)
            _logger.debug(f"Set the monitoring memory usage to "
                          f"{self.base_monitoring_memory_usage.human_readable(separator=' ')}")

        if self.base_kernel_memory_usage == -1:
            self.base_kernel_memory_usage = ByteSize(768 * Mi)
            if self.operating_system == 'containerd':
                self.base_kernel_memory_usage = ByteSize(64 * Mi)
            elif self.operating_system == 'windows':
                self.base_kernel_memory_usage = ByteSize(2 * Gi)
            elif self.operating_system == 'PaaS':
                self.base_kernel_memory_usage = ByteSize(0 * Mi)
            _logger.debug(f"Set the kernel memory usage to "
                          f"{self.base_kernel_memory_usage.human_readable(separator=' ')}")

        # Check minimal RAM usage
        if self.usable_ram < 4 * Gi:
            _sign = '+' if self.usable_ram >= 0 else '-'
            _msg: str = (f'The usable RAM {_sign}{bytesize_to_hr(self.usable_ram)} is less than the PostgreSQL '
                         'minimum 4 GiB, and your workload is not self tested or local testing. The tuning may not be '
                         'accurate. It is recommended to increase the total RAM of your server, or switch to a more '
                         'lightweight monitoring system, kernel usage, or even the operating system.')
            _logger.warning(_msg)

        # Check database size to be smaller than 90% of data volume
        _database_limit = ceil((self.data_index_spec.disk_usable_size / Gi) * 0.90)
        if self.database_size_in_gib == 0:
            _logger.warning('The database size is set to 0 GiB. The database size is estimated to be 60% of the data '
                            'volume, which is a common but highest amount of data I observed in general. Even for '
                            'TiB-scaled data, in usual they add in 1 TiB storage every review interval (1-3 years) '
                            'depending on use-case and growth (not accounting media files such as images or videos).')
            self.database_size_in_gib = ceil((self.data_index_spec.disk_usable_size / Gi) * 0.60)
        if self.database_size_in_gib > _database_limit:
            _logger.warning(f'The database size {self.database_size_in_gib} GiB is larger than the data volume. The '
                            f'database size is silently capped at 90% of the data volume.')
            self.database_size_in_gib = _database_limit

        return None

    @cached_property
    def hardware_scope(self) -> dict[str, PG_SIZING]:
        """ Translate the hardware scope into the dictionary format """
        # return {'cpu': self.cpu_profile, 'mem': self.mem_profile, 'net': self.net_profile, 'disk': self.disk_profile,
        #         'overall': self.workload_profile}
        return {k: self.workload_profile for k in ('cpu', 'mem', 'net', 'disk', 'overall')}

    def translate_hardware_scope(self, term: str | None) -> PG_SIZING:
        if term:
            term = term.lower().strip()
            try:
                return self.hardware_scope[term]
            except KeyError as e:
                # This should never be happened.
                _logger.debug(f'The hardware scope {term} is not in the supported list '
                              f'-> Fall back to overall profile.')

        return self.workload_profile

    # ========================================================================
    # Some VM Snapshot Function
    @cached_property
    def usable_ram(self) -> ByteSize | int:
        mem_available: ByteSize | int = self.total_ram
        mem_available -= self.base_kernel_memory_usage
        mem_available -= self.base_monitoring_memory_usage
        assert mem_available >= 0, 'The available memory is less than 0. Please check the memory usage.'
        return mem_available
