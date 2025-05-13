"""
---------------------------------------------------------------------------
This script is the PostgreSQL database collector for the PyCollect project, which 
aims to collect the current profile and brings out meaningful suggestions for 
database tuning. This script is written in Python and uses the psycopg2 library
to interact with the PostgreSQL database.

The script includes two parts:
- Collect and backup the database profile
- Analyze the profile and generate suggestions

This work may not be there without these great projects:
- PostgreSQL: https://www.postgresql.org/
- postgresqltuner: https://github.com/jfcoz/postgresqltuner/blob/master/postgresqltuner.pl
- timescaledb-tune: https://github.com/timescale/timescaledb-tune

"""
import os
from zoneinfo import ZoneInfo
from typing import Literal
from datetime import datetime

from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.options import PG_TUNE_USR_OPTIONS, PG_TUNE_USR_KWARGS
from src.tuner.data.workload import PG_SIZING, PG_WORKLOAD, PG_PROFILE_OPTMODE, PG_BACKUP_TOOL
from src.utils.mean import generalized_mean
from src.utils.static import DATETIME_PATTERN_FOR_FILENAME, Gi, SUGGESTION_ENTRY_READER_DIR, K10, Mi, Ki, \
    BASE_WAL_SEGMENT_SIZE
from src.tuner.data.scope import PGTUNER_SCOPE

from src import pgtuner
from src.tuner.pg_dataclass import PG_TUNE_REQUEST


# ==================================================================================================
# Metadata


def optimize(request: PG_TUNE_REQUEST, output_format: Literal['json', 'text', 'file', 'conf'] = 'conf'):
    # entry.init(request)
    response = pgtuner.optimize(request)

    if request.options.enable_sysctl_general_tuning:
        dt_start = datetime.now(ZoneInfo('UTC'))
        filepath = f'{PGTUNER_SCOPE.KERNEL_SYSCTL.value}_{dt_start.strftime(DATETIME_PATTERN_FOR_FILENAME)}.conf'
        result = pgtuner.write(request, response, PGTUNER_SCOPE.KERNEL_SYSCTL, output_format=output_format,
                               output_file=os.path.join(SUGGESTION_ENTRY_READER_DIR, filepath), exclude_names=[])

        # pprint(result)


    if request.options.enable_database_general_tuning:
        dt_start = datetime.now(ZoneInfo('UTC'))
        filepath = f'{PGTUNER_SCOPE.DATABASE_CONFIG.value}_{dt_start.strftime(DATETIME_PATTERN_FOR_FILENAME)}.conf'
        result = pgtuner.write(request, response, PGTUNER_SCOPE.DATABASE_CONFIG, output_format=output_format,
                               output_file=os.path.join(SUGGESTION_ENTRY_READER_DIR, filepath), exclude_names=[])
        filepath = f'{PGTUNER_SCOPE.DATABASE_CONFIG.value}_{dt_start.strftime(DATETIME_PATTERN_FOR_FILENAME)}.txt'
        with open(os.path.join(SUGGESTION_ENTRY_READER_DIR, filepath), 'w') as f:
            f.write(response.report(request.options, use_full_connection=True, ignore_report=False)[0])


        # pprint(result)

    # Test the logger of rotation
    # _logger = logging.getLogger(APP_NAME_UPPER)
    # for _handlers in _logger.handlers:
    #     if isinstance(_handlers, (logging.handlers.RotatingFileHandler, logging.handlers.TimedRotatingFileHandler)):
    #         _handlers.doRollover()
    return response



