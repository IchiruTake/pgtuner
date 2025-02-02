import logging
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ByteSize
from pydantic.types import PositiveInt, PositiveFloat

from src.static.vars import K10, Ki, Gi, Mi, APP_NAME_UPPER, THROUGHPUT, RANDOM_IOPS, BASE_WAL_SEGMENT_SIZE, M10
from src.tuner.data.disks import PG_DISK_PERF, string_disk_to_performance
from src.tuner.data.keywords import PG_TUNE_USR_KWARGS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.sizing import PG_SIZING
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.pg_dataclass import PG_TUNE_REQUEST


__all__ = ['PG_WEB_TUNE_USR_OPTIONS', 'PG_WEB_TUNE_REQUEST']
_logger = logging.getLogger(APP_NAME_UPPER)

# =============================================================================
class _PG_WEB_DISK_PERF_BASE(BaseModel):
    random_iops_scale_factor: PositiveFloat = Field(default=0.9, gt=0, le=1.0)
    throughput_scale_factor: PositiveFloat = Field(default=0.9, gt=0, le=1.0)
    # ========================================================================
    # RAID efficiency
    per_scale_in_raid: PositiveFloat = Field(default=0.75, ge=1e-8, le=1.0)
    num_disks: PositiveInt = Field(default=1, ge=1, le=2 ** 6)
    disk_usable_size_in_gib: ByteSize = Field(default=20, ge=5)


_DEFAULT_DISK_STRING_CODE = 'ssdv2'
class _PG_WEB_DISK_PERF_STRING(_PG_WEB_DISK_PERF_BASE):
    random_iops: str = Field(default='ssdv2')
    throughput: str = Field(default='ssdv2')

    def to_backend(self) -> PG_DISK_PERF:
        _translate = string_disk_to_performance
        iops = _translate(self.random_iops, mode=RANDOM_IOPS)
        tput = _translate(self.throughput, mode=THROUGHPUT)
        return PG_DISK_PERF(read_random_iops_spec=iops, write_random_iops_spec=iops, read_throughput_spec=tput,
                            write_throughput_spec=tput, random_iops_scale_factor=self.random_iops_scale_factor,
                            throughput_scale_factor=self.throughput_scale_factor, num_disks=self.num_disks,
                            per_scale_in_raid=self.per_scale_in_raid, disk_usable_size=self.disk_usable_size_in_gib * Gi)


