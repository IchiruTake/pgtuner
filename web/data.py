import logging
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ByteSize
from pydantic.types import PositiveInt, PositiveFloat

from src.static.vars import K10, Ki, Gi, Mi, APP_NAME_UPPER, BASE_WAL_SEGMENT_SIZE, M10
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.keywords import PG_TUNE_USR_KWARGS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.sizing import PG_SIZING, PG_DISK_SIZING
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.pg_dataclass import PG_TUNE_REQUEST


__all__ = ['PG_WEB_TUNE_USR_OPTIONS', 'PG_WEB_TUNE_REQUEST']
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
class _PG_WEB_DISK_PERF_INT(BaseModel):
    random_iops: PositiveInt = Field(default=PG_DISK_SIZING.SANv1.iops())
    throughput: PositiveInt = Field(default=PG_DISK_SIZING.SANv1.throughput())
    disk_usable_size_in_gib: ByteSize = Field(default=20, ge=5)

    def to_backend(self) -> PG_DISK_PERF:
        return PG_DISK_PERF(random_iops_spec=self.random_iops, throughput_spec=self.throughput,
                            random_iops_scale_factor=0.9, throughput_scale_factor=0.9, num_disks=1,
                            per_scale_in_raid=0.75, disk_usable_size=self.disk_usable_size_in_gib * Gi)


class PG_WEB_TUNE_USR_KWARGS(BaseModel):
    """
    This class stored some tuning user|app-defined keywords that could be used to adjust the tuning phase.
    Parameters:
    """
    # Connection Parameters
    user_max_connections: int = Field(default=0, ge=0, le=1000)
    superuser_reserved_connections_scale_ratio: PositiveFloat = Field(default=1.5, ge=1, le=3)
    single_memory_connection_overhead_in_kib: ByteSize = Field(default=5 * Ki, ge=2 * Ki, le=12 * Ki)
    memory_connection_to_dedicated_os_ratio: float = Field(default=0.3, ge=0.0, le=1.0)

    # Memory Parameters
    effective_cache_size_available_ratio: PositiveFloat = Field(default=0.985, ge=0.95, le=1.0)
    shared_buffers_ratio: PositiveFloat = Field(default=0.25, ge=0.15, le=0.60)
    shared_buffers_fill_ratio: PositiveFloat = Field(default=0.995, ge=0.95, le=1.0)
    max_work_buffer_ratio: PositiveFloat = Field(default=0.075, gt=0, le=0.50)
    effective_connection_ratio: PositiveFloat = Field(default=0.75, ge=0.25, le=1.0)
    temp_buffers_ratio: PositiveFloat = Field(default=0.25, ge=0.05, le=0.95)

    # These are used for memory_precision_tuning
    max_normal_memory_usage: PositiveFloat = Field(default=0.45, ge=0.35, le=0.80)
    mem_pool_tuning_ratio: float = Field(default=0.6, ge=0, le=1)
    mem_pool_parallel_estimate: bool = Field(default=True)
    hash_mem_usage_level: int = Field(default=-6, ge=-60, le=60)

    # WAL control parameters -> Change this when you initdb with custom wal_segment_size
    wal_segment_size_scale: int = Field(default=0, ge=0, le=3)  # Instead of 8
    min_wal_size_ratio: PositiveFloat = Field(default=0.03, ge=0.0, le=0.15)
    max_wal_size_ratio: PositiveFloat = Field(default=0.05, ge=0.0, le=0.30)
    wal_keep_size_ratio: PositiveFloat = Field(default=0.05, ge=0.0, le=0.30)

    # Tune logging behaviour (query size, and query runtime)
    max_query_length_in_bytes: ByteSize = Field(default=2 * Ki, ge=64, le=64 * Mi)
    max_runtime_ms_to_log_slow_query: PositiveInt = Field(default=2 * K10, ge=20, le=100 * K10)
    max_runtime_ratio_to_explain_slow_query: PositiveFloat = Field(default=1.5, ge=0.1, le=10.0)

    # Vacuum Tuning
    autovacuum_utilization_ratio: PositiveFloat = Field(default=0.80, gt=0.50, le=0.95)
    vacuum_safety_level: PositiveInt = Field(default=2, ge=0, le=12)

    def to_backend(self) -> PG_TUNE_USR_KWARGS:
        return PG_TUNE_USR_KWARGS(
            # Connection Parameters
            user_max_connections=self.user_max_connections,
            superuser_reserved_connections_scale_ratio=self.superuser_reserved_connections_scale_ratio,
            single_memory_connection_overhead=self.single_memory_connection_overhead_in_kib * Ki,
            memory_connection_to_dedicated_os_ratio=self.memory_connection_to_dedicated_os_ratio,

            # Memory Parameters
            effective_cache_size_available_ratio=self.effective_cache_size_available_ratio,
            shared_buffers_ratio=self.shared_buffers_ratio,
            max_work_buffer_ratio=self.max_work_buffer_ratio,
            effective_connection_ratio=self.effective_connection_ratio,
            temp_buffers_ratio=self.temp_buffers_ratio,

            # Memory Pool Resizing
            max_normal_memory_usage=self.max_normal_memory_usage,
            mem_pool_tuning_ratio=self.mem_pool_tuning_ratio,
            mem_pool_parallel_estimate=self.mem_pool_parallel_estimate,
            hash_mem_usage_level=self.hash_mem_usage_level,


            # Logging
            max_query_length_in_bytes=self.max_query_length_in_bytes,
            max_runtime_ms_to_log_slow_query=self.max_runtime_ms_to_log_slow_query,
            max_runtime_ratio_to_explain_slow_query=self.max_runtime_ratio_to_explain_slow_query,

            # WAL
            wal_segment_size=BASE_WAL_SEGMENT_SIZE * (2 ** self.wal_segment_size_scale),
            min_wal_size_ratio=self.min_wal_size_ratio,
            max_wal_size_ratio=self.max_wal_size_ratio,
            wal_keep_size_ratio=self.wal_keep_size_ratio,

            # Others
            autovacuum_utilization_ratio=self.autovacuum_utilization_ratio,
            vacuum_safety_level=self.vacuum_safety_level,
        )


