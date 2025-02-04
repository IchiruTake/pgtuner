import logging

from pydantic import BaseModel, Field
from pydantic.types import PositiveFloat, PositiveInt, ByteSize

from src.static.vars import APP_NAME_UPPER, K10, BASE_WAL_SEGMENT_SIZE, Mi, Ki, Gi, Ti, M10

__all__ = ["PG_TUNE_USR_KWARGS", ]
_logger = logging.getLogger(APP_NAME_UPPER)


# =============================================================================
# Ask user which tuning options they choose for
class PG_TUNE_USR_KWARGS(BaseModel):
    """
    This class stored some tuning user|app-defined keywords that could be used to adjust the tuning phase.
    Parameters:
    """
    user_max_connections: int = (
        Field(default=0, ge=0, le=1000,
              description='The maximum number of client connections allowed (override by user). The supported range is '
                          '[0, 1000], default is 0 (ignored). As our check, the higher number of connections could '
                          'risk the benefit of the tuning over PostgreSQL shared memory and allocated memory for '
                          'query and management.')
    )
    superuser_reserved_connections_scale_ratio: PositiveFloat = (
        Field(default=1.5, ge=1, le=3,
              description='The de-scale ratio for the reserved superuser connections over the normal reserved '
                          'connection. The supported range is [1, 3], default is 1.5. Higher value means the de-scale '
                          'is stronger.')
    )
    single_memory_connection_overhead: ByteSize = (
        Field(default=5 * Mi, ge=2 * Mi, le=12 * Mi,
              description='The memory overhead for a single connection at idle state. The supported range is [2 MiB, '
                          '12 MiB], default is 5 MiB in total. This value is used to estimate the memory usage for '
                          "each connection. We do not recommend to set this value too high as it could make the "
                          'estimation to be incorrect (recommend to be between 4 - 8 MiB).')
    )
    memory_connection_to_dedicated_os_ratio: float = (
        Field(default=0.3, ge=0.0, le=1.0,
              description='The ratio of the memory connection to the dedicated OS memory. The supported range is [0, 1], '
                          'default is 0.3. This value is used to estimate the memory usage for each connection is '
                          'placed under the OS memory page rather than the shared_buffers of the PostgreSQL memory.')
    )

    effective_cache_size_available_ratio: PositiveFloat = (
        Field(default=0.99, ge=0.93, le=1.0,
              description='The percentage of effective_cache_size over the total PostgreSQL available memory excluding '
                          'the shared_buffers and others. The supported range is [0.93, 1.0], default is 0.99. '
                          'It is recommended to set this value to at least 0.98 or higher.')
    )
    shared_buffers_ratio: PositiveFloat = (
        Field(default=0.25, ge=0.15, lt=0.60,
              description='The ratio of shared_buffers ratio to the total non-database memory. The supported range '
                          'is [0.15, 0.60), default is 0.25. If you have or prioritize the *simple* query that perform '
                          'more READ (SELECT) than WRITE (INSERT/UPDATE/DELETE) between two WRITE interval in the '
                          '*same* table, than you can think of increasing **slowly** this value (1-2% increment change) '
                          'with consideration. However, we recommend that this value should be below 0.40 to prevent '
                          'double caching unless you are making a read-only database or a not-good synthetic benchmark.')
    )
    max_work_buffer_ratio: PositiveFloat = (
        Field(default=0.075, gt=0, le=0.50,
              description='The ratio of the maximum PostgreSQL available memory (excluding shared_buffers and others) '
                          'to be used in the session-based variable: temp_buffers and work_mem (globally managed). The '
                          'supported range is (0, 0.50], default is 0.075. The algorithm is temp_buffers + work_mem = '
                          '(pgmem_available * max_work_buffer_ratio) / active_user_connections.')
    )
    effective_connection_ratio: PositiveFloat = (
        Field(default=0.75, ge=0.25, le=1.0,
              description='The percentage of the maximum non-reserved connection used to tune temp_buffers and '
                          'work_mem. The supported range is [0.25, 1], default is 0.75. Set to 1 meant that we assume'
                          'all the normal connections use the same temp_buffers and work_mem. Reduce this ratio would '
                          'increase the temp_buffers and work_mem allowed for each connection by assuming not all '
                          'active connections are running complex queries that requires high work_mem or temp_buffers.')
    )
    temp_buffers_ratio: PositiveFloat = (
        Field(default=1 / 3, ge=0.05, le=0.95,
              description='The ratio of temp_buffers to the work_buffer pool above. The supported range is [0.05, '
                          '0.95], default is 1/3. Increase this value make the temp_buffers larger than the work_mem. '
                          'If you have query that use much temporary object (temporary table, CTE, ...) then you can '
                          'increase this value slowly (1-3% increment is recommended). If you have query involving '
                          'more WRITE and/or the WRITE query plan is complex involving HASH, JOIN, MERGE, ... then '
                          'it is better to decrease this value (1-3% decrement is recommended).')
    )
    # These are used for memory_precision_tuning
    max_normal_memory_usage: PositiveFloat = (
        Field(default=0.45, ge=0.35, le=0.85,
              description='The maximum memory usage under normal PostgreSQL operation over the usable memory. This '
                          'holds as the upper bound to increase the variable before reaching the limit. The supported '
                          'range is [0.35, 0.85], default is 0.45. Increase this ratio meant you are expecting your '
                          'server would have more headroom for the tuning and thus for database workload. It is '
                          'not recommended to set this value too high, as there are multiple constraints that prevent '
                          'further tuning to keep your server function properly without unknown incident such as '
                          'parallelism, maintenance, and other background tasks.')
    )
    mem_pool_epsilon_to_rollback: PositiveFloat = (
        Field(default=0.01, ge=0, le=0.02,
              description='A small epsilon value if the memory tuning does not exceeded max_normal_memory_usage + '
                          'epsilon to perform a rollback. We recommend this value to be small. The supported '
                          'range is [0, 0.02], and default to 1e-2 (1.0%). If the result exceeded, we trigger the '
                          'rollback to get the previous iteration.')
    )
    mem_pool_tuning_increment: PositiveFloat = (
        Field(default=1 / 280, ge=1 / 2000, le=0.01,
              description='The single increment for the memory tuning in correction tuning of shared_buffer_ratio '
                          'and max_work_buffer_ratio, which impacted to shared_buffers, temp_buffers, work_mem, '
                          'wal_buffers, and effective_cache_size. A lower value means the tuning is more precise '
                          'but slower. Supported value is [1/2000, 1/100] and default is 1/280. Higher value meant '
                          'there may have a small room for rollback')
    )
    mem_pool_tuning_ratio: float = (
        Field(default=0.5, ge=0, le=1,
              description='The ratio of the memory tuning in correction tuning of shared_buffer_ratio and '
                          'max_work_buffer_ratio. Supported value is [0, 1] and default is 0.5. Higher value meant '
                          'the tuning would prefer the shared_buffers over the max_work_buffer_ratio. Lower value '
                          'meant the tuning would prefer the max_work_buffer_ratio over the shared_buffers.')
    )
    mem_pool_parallel_estimate: bool = (
        Field(default=False,
              description='The flag to switch to the memory estimation in parallelism. The default is False. ')
    )

    # Tune logging behaviour (query size, and query runtime)
    max_query_length_in_bytes: ByteSize = (
        Field(default=2 * Ki, ge=64, le=64 * Mi, multiple_of=32,
              description='The maximum query length in bytes. The supported range is 64 bytes to 64 MiB, default to '
                          '2 KiB. Default on PostgreSQL is 1 KiB. It is recommended to not set this value too high '
                          'to prevent the server write too many logs. This would be re-aligned with 32-bytes.')
    )
    max_runtime_ms_to_log_slow_query: PositiveInt = (
        Field(default=2 * K10, ge=20, le=100 * K10,
              description='The maximum runtime of the query in milliseconds to be logged as a slow query. The '
                          'supported range is [10, 100K], default is 2000 ms (or 2 seconds). We recommend and enforce '
                          'you should know your average runtime query and its distribution and pivot the timerange '
                          'to log the *slow* query based on the database sizing and business requirements. This '
                          'value is re-aligned by 20 ms to support some old system with high time-resolution.')
    )
    max_runtime_ratio_to_explain_slow_query: PositiveFloat = (
        Field(default=1.5, ge=0.1, le=10.0,
              description='The ratio of the query runtime to be logged as a slow query and bring to the 3rd library '
                          'auto_explain. The value must be at least 0.1, default to 1.5. We recommend and enforce '
                          'this value should be equal to higher than the variable max_runtime_ms_to_log_slow_query to '
                          'prevent excessive logging of query planing.',
              )
    )

    # WAL control parameters -> Change this when you initdb with custom wal_segment_size
    # WAL tuning
    wal_segment_size: PositiveInt = (
        Field(default=BASE_WAL_SEGMENT_SIZE, ge=BASE_WAL_SEGMENT_SIZE, le=128 * BASE_WAL_SEGMENT_SIZE, frozen=True,
              multiple_of=BASE_WAL_SEGMENT_SIZE,
              description='The WAL segment size in PostgreSQL (in MiB). The supported range is [16, 2048] in MiB. '
                          'Whilst the tuning of this value is not recommended as mentioned in [36-39] due to some '
                          'hard-coded in 3rd-party tools, and benefits of WAL recovering, archiving, and transferring; '
                          'longer WAL initialization during burst workload. Unless you run initdb with custom '
                          'wal_segment_size (64 MiB or larger); I still leave it here for you to adjust. For the best '
                          'practice, whilst 16 MiB of single WAL file is good for most cases; a scenario where you '
                          'need higher WAL size is when dealing with OLTP workload with large amount of data write '
                          'that would rotate the WAL too frequently. Also, the benchmarking from PostgreSQL team '
                          'does show improvement but at when the number of connections are large (> 64) with larger '
                          'than 64 vCPU. Beyond that, the improvement are marginal and you could have same benefit '
                          'when tuning other variables. Just to remember to adjust the max_wal_size, archive_timeout, '
                          'and checkpoint_timeout to better suit your workload.')
    )
    min_wal_ratio_scale: PositiveFloat = (
        Field(default=0.5, gt=0.0, le=3.0,
              description='The WAL ratio scaler for tune the min_wal_size configuration. The min_wal_size is computed '
                          'by take this argument and multiply with remaining storage. Setting this value beyond 1.0 '
                          'meant that the min_wal_size would be larger than the max_wal_size. The maximum value of '
                          'min_wal_size is depending on the smallest ratio of max_wal_size (defined in the source). '
                          'The supported range is [0.01, 3.0], default is 0.5. ')
    )
    max_wal_size_ratio: PositiveFloat = (
        Field(default=0.90, gt=0.0, lt=1.0,
              description='The ratio of the max_wal_size against the total WAL volume. The supported range is between 0.0 '
                          'and 1.0 (exclusive on two end), default is 0.90.')
    )
    max_wal_size_remain_upper_size: ByteSize = (
        Field(default=256 * Gi, ge=1 * Gi, le=2 * Ti, multiple_of=1 * Gi,
              description='The upper bound of free space from max_wal_size value to the WAL volume capacity. It is '
                          'set to ensure that you can maximize the WAL partition better and prevent frequent changes '
                          'on ratio. If the remaining space exceeded this capacity, the max_wal_size is adjusted to '
                          'the total storage minus this value. Whilst this value could be different across workloads, '
                          'it is OK to set this value a little bit high when you work on SSD where its performance '
                          'corresponding to the remaining space (especially on the NVME QLC SSD, TLC and MLC usually '
                          'have less impact). The minimum value is 1 GiB and the default is 256 GiB, and must be a '
                          'multiple of 256 MiB. For example if the ratio is 0.9 and upper size is 256 GiB, then the '
                          'disk size must be larger 256 Gi / (1 - 0.9) ~ 2.5 TiB to have max_wal_size is 256 GiB less '
                          'than the disk size.')
    )

    # Background Writer Tuning
    bgwriter_utilization_ratio: PositiveFloat = (
        Field(default=0.15, gt=0, le=0.4,
              description='The utilization ratio of the random IOPS of data volume used for the background writer '
                          'process. The supported range is (0, 0.4], default is 0.15 or 15%. This would determine the '
                          'efficient estimated WRITE IOPs, but minimum 4 MiB/s of 8K-IOPS. Higher value would make '
                          'the background writer overflow the data disk, which could be in use for other purposes. ')
    )

    # Vacuum Tuning
    autovacuum_utilization_ratio: PositiveFloat = (
        Field(default=0.80, gt=0.50, le=0.95,
              description='The utilization ratio of the random IOPS of data volume used for the autovacuum process. '
                          'Note that this is based on the efficient estimated READ/WRITE IOPs and may not be reflected '
                          'in your real-world scenario. Our intention is to reduce the un-necessary time of running '
                          'autovacuum, but be able to serve a small portion of user who want to fetch the data from '
                          'database. Unless you are using the NVME as data disk (and currently have lots of IOPS), '
                          'it is not recommended to set this beyond 0.90. The supported range is (0.50, 0.95], default '
                          'is 0.80.')
    )
    # Transaction Rate
    num_write_transaction_per_hour_on_workload: PositiveInt = (
        Field(default=int(5 * M10), ge=K10, le=50 * M10,
              description='The peak number of workload write transaction per hour. The supported range is [1K, 50M], '
                          'default is 5M (translated into 1.4K transactions per second). Note that this number requires '
                          'you to have good estimation on how much your server can be handled during its busy workload. '
                          'This parameter is used to determine the which page is frozen. ')
    )


    # =============================================================================
    # Currently unused keywords
    # max_num_databases: PositiveInt = (
    #     Field(default=5, ge=1, le=50,
    #           description="The maximum number of *estimated* databases stored in your PostgreSQL server. If you have "
    #                       "the database dedicated for each application or microservices, it is best to distribute them "
    #                       "equally to reduce failure risk and better performance management. Similarly, if you have "
    #                       "more than 10-20 databases, then it is best to break them out into multiple PostgreSQL "
    #                       "instances. The supported range is [1, 50], default is 5; and this value is used for "
    #                       "parallelism estimation.")
    # )
    # total_database_size_in_gib: PositiveInt = (
    #     Field(default=20, ge=1, le=128 * K10,
    #           description="The total size of all databases in the PostgreSQL server (in GiB). This value is used to "
    #                       "estimate some. The supported range is [1, 128000], default is 20 (GB).")
    # )