class _PG_WEB_DISK_PERF_INT(_PG_WEB_DISK_PERF_BASE):
    random_iops: PositiveInt = Field(default=string_disk_to_performance(_DEFAULT_DISK_STRING_CODE, mode=RANDOM_IOPS))
    throughput: PositiveInt = Field(default=string_disk_to_performance(_DEFAULT_DISK_STRING_CODE, mode=THROUGHPUT))

    def to_backend(self) -> PG_DISK_PERF:
        return PG_DISK_PERF(read_random_iops_spec=self.random_iops, write_random_iops_spec=self.random_iops,
                            read_throughput_spec=self.throughput, write_throughput_spec=self.throughput,
                            random_iops_scale_factor=self.random_iops_scale_factor,
                            throughput_scale_factor=self.throughput_scale_factor, num_disks=self.num_disks,
                            per_scale_in_raid=self.per_scale_in_raid, disk_usable_size=self.disk_usable_size_in_gib * Gi)


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
    effective_cache_size_available_ratio: PositiveFloat = Field(default=0.99, ge=0.93, le=1.0)
    shared_buffers_ratio: PositiveFloat = Field(default=0.25, ge=0.15, lt=0.60)
    shared_buffers_fill_ratio: PositiveFloat = Field(default=0.995, ge=0.95, le=1.0)
    max_work_buffer_ratio: PositiveFloat = Field(default=0.075, gt=0, le=0.50)
    effective_connection_ratio: PositiveFloat = Field(default=0.75, ge=0.25, le=1.0)
    temp_buffers_ratio: PositiveFloat = Field(default=2/3, ge=0.25, le=0.95)
    work_mem_scale_factor: PositiveFloat = Field(default=1.0, gt=0, le=3.0)

    # These are used for memory_precision_tuning
    max_normal_memory_usage: PositiveFloat = Field(default=0.45, ge=0.35, le=0.85)
    mem_pool_epsilon_to_rollback: PositiveFloat = Field(default=0.01, ge=0, le=0.02)
    mem_pool_tuning_increment: PositiveFloat = Field(default=1 / 280, ge=1 / 2000, le=0.01)
    mem_pool_tuning_ratio: float = Field(default=0.5, ge=0, le=1)
    mem_pool_max_iterations: int = Field(default=100, ge=0, le=1000)
    mem_pool_parallel_estimate: bool = Field(default=False)

    # WAL control parameters -> Change this when you initdb with custom wal_segment_size
    wal_segment_size: PositiveInt = Field(default=1, ge=1, le=128, frozen=True)
    min_wal_ratio_scale: PositiveFloat = Field(default=0.5, ge=0.01, le=3.0)
    max_wal_size_ratio: PositiveFloat = Field(default=0.90, gt=0.0, lt=1.0)
    max_wal_size_remain_upper_size_in_gib: ByteSize = Field(default=256, ge=1, le=2 * Ki)

    # Tune logging behaviour (query size, and query runtime)
    max_query_length_in_bytes: ByteSize = Field(default=2 * Ki, ge=64, le=64 * Mi)
    max_runtime_ms_to_log_slow_query: PositiveInt = Field(default=2 * K10, ge=20, le=100 * K10)
    max_runtime_ratio_to_explain_slow_query: PositiveFloat = Field(default=1.5, ge=0.1, le=10.0)

    # Background Writer Tuning
    bgwriter_utilization_ratio: PositiveFloat = Field(default=0.15, gt=0, le=0.4)

    # Vacuum Tuning
    autovacuum_utilization_ratio: PositiveFloat = Field(default=0.80, gt=0.50, le=0.95)

    # Transaction Rate
    num_write_transaction_per_hour_on_workload: PositiveInt = Field(default=int(1 * M10), ge=K10, le=50 * M10)

    def to_backend(self) -> PG_TUNE_USR_KWARGS:
        return PG_TUNE_USR_KWARGS(
            user_max_connections=self.user_max_connections,
            superuser_reserved_connections_scale_ratio=self.superuser_reserved_connections_scale_ratio,
            single_memory_connection_overhead=self.single_memory_connection_overhead_in_kib * Ki,
            memory_connection_to_dedicated_os_ratio=self.memory_connection_to_dedicated_os_ratio,
            effective_cache_size_available_ratio=self.effective_cache_size_available_ratio,
            shared_buffers_ratio=self.shared_buffers_ratio,
            max_work_buffer_ratio=self.max_work_buffer_ratio,
            effective_connection_ratio=self.effective_connection_ratio,
            temp_buffers_ratio=self.temp_buffers_ratio,
            work_mem_scale_factor=self.work_mem_scale_factor,
            max_normal_memory_usage=self.max_normal_memory_usage,
            mem_pool_epsilon_to_rollback=self.mem_pool_epsilon_to_rollback,
            mem_pool_tuning_increment=self.mem_pool_tuning_increment,
            mem_pool_tuning_ratio=self.mem_pool_tuning_ratio,
            mem_pool_max_iterations=self.mem_pool_max_iterations,
            mem_pool_parallel_estimate=self.mem_pool_parallel_estimate,
            wal_segment_size=self.wal_segment_size * BASE_WAL_SEGMENT_SIZE,
            max_query_length_in_bytes=self.max_query_length_in_bytes,
            max_runtime_ms_to_log_slow_query=self.max_runtime_ms_to_log_slow_query,
            max_runtime_ratio_to_explain_slow_query=self.max_runtime_ratio_to_explain_slow_query,
            min_wal_ratio_scale=self.min_wal_ratio_scale,
            max_wal_size_ratio=self.max_wal_size_ratio,
            max_wal_size_remain_upper_size=self.max_wal_size_remain_upper_size_in_gib * Gi,
            bgwriter_utilization_ratio=self.bgwriter_utilization_ratio,
            autovacuum_utilization_ratio=self.autovacuum_utilization_ratio,
            num_write_transaction_per_hour_on_workload=self.num_write_transaction_per_hour_on_workload
        )