class PG_WEB_TUNE_USR_OPTIONS(BaseModel):
    # Note that in here we just adhere to the Pydantic datatype and not constraint to the list of allowed values
    # Also, not all the values are used in a web application. So we decided to prune some of them.

    # The basic profile for the system tuning for profile-guided tuning
    workload_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    # cpu_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    # mem_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    # disk_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    # net_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    pgsql_version: str = Field(default='17')

    # Disk options for data partitions
    # os_db_spec: PG_DISK_PERF        # This is not used
    data_index_spec: _PG_WEB_DISK_PERF_INT = Field(default=_PG_WEB_DISK_PERF_INT())
    wal_spec: _PG_WEB_DISK_PERF_INT = Field(default=_PG_WEB_DISK_PERF_INT())
    # db_log_spec: PG_DISK_PERF       # This is not used

    # Data Integrity, Transaction, Crash Recovery, and Replication
    max_backup_replication_tool: str = Field(default='pg_basebackup')
    opt_transaction_lost: PG_PROFILE_OPTMODE = Field(default=PG_PROFILE_OPTMODE.NONE)
    opt_wal_buffers: PG_PROFILE_OPTMODE = Field(default=PG_PROFILE_OPTMODE.SPIDEY)
    max_time_transaction_loss_allow_in_millisecond: PositiveInt = Field(default=650, ge=1, le=10000)
    max_num_stream_replicas_on_primary: int = Field(default=0, ge=0, le=32)
    max_num_logical_replicas_on_primary: int = Field(default=0, ge=0, le=32)
    offshore_replication: bool = False

    # These are for the database tuning options
    workload_type: PG_WORKLOAD = Field(default=PG_WORKLOAD.HTAP)
    opt_mem_pool: PG_PROFILE_OPTMODE = Field(default=PG_PROFILE_OPTMODE.OPTIMUS_PRIME)
    keywords: PG_WEB_TUNE_USR_KWARGS = Field(default=PG_TUNE_USR_KWARGS())

    # Wraparound Tuning
    database_size_in_gib: int = Field(default=10, ge=0, le=32 * K10)
    num_write_transaction_per_hour_on_workload: PositiveInt = Field(default=int(50 * K10), ge=K10, le=20 * M10)
    # https://www.postgresql.org/docs/13/functions-info.html -> pg_current_xact_id_if_assigned


    # ========================================================================
    # This is used for analyzing the memory available.
    operating_system: str = Field(default='linux')
    logical_cpu: PositiveInt = Field(default=4, ge=1)
    total_ram_in_gib: ByteSize | PositiveFloat = Field(default=16, ge=2, multiple_of=0.25)
    base_kernel_memory_usage_in_mib: Annotated[ByteSize | int, Field(default=-1, ge=-1, le=8 * Ki)]
    base_monitoring_memory_usage_in_mib: Annotated[ByteSize | int, Field(default=-1, ge=-1, le=4 * Ki)]

    # ========================================================================
    enable_database_general_tuning: bool = True
    enable_database_correction_tuning: bool = True
    enable_sysctl_general_tuning: bool = False
    enable_sysctl_correction_tuning: bool = False

    # ========================================================================
    # Revert some invalid options as described in :attr:`is_os_user_managed`
    def to_backend(self) -> PG_TUNE_USR_OPTIONS:
        monitoring_memory = self.base_monitoring_memory_usage_in_mib
        kernel_memory = self.base_kernel_memory_usage_in_mib
        monitoring_memory = min(monitoring_memory, max(monitoring_memory, monitoring_memory * Mi))
        kernel_memory = min(kernel_memory, max(kernel_memory, kernel_memory * Mi))

        return PG_TUNE_USR_OPTIONS(
            # The basic profile for the system tuning for profile-guided tuning
            workload_profile=self.workload_profile,
            cpu_profile=self.workload_profile,
            mem_profile=self.workload_profile,
            net_profile=self.workload_profile,
            disk_profile=self.workload_profile,
            pgsql_version=self.pgsql_version,
            # Disk partitions
            os_db_spec=None,
            data_index_spec=self.data_index_spec.to_backend(),
            wal_spec=self.wal_spec.to_backend(),
            db_log_spec=None,
            # Data Integrity, Transaction, Crash Recovery, and Replication
            max_backup_replication_tool=self.max_backup_replication_tool,
            opt_transaction_lost=self.opt_transaction_lost,
            opt_wal_buffers=self.opt_wal_buffers,
            max_time_transaction_loss_allow_in_millisecond=self.max_time_transaction_loss_allow_in_millisecond,
            max_num_stream_replicas_on_primary=self.max_num_stream_replicas_on_primary,
            max_num_logical_replicas_on_primary=self.max_num_logical_replicas_on_primary,
            offshore_replication=self.offshore_replication,
            # Database tuning options
            workload_type=self.workload_type,
            opt_mem_pool=self.opt_mem_pool,
            tuning_kwargs=self.keywords.to_backend(),
            # Wraparound Tuning
            database_size_in_gib=self.database_size_in_gib,
            num_write_transaction_per_hour_on_workload=self.num_write_transaction_per_hour_on_workload,
            # Analyzing the memory available
            operating_system=self.operating_system,
            vcpu=self.logical_cpu,
            total_ram=ByteSize(self.total_ram_in_gib * Gi),
            base_kernel_memory_usage=kernel_memory,
            base_monitoring_memory_usage=monitoring_memory,
            # Questions of Application Operations to be done
            enable_database_general_tuning=self.enable_database_general_tuning,
            enable_database_correction_tuning=self.enable_database_correction_tuning,
            enable_sysctl_general_tuning=self.enable_sysctl_general_tuning,
            enable_sysctl_correction_tuning=self.enable_sysctl_correction_tuning,
            align_index=1,
        )

class PG_WEB_TUNE_REQUEST(BaseModel):
    user_options: PG_WEB_TUNE_USR_OPTIONS
    alter_style: bool = False
    backup_settings: bool = False
    output_format: Literal['json', 'conf', 'file'] = 'conf'

    analyze_with_full_connection_use: bool = False
    ignore_non_performance_setting: bool = True

    def to_backend(self) -> PG_TUNE_REQUEST:
        custom_style = None if not self.alter_style else 'ALTER SYSTEM SET $1 = $2;'
        backend_request = PG_TUNE_REQUEST(options=self.user_options.to_backend(), output_if_difference_only=False,
                                          include_comment=False, custom_style=custom_style)
        return backend_request