if __name__ == "__main__":
    data_index_disk = PG_DISK_PERF(
        random_iops_spec=5 * K10, random_iops_scale_factor=1.0,
        throughput_spec=350, throughput_scale_factor=1.0,
        disk_usable_size=128 * Gi, num_disks=1
    )
    wal_disk = PG_DISK_PERF(
        random_iops_spec=5 * K10, random_iops_scale_factor=1.0,
        throughput_spec=500, throughput_scale_factor=1.0,
        disk_usable_size=256 * Gi, num_disks=1
    )
    kw = PG_TUNE_USR_KWARGS(
        # Connection
        user_max_connections=0, # Default to let pgtuner manage the number of connections
        superuser_reserved_connections_scale_ratio=1.5, # [1, 3]. Higher for less superuser reserved connections
        single_memory_connection_overhead=5 * Mi, # [2, 12]. Default is 5 MiB. This is estimation and not big impact
        memory_connection_to_dedicated_os_ratio=0.7, # [0, 1]. Default is 0.7. This is estimation and not big impact

        # Memory Utilization (Basic)
        effective_cache_size_available_ratio=0.985, # [0.95, 1.0]. Default is 0.985 (98.5%).
        shared_buffers_ratio=0.25, # [0.15, 0.60). Default is 0.25 (25%). The starting ratio
        max_work_buffer_ratio=0.075, # [0.0, 0.50]. Default is 0.075 (7.5%). The starting ratio
        effective_connection_ratio=0.75, # [0.25, 1.0]. Default is 0.75 (75%). Only this ratio are maintained connected
        temp_buffers_ratio=0.25, # [0.05, 0.95]. Default is 0.25 (25%). The ratio of temp_buffers to total

        # Memory Utilization (Advanced)
        max_normal_memory_usage=0.45, # [0.35, 0.80]. Default is 0.45 (45%). The optimized ratio for normal memory usage
        mem_pool_tuning_ratio=0.4, # [0.0, 1.0]. Default is 0.4 (40%). The optimized ratio for memory pool tuning
        # Maximum float allowed is [-60, 60] under 64-bit system
        hash_mem_usage_level=-5, # [-50, 50]. Default is -6. The optimized ratio for hash memory usage level
        mem_pool_parallel_estimate=True, # Default is True to assume the use of p

        # Logging behaviour (query size, and query runtime)
        max_query_length_in_bytes=2 * Ki, # [64, 64 * Mi]. Default is 2 KiB. The maximum query length in bytes
        max_runtime_ms_to_log_slow_query=2 * K10, # [20, 100 * K10]. Default is 2000 ms (or 2 seconds). The maximum
        max_runtime_ratio_to_explain_slow_query=1.5, # [0.1, 10.0]. Default is 1.5. The ratio to EXPLAIN

        # WAL control parameters -> Change this when you initdb with custom wal_segment_size (not recommended)
        # https://postgrespro.com/list/thread-id/1898949
        # TODO: Whilst PostgreSQL allows up to 2 GiB, my recommendation is to limited below 128 MiB to prevent issue
        wal_segment_size=BASE_WAL_SEGMENT_SIZE, # [16 * Mi, 128 * Mi]. Default is 16 MiB. The WAL segment size
        min_wal_size_ratio=0.05, # [0.0, 0.15]. Default is 0.05 (5%). The ratio of the min_wal_size
        max_wal_size_ratio=0.05, # [0.0, 0.30]. Default is 0.05 (5%). The ratio to force CHECKPOINT
        wal_keep_size_ratio=0.05, # [0.0, 0.30]. Default is 0.05 (5%). The ratio to keep for replication

        # Vacuum Tuning
        autovacuum_utilization_ratio=0.80, # [0.30, 0.95]. Default is 0.80 (80%). The utilization of the random IOPS
        vacuum_safety_level=2, # [0, 12]. Default is 2. The safety level of the vacuum process # Think as CHUNK
    )

    options = PG_TUNE_USR_OPTIONS(
        ## Operation Mode
        enable_sysctl_general_tuning=False, enable_sysctl_correction_tuning=False,
        enable_database_general_tuning=True, enable_database_correction_tuning=True,
        ## User-Tuning Profiles
        workload_profile=PG_SIZING.LARGE, pgsql_version=17,
        database_size_in_gib=0, # [0, 1000]. Default is 0 GiB for maximum of 60% of data disk
        num_write_transaction_per_hour_on_workload=50 * K10, # [K10, 20 * M10]. Default is 50 * K10 (50K).
        align_index=1, # [0, 1]. Default is 1. Choose the higher number during alignment
        ## Disk Performance
        data_index_spec=data_index_disk, wal_spec=wal_disk,

        ## PostgreSQL Tuning Configuration
        tuning_kwargs=kw, workload_type=PG_WORKLOAD.HTAP, operating_system='containerd',
        base_kernel_memory_usage=-1, base_monitoring_memory_usage=-1,   # To let pgtuner manage the memory usage
        vcpu=8, total_ram=8 * 5 * Gi,
        opt_mem_pool=PG_PROFILE_OPTMODE.OPTIMUS_PRIME,

        ## PostgreSQL Data Integrity
        opt_transaction_lost=PG_PROFILE_OPTMODE.NONE, opt_wal_buffers=PG_PROFILE_OPTMODE.SPIDEY,
        max_time_transaction_loss_allow_in_millisecond=650,
        max_num_stream_replicas_on_primary=0,
        max_num_logical_replicas_on_primary=0,
        max_backup_replication_tool=PG_BACKUP_TOOL.PG_BASEBACKUP,
        offshore_replication=False,
    )
    rq = PG_TUNE_REQUEST(options=options, include_comment=False, custom_style=None)
    response = optimize(rq, output_format='file')
    # print(generalized_mean(1, 2.0, level=-5, round_ndigits=4))
    pass