class PG_WEB_TUNE_USR_OPTIONS(BaseModel):
    # Note that in here we just adhere to the Pydantic datatype and not constraint to the list of allowed values
    # Also, not all the values are used in a web application. So we decided to prune some of them.

    # The basic profile for the system tuning for profile-guided tuning
    workload_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    cpu_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    mem_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    disk_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
    net_profile: PG_SIZING = Field(default=PG_SIZING.LARGE)
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
    repurpose_wal_buffers: bool = True
    max_time_transaction_loss_allow_in_millisecond: PositiveInt = Field(default=650, ge=1, le=10000)
    max_num_stream_replicas_on_primary: int = Field(default=0, ge=0, le=32)
    max_num_logical_replicas_on_primary: int = Field(default=0, ge=0, le=32)
    offshore_replication: bool = False

    # These are for the database tuning options
    workload_type: PG_WORKLOAD = Field(default=PG_WORKLOAD.HTAP)
    opt_mem_pool: PG_PROFILE_OPTMODE = Field(default=PG_PROFILE_OPTMODE.OPTIMUS_PRIME)
    keywords: PG_WEB_TUNE_USR_KWARGS = Field(default=PG_TUNE_USR_KWARGS())


    # ========================================================================
    # This is used for analyzing the memory available.
    operating_system: str = Field(default='linux')
    logical_cpu: PositiveInt = Field(default=4, ge=1)
    ram_sample_in_gib: ByteSize | PositiveFloat = Field(default=16, ge=2, multiple_of=0.25)
    add_system_reserved_memory_into_ram: bool = False
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

        backend_options = PG_TUNE_USR_OPTIONS(
            # The basic profile for the system tuning for profile-guided tuning
            workload_profile=self.workload_profile,
            cpu_profile=self.cpu_profile,
            mem_profile=self.mem_profile,
            net_profile=self.net_profile,
            disk_profile=self.disk_profile,
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
            repurpose_wal_buffers=self.repurpose_wal_buffers,
            max_time_transaction_loss_allow_in_millisecond=self.max_time_transaction_loss_allow_in_millisecond,
            max_num_stream_replicas_on_primary=self.max_num_stream_replicas_on_primary,
            max_num_logical_replicas_on_primary=self.max_num_logical_replicas_on_primary,
            offshore_replication=self.offshore_replication,
            # Database tuning options
            workload_type=self.workload_type,
            opt_mem_pool=self.opt_mem_pool,
            tuning_kwargs=self.keywords.to_backend(),
            # Analyzing the memory available
            operating_system=self.operating_system,
            vcpu=self.logical_cpu,
            ram_sample=ByteSize(self.ram_sample_in_gib * Gi),
            add_system_reserved_memory_into_ram=self.add_system_reserved_memory_into_ram,
            base_kernel_memory_usage=kernel_memory,
            base_monitoring_memory_usage=monitoring_memory,
            # Questions of Application Operations to be done
            enable_database_general_tuning=self.enable_database_general_tuning,
            enable_database_correction_tuning=self.enable_database_correction_tuning,
            enable_sysctl_general_tuning=self.enable_sysctl_general_tuning,
            enable_sysctl_correction_tuning=self.enable_sysctl_correction_tuning,
            align_index=1,
        )

        # Scan and Update the current configuration
        backend_options_dumps = backend_options.model_dump()
        for key, value in backend_options_dumps.items():
            if key in self.__dict__:
                self.__dict__[key] = value

        return backend_options

class PG_WEB_TUNE_REQUEST(BaseModel):
    user_options: PG_WEB_TUNE_USR_OPTIONS
    alter_style: bool = False
    backup_settings: bool = False
    output_format: Literal['json', 'conf', 'file'] = 'conf'
    analyze_with_full_connection_use: bool = False

    def to_backend(self) -> PG_TUNE_REQUEST:
        custom_style = None if not self.alter_style else 'ALTER SYSTEM SET $1 = $2;'
        backend_request = PG_TUNE_REQUEST(options=self.user_options.to_backend(), output_if_difference_only=False,
                                          include_comment=False, custom_style=custom_style)
        return backend_request