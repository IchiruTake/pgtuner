import json
import logging
import os
from time import perf_counter
from pydantic import ByteSize

from src.tuner.base import GeneralOptimize
from src.tuner.profile.database.gtune_18 import DB18_CONFIG_PROFILE
from src.utils.static import (APP_NAME_UPPER, SUGGESTION_ENTRY_READER_DIR, K10, )

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
    18: DB18_CONFIG_PROFILE
}
_logger = logging.getLogger(APP_NAME_UPPER)
_SIZING = ByteSize | int | float
__all__ = ['optimize',]

# ==================================================================================================
@time_decorator
def optimize(request: PG_TUNE_REQUEST, database_filename: str = None):
    _logger.info(f'Initializing the {APP_NAME_UPPER} application. Create the directory structure of '
                 f'{SUGGESTION_ENTRY_READER_DIR}')
    os.makedirs(SUGGESTION_ENTRY_READER_DIR, mode=0o640, exist_ok=True)

    _logger.info(f'Start tuning the system based on generated request.')
    response = PG_TUNE_RESPONSE()
    result = {
        'response': response,
    }

    # [01]: Perform tuning on the sysctl-based parameters if the OS is managed by the user
    t = perf_counter()
    if request.options.operating_system == 'linux' and request.options.enable_sysctl_general_tuning:
        _logger.info('=========================================================================================='
                     '\nStart general tuning on the sysctl-based parameters.')
        from src.tuner.profile.linux.gtune_0 import KERNEL_SYSCTL_PROFILE
        GeneralOptimize(request, response, target=PGTUNER_SCOPE.KERNEL_SYSCTL, tuning_items=KERNEL_SYSCTL_PROFILE)
        if request.options.enable_sysctl_correction_tuning:
            _logger.info('=========================================================================================='
                         '\nStart correction tuning on the sysctl-based parameters.')
    else:
        _logger.warning('The system tuning is not supported on the non-Linux operating system.')

    # [02]: Perform general tuning on the PostgreSQL configuration file
    if request.options.enable_database_general_tuning:
        _logger.info('=========================================================================================='
                     '\nStart general tuning on the PostgreSQL database settings.')
        db_config_profile = _profiles.get(request.options.pgsql_version, DB13_CONFIG_PROFILE)
        GeneralOptimize(request, response, target=PGTUNER_SCOPE.DATABASE_CONFIG, tuning_items=db_config_profile)

        if request.options.enable_database_correction_tuning:
            _logger.info('=========================================================================================='
                         '\nStart correction tuning on the PostgreSQL database settings.')
            correction_tune(request, response)
    print(f'Tuning on the PostgreSQL database settings is completed within {K10 * (perf_counter() - t):.2f} (ms).')

    # ===========================================================================================
    # [03]: Write the tuning result to the file
    if request.options.enable_database_general_tuning:
        # Display the content and perform memory testing validation
        default_exclude_names = [
            'archive_command', 'restore_command', 'archive_cleanup_command',  'recovery_end_command',
            'log_directory'
        ]
        if request.ignore_non_performance_setting:
            default_exclude_names.extend([
                'deadlock_timeout', 'transaction_timeout', 'idle_session_timeout', 'log_autovacuum_min_duration',
                'log_checkpoints', 'log_connections', 'log_disconnections', 'log_duration', 'log_error_verbosity',
                'log_line_prefix', 'log_lock_waits', 'log_recovery_conflict_waits', 'log_statement',
                'log_replication_commands', 'log_min_error_statement', 'log_startup_progress_interval'
            ])

        if request.options.operating_system == 'windows':
            default_exclude_names.extend([
                'checkpoint_flush_after', 'bgwriter_flush_after', 'wal_writer_flush_after', 'backend_flush_after'
            ])

        content = response.generate_config(
            target=PGTUNER_SCOPE.DATABASE_CONFIG, request=request,
            exclude_names=default_exclude_names,
        )
        result['content'] = content

        report = response.report(
            request.options, use_full_connection=request.analyze_with_full_connection_use, ignore_report=False
        )[0]
        result['mem_report'] = report

        if database_filename:
            _logger.info(f'Writing the tuning result to the file: {database_filename} with format '
                         f'{request.output_format}')
            with open(os.path.join(SUGGESTION_ENTRY_READER_DIR, database_filename + '.conf'), 'w', encoding='utf8') as f:
                if request.output_format != 'json':
                    f.write(content)
                else:
                    json.dump(content, f, indent=2)

            with open(os.path.join(SUGGESTION_ENTRY_READER_DIR, database_filename + '.txt'), 'w', encoding='utf8') as f:
                f.write(report)

    return result


