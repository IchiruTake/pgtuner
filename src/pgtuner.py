import json
import logging
import os
from time import perf_counter
from typing import Literal

from pydantic import ByteSize, PositiveFloat, PositiveInt

from src.utils.static import (APP_NAME_UPPER, SUGGESTION_ENTRY_READER_DIR, Gi, K10, )
from src.tuner.base import GeneralTuner
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.options import PG_TUNE_USR_OPTIONS, PG_TUNE_USR_KWARGS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE, PG_BACKUP_TOOL
from src.tuner.data.scope import PGTUNER_SCOPE
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.pg_dataclass import PG_TUNE_REQUEST, PG_TUNE_RESPONSE
from src.tuner.profile.database.gtune_0 import DB0_CONFIG_PROFILE
from src.tuner.profile.database.gtune_13 import DB13_CONFIG_PROFILE
from src.tuner.profile.database.gtune_14 import DB14_CONFIG_PROFILE
from src.tuner.profile.database.gtune_15 import DB15_CONFIG_PROFILE
from src.tuner.profile.database.gtune_16 import DB16_CONFIG_PROFILE
from src.tuner.profile.database.gtune_17 import DB17_CONFIG_PROFILE
from src.tuner.profile.database.stune import correction_tune
from src.utils.timing import time_decorator

_profiles = {
    0: DB0_CONFIG_PROFILE,
    13: DB13_CONFIG_PROFILE,
    14: DB14_CONFIG_PROFILE,
    15: DB15_CONFIG_PROFILE,
    16: DB16_CONFIG_PROFILE,
    17: DB17_CONFIG_PROFILE,
}
_logger = logging.getLogger(APP_NAME_UPPER)
_SIZING = ByteSize | int | float
__all__ = ['init', 'optimize', 'make_disk', 'make_tuning_keywords', 'make_tune_request']


# ==================================================================================================
# Initialize folders
def init() -> None:
    _logger.info(f'Initializing the {APP_NAME_UPPER} application. Create the directory structure of '
                 f'{SUGGESTION_ENTRY_READER_DIR}')

    os.makedirs(SUGGESTION_ENTRY_READER_DIR, mode=0o640, exist_ok=True)
    return None


