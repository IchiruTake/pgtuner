import json
import logging
import os
from time import perf_counter
from typing import Literal

from pydantic import ByteSize, PositiveFloat, PositiveInt

from src.tuner.base import GeneralOptimize
from src.utils.static import (APP_NAME_UPPER, SUGGESTION_ENTRY_READER_DIR, Gi, K10, )
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.options import PG_TUNE_USR_OPTIONS, PG_TUNE_USR_KWARGS
from src.tuner.data.workload import PG_PROFILE_OPTMODE, PG_BACKUP_TOOL, PG_WORKLOAD
from src.tuner.data.scope import PGTUNER_SCOPE
from src.tuner.pg_dataclass import PG_TUNE_REQUEST, PG_TUNE_RESPONSE
from src.tuner.profile.database.gtune_13 import DB13_CONFIG_PROFILE
from src.tuner.profile.database.gtune_14 import DB14_CONFIG_PROFILE
from src.tuner.profile.database.gtune_15 import DB15_CONFIG_PROFILE
from src.tuner.profile.database.gtune_16 import DB16_CONFIG_PROFILE
from src.tuner.profile.database.gtune_17 import DB17_CONFIG_PROFILE
from src.tuner.profile.database.stune import correction_tune
from src.utils.timing import time_decorator

_profiles = {
    13: DB13_CONFIG_PROFILE,
    14: DB14_CONFIG_PROFILE,
    15: DB15_CONFIG_PROFILE,
    16: DB16_CONFIG_PROFILE,
    17: DB17_CONFIG_PROFILE,
}
_logger = logging.getLogger(APP_NAME_UPPER)
_SIZING = ByteSize | int | float
__all__ = ['init', 'optimize',]


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
        GeneralOptimize(request, response, target=PGTUNER_SCOPE.KERNEL_SYSCTL, tuning_items=KERNEL_SYSCTL_PROFILE)
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
        db_config_profile = _profiles.get(request.options.pgsql_version, DB13_CONFIG_PROFILE)
        GeneralOptimize(request, response, target=PGTUNER_SCOPE.DATABASE_CONFIG, tuning_items=db_config_profile)
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
def write(request: PG_TUNE_REQUEST, response: PG_TUNE_RESPONSE, scope: PGTUNER_SCOPE = PGTUNER_SCOPE.DATABASE_CONFIG,
          output_format: Literal['json', 'file', 'conf'] = 'conf', output_file: str = None,
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
