from pydantic import BaseModel, Field
from pydantic.types import PositiveFloat, PositiveInt
from src.static.vars import APP_NAME_UPPER, K10, Mi, Gi, WAL_SEGMENT_SIZE
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
import logging

__all__ = ["PG_TUNE_USR_KWARGS", ]
_PG_OPT_KEYS = PG_PROFILE_OPTMODE.__members__.keys()
_logger = logging.getLogger(APP_NAME_UPPER)


# =============================================================================
# Ask user which tuning options they choose for
class PG_TUNE_USR_KWARGS(BaseModel):
    """
    This class stored some tuning user|app-defined keywords that could be used to adjust the tuning phase.
    Parameters:
    """
    user_max_connections: PositiveInt = (
        Field(default=0, ge=0, le=1000,
              description="The maximum number of client connections allowed (override by user). The supported range is "
                          "[0, 1000], default is 0 (ignored). As our check, the higher number of connections could "
                          "risk the benefit of the tuning over PostgreSQL shared memory and allocated memory for "
                          "query and management. See the gtune_common.py for more information.")
    )
    shared_buffers_ratio: PositiveFloat = (
        Field(default=0.25, ge=0.15, lt=0.40,
              description="The ratio of shared_buffers ratio to the total non-database memory. The supported range "
                          "is [0.15, 0.40), default is 0.25. If you have or prioritize the *simple* query that perform "
                          "more READ (SELECT) than WRITE (INSERT/UPDATE/DELETE) between two WRITE interval in the "
                          "*same* table, than you can think of increasing **slowly** this value (1-2% increment change) "
                          "with consideration. See the gtune_common.py for more information. ")
    )
    effective_cache_size_available_ratio: PositiveFloat = (
        Field(default=0.95, ge=0.80, lt=1.0,
              description="The percentage of effective_cache_size memory over the total available memory excluding "
                          "the shared_buffers and kernel memory. The supported range is [0.80, 1.0), default is 0.95. "
                          "See the gtune_common.py for more information.")
    )
    superuser_reserved_connections_scale_ratio: PositiveFloat = (
        Field(default=1.5, ge=1, le=3,
              description="The de-scale ratio for the reserved superuser connections over the normal reserved "
                          "connection. The supported range is [1, 3], default is 1.5. Higher value means the de-scale "
                          "is stronger. See the gtune_common.py for more information.")
    )
    max_work_buffer_ratio: PositiveFloat = (
        Field(default=0.25, gt=0, le=0.5,
              description="The ratio of the maximum available memory (excluding kernel memory and shared_buffers) to "
                          "be used in the session-based variable: temp_buffers and work_mem (globally managed). The "
                          "supported range is (0, 0.5], default is 0.25. See the gtune_common.py for more information."
                          "The algorithm is temp_buffers + work_mem = (pgmem_available * max_work_buffer_ratio) / "
                          "(non_reserved_connection * conn_heuristic_percentage).")
    )
    conn_heuristic_percentage: PositiveFloat = (
        Field(default=0.8, ge=0.25, le=1,
              description="The percentage of the maximum non-reserved connection used to tune temp_buffers and "
                          "work_mem. The supported range is [0.25, 1], default is 0.8. Set to 1 meant that we assume"
                          "all the normal connections use the same temp_buffer and work_mem. See the gtune_common.py "
                          "for more information.")
    )
    temp_buffers_ratio: PositiveFloat = (
        Field(default=2 / 3, ge=0.35, le=0.95,
              description="The ratio of temp_buffers to the work_mem. The supported range is [0.35, 0.95], default is "
                          "2/3. Increase this value make the temp_buffers larger than the work_mem. If you have query "
                          "that use much temporary object (temporary table, CTE, ...) then you can increase this value"
                          "slowly (1-3% increment is recommended). If you have query involving more WRITE and/or the "
                          "WRITE query plan is complex involving HASH, JOIN, MERGE, ... then it is better to decrease "
                          "this value (1-3% decrement is recommended). See the gtune_common.py for more information.")
    )
    raid_io_efficiency: PositiveFloat = (
        Field(default=0.80, ge=0, le=1,
              description="The efficiency of the RAID IO operation when translating to effective_io_concurrency. Set to "
                          "1.0 means 100 % I/O could be translated directly to PostgreSQL. The naive RAID scale factor "
                          "would be converted as raid_scale_factor ** raid_io_efficiency. The supported range is "
                          "[0, 1.0], deafult to 0.80.")
    )
    max_normal_memory_usage: PositiveFloat = (
        Field(default=0.75, ge=0.50, le=0.95,
              description="The maximum memory usage for the normal PostgreSQL operation over the total memory. This "
                          "holds as the upper bound to increase the variable before reaching the limit. The supported "
                          "range is [0.50, 0.95], default is 0.75. Increase this ratio meant you are expecting your "
                          "server would have more headroom for the tuning and thus for database workload. It is "
                          "not recommended to set this value too high, as there are multiple constraint that prevent"
                          "further tuning to keep your server function properly without unknown downtime. See the "
                          "gtune_common.py for more information.")
    )
    memory_precision_tuning_ratio: PositiveFloat = (
        Field(default=1 / 160, ge=1 / 2000, le=0.01,
              description="The precision for the memory tuning in correction tuning of shared_buffer_ratio and "
                          "max_work_buffer_ratio, which impacted to shared_buffers, temp_buffers, work_mem, "
                          "wal_buffers, and effective_cache_size. A lower value means the tuning is more precise "
                          "but slower. Supported value is [1/2000, 1/100] and default is 1/160. Higher value meant"
                          "there may have a small room for rollback")
    )


    # =============================================================================
    # Currently unused keywords
    max_num_databases: PositiveInt = (
        Field(default=5, ge=1, le=100,
              description="The maximum number of *estimated* databases stored in your PostgreSQL server. If you have "
                          "the database dedicated for each application or microservices, it is best to distribute them "
                          "equally to reduce failure risk and better performance management. Similarly, if you "
                          "have more than 10-20 databases, then it is best to break them out into multiple PostgreSQL "
                          "instances. The supported range is [1, 100], default is 5; and this value is used for "
                          "parallelism estimation.")
    )
    total_database_size_in_gib: PositiveInt = (
        Field(default=20, ge=1, le=128 * K10,
                description="The total size of all databases in the PostgreSQL server (in GiB). This value is used to "
                            "estimate some. The supported range is [1, 128000], default is 20 (GB).")
    )
    wal_segment_size: PositiveInt = (
        Field(default=WAL_SEGMENT_SIZE, ge=WAL_SEGMENT_SIZE, le=128 * WAL_SEGMENT_SIZE, frozen=True,
              multiple_of=WAL_SEGMENT_SIZE,
              description="The size of the WAL segment in PostgreSQL (in MiB). The supported range is [16, 2048] in "
                          "MiB (default to 16 MiB). Whilst the tuning of this value is not recommended as mentioned "
                          "in [36-39] due to some hard-coded in PostgreSQL sourcecode, 3rd-party tools, and benefits "
                          "of WAL recovering, archiving, and transferring; longer WAL initialization during burst "
                          "workload; I still leave it here for you to adjust. The reason why I am not recommended a"
                          "default change is that 16 MiB is equivalent of 2048 pages; thus not many applications write "
                          "this much in a second (unless you stack every database of every application in the same "
                          "server, which is a maintenance bomb). Also, instead of benchmarking only wal_segment_size, "
                          "you might consider tuning checkpoint_timeout and max_wal_size to better suit your workload.")
    )