# ==================================================================================================
@time_decorator
def _tune_sysctl(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    found_tuning: bool = False
    t = perf_counter()
    if request.options.enable_sysctl_general_tuning:
        _logger.info('=========================================================================================='
                     '\nStart general tuning on the sysctl-based parameters.')
        from src.tuner.profile.linux.gtune_0 import KERNEL_SYSCTL_PROFILE
        sysctl_tuner = GeneralTuner(target=PGTUNER_SCOPE.KERNEL_SYSCTL, items=KERNEL_SYSCTL_PROFILE)
        sysctl_tuner.optimize(request=request, response=response)
        found_tuning = True

    if request.options.enable_sysctl_correction_tuning:
        _logger.info('=========================================================================================='
                     '\nStart correction tuning on the sysctl-based parameters.')
        pass

    if not found_tuning:
        _logger.warning('No tuning is executed for the sysctl-based parameters.')
        return None
    _logger.info(f'General & Correction tuning on the sysctl-based parameters is completed.'
                 f'\nElapsed time: {(perf_counter() - t) * K10:.2f} (ms).')
    return None


@time_decorator
def _tune_pgdb(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE):
    found_tuning: bool = False
    t = perf_counter()
    if request.options.enable_database_general_tuning:
        _logger.info('=========================================================================================='
                     '\nStart general tuning on the PostgreSQL database settings.')
        db_config_profile = _profiles.get(request.options.pgsql_version, DB0_CONFIG_PROFILE)
        dbconf_tuner = GeneralTuner(target=PGTUNER_SCOPE.DATABASE_CONFIG, items=db_config_profile)
        dbconf_tuner.optimize(request=request, response=response)
        found_tuning = True

    if request.options.enable_database_correction_tuning:
        _logger.info('=========================================================================================='
                     '\nStart correction tuning on the PostgreSQL database settings.')
        correction_tune(request, response)
        found_tuning = True

    if not found_tuning:
        _logger.warning('No tuning is found for the database-based parameters.')
        return None
    _logger.info(f'General & Correction tuning on the PostgreSQL database settings is completed.'
                 f'\nElapsed time: {(perf_counter() - t) * K10:.2f} (ms).')

    return None


@time_decorator
def optimize(request: PG_TUNE_REQUEST):
    _logger.info(f'Start tuning the system based on generated request.')
    response = PG_TUNE_RESPONSE()

    # [01]: Perform tuning on the sysctl-based parameters if the OS is managed by the user
    if request.options.operating_system == 'linux':
        _tune_sysctl(request, response)
    else:
        _logger.warning('The system tuning is not supported on the non-Linux operating system.')

    # [02]: Perform general tuning on the PostgreSQL configuration file
    _tune_pgdb(request, response)

    return response


# ==================================================================================================
# Receive user tuning options
_OS_DB_DISK_STRING_CODE = 'ssdv1'
_DATA_INDEX_DISK_STRING_CODE = 'ssdv2'
_WAL_DISK_STRING_CODE = 'ssdv2'
_DB_LOG_DISK_STRING_CODE = 'hddv1'


def make_disk(disk_string_code_throughput: str = _OS_DB_DISK_STRING_CODE,
              disk_string_code_rand_iops: str = _OS_DB_DISK_STRING_CODE,
              num_disks: PositiveInt = 1, disk_usable_size: _SIZING = 500 * Gi,
              random_iops_spec: _SIZING | str = None, random_iops_scale_factor: PositiveFloat = 0.9,
              throughput_spec: _SIZING | str = None, throughput_scale_factor: PositiveFloat = 0.9,
              per_scale_in_raid: PositiveFloat = 0.75) -> PG_DISK_PERF:
    return PG_DISK_PERF(random_iops_spec=random_iops_spec or disk_string_code_rand_iops,
                        random_iops_scale_factor=random_iops_scale_factor,
                        throughput_spec=throughput_spec or disk_string_code_throughput,
                        throughput_scale_factor=throughput_scale_factor, disk_usable_size=disk_usable_size,
                        per_scale_in_raid=per_scale_in_raid, num_disks=num_disks)


def make_tuning_keywords(**kwargs: _SIZING) -> PG_TUNE_USR_KWARGS:
    return PG_TUNE_USR_KWARGS(**kwargs)


def make_tune_request(
        enable_sysctl_general_tuning: bool = False, enable_sysctl_correction_tuning: bool = False,
        enable_database_general_tuning: bool = True, enable_database_correction_tuning: bool = True,

        ## User-Tuning Profiles
        workload_profile: str = 'large', cpu_profile: str = 'large', mem_profile: str = 'large',
        net_profile: str = 'large', disk_profile: str = 'large', pgsql_version: str = 17 ,

        ## Disk Performance
        disk_template: PG_DISK_PERF = make_disk(_DATA_INDEX_DISK_STRING_CODE, _DATA_INDEX_DISK_STRING_CODE),
        os_db_disk: PG_DISK_PERF = make_disk(_OS_DB_DISK_STRING_CODE, _OS_DB_DISK_STRING_CODE),
        data_index_disk: PG_DISK_PERF = make_disk(_DATA_INDEX_DISK_STRING_CODE, _DATA_INDEX_DISK_STRING_CODE),
        wal_disk: PG_DISK_PERF = make_disk(_WAL_DISK_STRING_CODE, _WAL_DISK_STRING_CODE),
        db_log_disk: PG_DISK_PERF = make_disk(_DB_LOG_DISK_STRING_CODE, _DB_LOG_DISK_STRING_CODE),

        ## PostgreSQL Tuning Configuration
        workload_type: PG_WORKLOAD = PG_WORKLOAD.HTAP,
        opt_mem_pool: PG_PROFILE_OPTMODE = PG_PROFILE_OPTMODE.OPTIMUS_PRIME,
        operating_system: str = 'linux',
        base_kernel_memory_usage: _SIZING = -1,
        base_monitoring_memory_usage: _SIZING = -1,
        tuning_keywords: PG_TUNE_USR_KWARGS = make_tuning_keywords(),
        logical_cpu: int = 4,
        total_ram: _SIZING = 16 * Gi,

        ## PostgreSQL Data Integrity
        opt_transaction_lost: PG_PROFILE_OPTMODE = PG_PROFILE_OPTMODE.NONE,
        opt_wal_buffers: PG_PROFILE_OPTMODE = PG_PROFILE_OPTMODE.SPIDEY,
        max_time_transaction_loss_allow_in_millisecond: PositiveInt = 650,
        max_num_stream_replicas_on_primary: PositiveInt = 0,
        max_num_logical_replicas_on_primary: PositiveInt = 0,
        max_backup_replication_tool: str = 'pg_basebackup',
        offshore_replication: bool = False,

        ## How to output item
        output_if_difference_only: bool = False,
        include_comment: bool = False,
        custom_style: str | None = None,
) -> PG_TUNE_REQUEST:

    options = PG_TUNE_USR_OPTIONS(
        ## Operation Mode
        enable_sysctl_general_tuning=enable_sysctl_general_tuning,
        enable_sysctl_correction_tuning=enable_sysctl_correction_tuning,
        enable_database_general_tuning=enable_database_general_tuning,
        enable_database_correction_tuning=enable_database_correction_tuning,
        ## User-Tuning Profiles
        workload_profile=workload_profile,

        pgsql_version=pgsql_version,
        ## Disk Performance
        data_index_spec=data_index_disk or disk_template,
        wal_spec=wal_disk or disk_template,
        ## PostgreSQL Tuning Configuration
        workload_type=workload_type, operating_system=operating_system,
        base_kernel_memory_usage=base_kernel_memory_usage, base_monitoring_memory_usage=base_monitoring_memory_usage,
        tuning_kwargs=tuning_keywords, vcpu=logical_cpu, total_ram=total_ram,
        opt_mem_pool=opt_mem_pool,

        ## PostgreSQL Data Integrity
        opt_transaction_lost=opt_transaction_lost, opt_wal_buffers=opt_wal_buffers,
        max_time_transaction_loss_allow_in_millisecond=max_time_transaction_loss_allow_in_millisecond,
        max_num_stream_replicas_on_primary=max_num_stream_replicas_on_primary,
        max_num_logical_replicas_on_primary=max_num_logical_replicas_on_primary,
        max_backup_replication_tool=PG_BACKUP_TOOL(max_backup_replication_tool),
        offshore_replication=offshore_replication,
    )
    return PG_TUNE_REQUEST(options=options, output_if_difference_only=output_if_difference_only,
                           include_comment=include_comment, custom_style=custom_style)


def write(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, scope: PGTUNER_SCOPE = PGTUNER_SCOPE.DATABASE_CONFIG,
          output_format: Literal['json', 'text', 'file', 'conf'] = 'conf', output_file: str = None,
          exclude_names: list[str] | set[str] = None, backup_settings: bool = True) -> str | dict | None:
    content = response.generate_content(target=scope, exclude_names=exclude_names, output_format=output_format,
                                        request=request, backup_settings=backup_settings)
    if output_file is not None:
        _logger.info(f'Writing the tuning result to the file: {output_file} with format {output_format}')
        if isinstance(content, str):
            with open(output_file, 'w') as f:
                f.write(content)
        else:
            json.dump(content, open(output_file, 'w'), indent=2)

    return content
