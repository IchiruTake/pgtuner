import logging
from pydantic import BaseModel, Field
from pydantic.types import PositiveFloat, PositiveInt, ByteSize
from src.static.vars import APP_NAME_UPPER, K10, BASE_WAL_SEGMENT_SIZE, Mi, Ki, Gi, Ti, M10

__all__ = ['PG_TUNE_USR_KWARGS', ]
_logger = logging.getLogger(APP_NAME_UPPER)


# =============================================================================
# Ask user which tuning options they choose for
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
    superuser_reserved_connections_scale_ratio: PositiveFloat = Field(
        default=1.5, ge=1, le=3, frozen=True,
        description='The de-scale ratio for the reserved superuser connections over the normal reserved connection. '
                    'The supported range is [1, 3], default is 1.5. Higher value means less superuser reserved '
                    'connection as compared to the normal reserved connection.'
    )
    single_memory_connection_overhead: ByteSize = Field(
        default=5 * Mi, ge=2 * Mi, le=12 * Mi, frozen=True,
        description='The memory overhead for a single connection at idle state. The supported range is [2 MiB, 12 MiB], '
                    'default is 5 MiB in total. This value is used to estimate the memory usage for each connection; '
                    'and it is advised to not set it too high or change it as it could make the estimation to be '
                    'incorrect (recommend to be between 4 - 8 MiB).'
    )
    memory_connection_to_dedicated_os_ratio: float = Field(
        default=0.3, ge=0.0, le=1.0, frozen=True,
        description='The ratio of the memory connection to the dedicated OS memory rather than shared_buffers of '
                    'the PostgreSQL memory. The supported range is [0, 1], default is 0.3 or 30%. '
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
        default=0.075, gt=0, le=0.50, frozen=False,
        description='The starting ratio of the maximum PostgreSQL available memory (after excluding shared_buffers and '
                    'others) to be used in the session-based variable: temp_buffers and work_mem (globally managed). '
                    'The supported range is (0, 0.50], default is 0.075. The algorithm is temp_buffers + work_mem = '
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
        default=0.6, ge=0.0, le=1.0, frozen=True,
        description='The memory tuning ratio in correction tuning between shared_buffers and work_buffers. Supported '
                    'value is [0, 1] and default is 0.6; Higher value meant that the tuning would prefer the '
                    ':arg`shared_buffers` over the :arg:`work_buffers`, and vice versa.'
    )
    # A too small or too large bound can lead to number overflow
    hash_mem_usage_level: int = Field(
        default=-6, ge=-50, le=50, frozen=True,
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
    max_query_length_in_bytes: ByteSize = Field(
        default=2 * Ki, ge=64, le=64 * Mi, multiple_of=32, frozen=True,
        description='The maximum query length in bytes. The supported range is [64 B, 64 MiB], default to 2 KiB. '
                    'Default on PostgreSQL is 1 KiB. It is recommended to not set this value too high to prevent the '
                    'server write too many logs. This would be re-aligned with 32-bytes.'
    )
    max_runtime_ms_to_log_slow_query: PositiveInt = Field(
        default=2 * K10, ge=20, le=100 * K10, frozen=True,
        description='The maximum runtime of the query in milliseconds to be logged as a slow query. The supported '
                    'range is [10, 100K], default is 2000 ms (or 2 seconds). We recommend and enforce you should '
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
    wal_segment_size: PositiveInt = Field(
        default=BASE_WAL_SEGMENT_SIZE, ge=BASE_WAL_SEGMENT_SIZE, le=8 * BASE_WAL_SEGMENT_SIZE, frozen=True,
        multiple_of=BASE_WAL_SEGMENT_SIZE,
        description='The WAL segment size in PostgreSQL (in MiB). Whilst theoretically, PostgreSQL allows up to 2 GiB, '
                    'our recommendation is to limit below 128 MiB (2^3 more of 16 MiB). The tuning of this value is '
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
        default=0.05, ge=0.0, le=0.15, frozen=True,
        description='The ratio of the min_wal_size against the total WAL volume. The supported range is [0.0, 0.15], '
                    'default to 0.03 (3% of the WAL volume), meaning that 3% of the WAL volume is reserved to handle '
                    'spikes in WAL usage, allowing time for CHECKPOINT and ARCHIVE to run to cleanup WAL archive, '
                    'ensuring the non-full WAL (for SATA/NVME SSD to have write cache) and updated data files. '
                    'Internally, the :arg:`min_wal_size` has an internal lower bound of 32 WAL files or 2 GiB and an '
                    'upper bound of 1.05x of :arg:`min_wal_size` (since the :arg:`min_wal_size` is a soft limit). '
    )
    max_wal_size_ratio: PositiveFloat = Field(
        default=0.05, ge=0.0, le=0.30, frozen=True,
        description='The ratio of the max_wal_size against the total WAL volume. The supported range is [0.0, 0.30], '
                    'default to 0.05 (5% of WAL volume). But internally, the max_wal_size has an internal lower bound '
                    'of 64 WAL files or 4 GiB (prevent the default running too frequently during burst, causing the '
                    'WAL spike); and the upper bound of 64 GiB to ensure fast recovery on burst at large scale.'
    )
    wal_keep_size_ratio: PositiveFloat = (
        Field(default=0.05, ge=0.0, le=0.30, frozen=True,
              description='The ratio of the wal_keep_size against the total WAL volume. The supported range is '
                          '[0.0, 0.30], default to 0.05 (5% of WAL volume). This value is used to ensure that the '
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
