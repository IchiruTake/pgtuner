import glob
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pprint import pformat

import psycopg
import toml
from dotenv import load_dotenv
from psycopg.rows import dict_row
from pydantic import ByteSize, PositiveFloat, PositiveInt

from src.static.c_timezone import PreloadGetUTC
from src.static.vars import (BACKUP_FILE_FORMAT, __VERSION__, APP_NAME_UPPER,
                             BACKUP_ENTRY_READER_DIR, SUGGESTION_ENTRY_READER_DIR, DATETIME_PATTERN_FOR_FILENAME, Gi, )
from src.static.vars import (ENV_PGPORT, ENV_PGHOST, ENV_PGDATABASE, ENV_PGUSER, ENV_PGPASSWORD, ENV_PGC_CONN_EXTARGS)
from src.tuner.base import GeneralTuner
from src.tuner.data.connection import PG_CONNECTION
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.keywords import PG_TUNE_USR_KWARGS
from src.tuner.data.options import PG_TUNE_USR_OPTIONS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.external.psutil_api import SERVER_SNAPSHOT
from src.tuner.pg_dataclass import PG_TUNE_REQUEST, PG_SYS_SHARED_INFO
from src.tuner.profile.stune_db_config import correction_tune
from src.utils.env import GetEnvVar

_logger = logging.getLogger(APP_NAME_UPPER)
_utc_tz = PreloadGetUTC()[0]
_SIZING = ByteSize | int | float
_HOSTVARS = [f"{APP_NAME_UPPER}_{ENV_PGHOST}", ENV_PGHOST]
_PORTVARS = [f"{APP_NAME_UPPER}_{ENV_PGPORT}", ENV_PGPORT]
_USERVARS = [f"{APP_NAME_UPPER}_{ENV_PGUSER}", ENV_PGUSER]
_PWDVARS = [f"{APP_NAME_UPPER}_{ENV_PGPASSWORD}", ENV_PGPASSWORD]
_DBVARS = [f"{APP_NAME_UPPER}_{ENV_PGDATABASE}", ENV_PGDATABASE]
_CONNEXTRAVARS = [f"{APP_NAME_UPPER}_{ENV_PGC_CONN_EXTARGS}", ENV_PGC_CONN_EXTARGS]

__all__ = ["init", "backup", "optimize", "make_disk", "make_connection", "make_tuning_keywords",
           "make_tune_request", "make_sys_info"]

# ==================================================================================================
# Initialize folders
def init(request: PG_TUNE_REQUEST) -> None:
    _logger.info(f"Initializing the {APP_NAME_UPPER} application. Create the two directory structures of "
                 f"{BACKUP_ENTRY_READER_DIR} and {SUGGESTION_ENTRY_READER_DIR}")
    os.makedirs(BACKUP_ENTRY_READER_DIR, mode=0o640, exist_ok=True)
    os.makedirs(SUGGESTION_ENTRY_READER_DIR, mode=0o640, exist_ok=True)
    return None

# ==================================================================================================
# Trigger backup to rollback if incident
def _os_backup(request: PG_TUNE_REQUEST, readme_filestream, current_datetime: datetime):
    if not request.options.enable_os_backup:
        return None

    # Backup the sysctl parameters
    _logger.info("Backup the OS and hardware settings.")
    readme_filestream.write(f"# OS & Hardware Backup: {request.options.enable_os_backup}\n")
    sysctl_filepath = os.path.join(BACKUP_ENTRY_READER_DIR, f"sysctl_{current_datetime}.bkp")
    try:
        with open(sysctl_filepath, "w") as sysctl_stream:
            sysctl_stream.write("[SYSCTL] # Remove this line before apply backward\n")
            subprocess.run(["sysctl", "-a"], stdout=sysctl_stream, check=True)
            readme_filestream.write(f"# [OK] The sysctl parameters are backup: {sysctl_filepath}.\n")
    except subprocess.CalledProcessError as e:
        readme_filestream.write(f"# [ERROR] The sysctl parameters are not backup: {sysctl_filepath}\n")
        _logger.error(f"Failed to execute sysctl: {e}")

    # Backup the hardware settings
    if sys.platform == "linux":
        _logger.info("Backup the hardware settings is possible on Linux server.")
        hardware_filepath = os.path.join(BACKUP_ENTRY_READER_DIR, f"hardware_{current_datetime}.bkp")
        hardware_commands = {
            "CPU": ["lscpu", "--json"],
            "BLOCK_DEVICES": ["lsblk", "-f", "-m", "--json"],
            "MEMORY": ["free", "-m"],
            "MEMORY_DETAIL": ["cat", "/proc/meminfo"],

            "MOUNTPOINTS": ["df", "-hT", "-x", "tmpfs", "-x", "devtmpfs"],
            "VIRTIO_DEVICES": ["lsblk", "--virtio", "--pairs", "--paths", "--json"],
            "NVME_DEVICES": ["lsblk", "--nvme", "--pairs", "--paths", "--json"],
            "SCSI_DEVICES": ["lsblk", "--scsi", "--pairs", "--paths", "--json"],
            "DEVICES": ["lshw", "-notime", "-sanitize", "-json"],
        }  # Linux-specific commands
        with open(hardware_filepath, "w") as hardware:
            failed_hardware = False
            for key, value in hardware_commands.items():
                hardware.write(f"[{key.strip().replace(' ', '_').upper()}]\n")
                try:
                    subprocess.run(value, stdout=hardware, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    _logger.error(f"Failed to backup hardware settings: {e}")
                    readme_filestream.write(f"# [ERROR] The hardware settings are NOT backup: "
                                            f"{hardware_filepath}\n")
                    failed_hardware = True
                hardware.write("\n")
            if not failed_hardware:
                readme_filestream.write(f"# [OK] The hardware settings are backup: {hardware_filepath}\n")

    else:
        _logger.warning("Backup the hardware settings is not possible on non-Linux platform.")
        readme_filestream.write("# [WARNING] The hardware settings are not backup: Not supported platform.\n")
    return None

def _db_backup(request: PG_TUNE_REQUEST, readme_filestream, current_datetime: datetime):
    if not request.options.enable_pgconf_db_backup:
        return None

    if request.options.pgconf_os_backup_filepath is not None:
        _logger.info("Backup the PostgreSQL configuration file.")
        readme_filestream.write(f"# PostgreSQL Config File: {request.options.pgconf_os_backup_filepath}\n")
        pgconf_filepath: str = os.path.join(BACKUP_ENTRY_READER_DIR, f"postgresql_{current_datetime}.bkp")
        try:
            shutil.copy2(request.options.pgconf_os_backup_filepath, pgconf_filepath)
            readme_filestream.write(f"# [OK] The PostgreSQL configuration file is backup: {pgconf_filepath}.\n")
        except Exception as e:
            readme_filestream.write(f"# [ERROR] The PostgreSQL configuration file is NOT backup {pgconf_filepath}\n")
            _logger.error(f"Failed to backup the PostgreSQL configuration file: {e}")


    _logger.info("Backup the PostgreSQL settings.")
    readme_filestream.write(f"# PostgreSQL Database Backup: {request.options.enable_pgconf_db_backup}\n")
    pg_settings_filepath = os.path.join(BACKUP_ENTRY_READER_DIR, f"pg_settings_{current_datetime}.json")
    try:
        with psycopg.connect(request.connection.dsn(), row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                query = "SELECT name, setting, unit, vartype, min_val, max_val, pending_restart FROM pg_settings"
                with open(pg_settings_filepath, "w") as json_file:
                    json.dump(cur.execute(query).fetchall(), json_file, indent=4)
                readme_filestream.write(f"# [OK] The pg_settings table is backup: {pg_settings_filepath}.\n")
    except Exception as e:
        readme_filestream.write(f"# [ERROR] The pg_settings table is NOT backup: {pg_settings_filepath}\n")
        _logger.error(f"Failed to backup pg_settings: {e}")
    return None

def backup(request: PG_TUNE_REQUEST, pgtuner_env_file: str | None = "~/.env",
           pgtuner_env_override: bool = False ):
    _logger.info(f"Start backup the system based on generated request.")
    if pgtuner_env_file is not None:
        assert isinstance(pgtuner_env_file, str), "The pgtuner_env_file must be a string."
        assert isinstance(pgtuner_env_override, bool), "The pgtuner_env_override must be a boolean."
        _logger.debug(f"Loading the environment variables from the file: {pgtuner_env_file} "
                      f"(override={pgtuner_env_override}).")
        load_dotenv(dotenv_path=pgtuner_env_file, override=pgtuner_env_override, verbose=True)

    current_datetime = datetime.now(tz=_utc_tz)
    backup_file_format = BACKUP_FILE_FORMAT.replace("*", current_datetime.strftime(DATETIME_PATTERN_FOR_FILENAME))
    backup_filepath: str = os.path.join(BACKUP_ENTRY_READER_DIR, backup_file_format)
    with open(backup_filepath, "w") as readme_filestream:
        readme_filestream.write(f"# PostgreSQL Tuner Profile - Datetime: {current_datetime}\n")
        readme_filestream.write(f"# Generated by PostgreSQL {APP_NAME_UPPER} - Version {__VERSION__}\n")
        readme_filestream.write(f"# OS Managed: {request.options.is_os_user_managed}\n")

        _os_backup(request, readme_filestream, current_datetime)

        # Backup the PostgreSQL configuration file
        _db_backup(request, readme_filestream, current_datetime)

        # Display tuning options
        readme_filestream.write(f"# Your tuning options: {pformat(request.options)}\n")
        readme_filestream.write(f"# Your tuning keyword options: {pformat(request.options.tuning_kwargs)}\n")
        readme_filestream.write(f"# OS for DB Disk: {pformat(request.options.os_db_spec)}\n")
        readme_filestream.write(f"# Data Index Disk: {pformat(request.options.data_index_spec)}\n")
        readme_filestream.write(f"# WAL Disk: {pformat(request.options.wal_spec)}\n")
        readme_filestream.write(f"# DB Log Disk: {pformat(request.options.db_log_spec)}\n")
        readme_filestream.write(f"# Connection String: {pformat(request.connection)}\n")
        readme_filestream.write(f"# Connection DSN: {request.connection.dsn}\n")

    return None


# ==================================================================================================
def _tune_sysctl(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    if not request.options.is_os_user_managed:
        _logger.warning("No tuning is found for the sysctl-based parameters.")
        return None

    found_tuning: bool = False
    dt_start = datetime.now(tz=_utc_tz)
    if request.options.enable_sysctl_general_tuning:
        _logger.info("Start general tuning on the sysctl-based parameters.")
        from src.tuner.profile.gtune_common_kernel_sysctl import KERNEL_SYSCTL_PROFILE
        sysctl_tuner = GeneralTuner(target='kernel', tune_type='sysctl', items=KERNEL_SYSCTL_PROFILE,
                                    ignore_source_result=True, ignore_optim_if_not_found_in_source=True)
        sysctl_tuner.optimize(request=request, sys_info=sys_info)
        found_tuning = True

    if request.options.enable_sysctl_correction_tuning:
        pass

    if not found_tuning:
        _logger.warning("No tuning is found for the sysctl-based parameters.")
        return None
    dt_end = datetime.now(tz=_utc_tz)

    _logger.info(f"General tuning on the sysctl-based parameters is completed. Start writing the tuning result.")
    filepath = f'kernel_sysctl_{dt_start.strftime(DATETIME_PATTERN_FOR_FILENAME)}.conf'
    with open(os.path.join(SUGGESTION_ENTRY_READER_DIR, filepath), 'w') as f:
        f.write(f"# {APP_NAME_UPPER}: Tuning started at {dt_start} --> Completed at {dt_end}\n")
        f.write(f'# HOWTO: Apply the tuning result by copy the file under the /etc/sysctl.d/* directory.\n')
        f.write(f'# DISCLAIMER: The tuning result is based on the {APP_NAME_UPPER} application, and there is no '
                f'\n# guarantee that the tuning result is the best for your system. Please consult with your system '
                f'\n# administrator or the system engineer or DBA before applying the tuning result.\n')
        output_if_difference_only, include_comment = request.output_if_difference_only, request.include_comment
        for scope, t_item in sys_info.outcome['kernel']['sysctl'].items():
            f.write(f'##  =================================== SCOPE: {scope} =================================== \n')
            for key, item in t_item.items():
                f.write(item.out(output_if_difference_only, include_comment))
                f.write('\n' * (2 if include_comment else 1))
            f.write('\n\n' * (2 if include_comment else 1))

    _logger.info(f"General tuning on the sysctl-based parameters is completed. "
                 f"Duration: {(dt_end - dt_start).total_seconds()} seconds.")
    return None


def _load_pgdb_profile(pgsql_version: str):
    try:
        match pgsql_version:
            case '13':
                from src.tuner.profile.gtune_13 import DB_CONFIG_PROFILE
                return DB_CONFIG_PROFILE
            case '14':
                from src.tuner.profile.gtune_14 import DB_CONFIG_PROFILE
                return DB_CONFIG_PROFILE
            case '15':
                from src.tuner.profile.gtune_15 import DB_CONFIG_PROFILE
                return DB_CONFIG_PROFILE
            case '16':
                from src.tuner.profile.gtune_16 import DB_CONFIG_PROFILE
                return DB_CONFIG_PROFILE
            case '17':
                from src.tuner.profile.gtune_17 import DB_CONFIG_PROFILE
                return DB_CONFIG_PROFILE
            case _:
                _logger.warning(f"Unsupported PostgreSQL version: {pgsql_version} -> Fallback to the common profile.")
                from src.tuner.profile.gtune_common_db_config import DB_CONFIG_PROFILE
                return DB_CONFIG_PROFILE
    except ImportError as e:
        _logger.error(f"Failed to import the PostgreSQL profile: {e}")
        _logger.warning(f"Unsupported PostgreSQL version: {pgsql_version} -> Fallback to the common profile.")
        from src.tuner.profile.gtune_common_db_config import DB_CONFIG_PROFILE
        return DB_CONFIG_PROFILE


def _tune_pgdb(request: PG_TUNE_REQUEST, sys_info: PG_SYS_SHARED_INFO):
    found_tuning: bool = False
    dt_start = datetime.now(tz=_utc_tz)
    if request.options.enable_database_general_tuning:
        _logger.info("Start general tuning on the PostgreSQL database settings.")
        db_config_profile = _load_pgdb_profile(request.options.pgsql_version)
        dbconf_tuner = GeneralTuner(target='database', tune_type='config', items=db_config_profile,
                                    ignore_source_result=True, ignore_optim_if_not_found_in_source=True)
        dbconf_tuner.optimize(request=request, sys_info=sys_info)
        found_tuning = True

    if request.options.enable_database_correction_tuning:
        correction_tune(request, sys_info)
        found_tuning = True

    if not found_tuning:
        _logger.warning("No tuning is found for the database-based parameters.")
        return None
    dt_end = datetime.now(tz=_utc_tz)

    _logger.info(f"Tuning on the PostgreSQL database settings is completed. Start writing the tuning result.")
    filepath = f'database_config_{dt_start.strftime(DATETIME_PATTERN_FOR_FILENAME)}.conf'
    with open(os.path.join(SUGGESTION_ENTRY_READER_DIR, filepath), 'w') as f:
        f.write(f"# {APP_NAME_UPPER}: Tuning started at {dt_start} --> Completed at {dt_end}\n")
        f.write(f'# HOWTO: Apply the tuning result by copy the file under the /etc/postgresql/* directory or inside '
                f'\n# the $PGDATA/conf/* or $PGDATA/* directory depending on how you start the PostgreSQL server.\n')
        f.write(f'# DISCLAIMER: The tuning result is based on the {APP_NAME_UPPER} application, and there is no '
                f'\n# guarantee that the tuning result is the best for your system. Please consult with your system '
                f'\n# administrator or the system engineer or DBA before applying the tuning result.\n')
        output_if_difference_only, include_comment = request.output_if_difference_only, request.include_comment
        for scope, t_item in sys_info.outcome['database']['config'].items():
            f.write(f'##  =================================== SCOPE: {scope} =================================== \n')
            for key, item in t_item.items():
                f.write(item.out(output_if_difference_only, include_comment))
                f.write('\n' * (2 if include_comment else 1))
            f.write('\n\n' * (2 if include_comment else 1))

    _logger.info(f"General tuning on the PostgreSQL database settings is completed. "
                 f"Duration: {(dt_end - dt_start).total_seconds()} seconds.")
    return None


def optimize(request: PG_TUNE_REQUEST, env_file: str | None = "~/.env", env_override: bool = False,
             **kwargs_sys_info):
    dt_start = datetime.now(tz=_utc_tz)
    _logger.info(f"Start tuning the system based on generated request.")
    if env_file is not None:
        assert isinstance(env_file, str), "The env_file must be a string."
        assert isinstance(env_override, bool), "The env_override must be a boolean."
        _logger.debug(f"Loading the environment variables from the file: {env_file} (override={env_override}).")
        load_dotenv(dotenv_path=env_file, override=env_override, verbose=True)
    sys_info = make_sys_info(request, **kwargs_sys_info)

    # [01]: Perform tuning on the sysctl-based parameters if the OS is managed by the user
    _tune_sysctl(request, sys_info)

    # [02]: Perform general tuning on the PostgreSQL configuration file
    _tune_pgdb(request, sys_info)

    dt_end = datetime.now(tz=_utc_tz)
    _logger.info(f"Optimization is completed. Duration: {(dt_end - dt_start).total_seconds()} seconds.")
    return request, sys_info

# ==================================================================================================
# Receive user tuning options
_OS_DB_DISK_STRING_CODE = 'ssdv1'
_DATA_INDEX_DISK_STRING_CODE = 'ssdv2'
_WAL_DISK_STRING_CODE = 'ssdv2'
_DB_LOG_DISK_STRING_CODE = 'hddv1'

def make_disk(disk_string_code_throughput: str = _OS_DB_DISK_STRING_CODE,
              disk_string_code_rand_iops: str = _OS_DB_DISK_STRING_CODE,
              num_disks: PositiveInt = 1,
              read_random_iops_spec: _SIZING | str = None, write_random_iops_spec: _SIZING | str = None,
              random_iops_scale_factor: PositiveFloat = 0.9, read_throughput_spec: _SIZING | str = None,
              write_throughput_spec: _SIZING | str = None, throughput_scale_factor: PositiveFloat = 0.9,
              per_scale_in_raid: PositiveFloat = 0.75) -> PG_DISK_PERF:
    return PG_DISK_PERF(read_random_iops_spec=read_random_iops_spec or disk_string_code_rand_iops,
                        write_random_iops_spec=write_random_iops_spec or disk_string_code_rand_iops,
                        random_iops_scale_factor=random_iops_scale_factor,
                        read_throughput_spec=read_throughput_spec or disk_string_code_throughput,
                        write_throughput_spec=write_throughput_spec or disk_string_code_throughput,
                        throughput_scale_factor=throughput_scale_factor,
                        per_scale_in_raid=per_scale_in_raid, num_disks=num_disks)

def make_tuning_keywords(**kwargs: _SIZING) -> PG_TUNE_USR_KWARGS:
    return PG_TUNE_USR_KWARGS(**kwargs)

def make_connection(
        pg_host: str = GetEnvVar(_HOSTVARS, "localhost", input_message_string="Enter the PostgreSQL host: "),
        pg_port: int = GetEnvVar(_PORTVARS, 5432, env_type_cast_fn=int, input_type_cast_fn=int,
                                 input_message_string="Enter the PostgreSQL port: "),
        pg_username: str = GetEnvVar(_USERVARS, "postgres", input_message_string="Enter the PostgreSQL user: "),
        pg_password: str = GetEnvVar(_PWDVARS, "postgres", input_message_string="Enter the PostgreSQL password: "),
        pg_database: str = GetEnvVar(_DBVARS, "postgres", input_message_string="Enter the PostgreSQL database: "),
        pgc_conn_extargs: str | None = GetEnvVar(_CONNEXTRAVARS, None,
                                                 input_message_string="Enter the PostgreSQL connection extra arguments: ")):

    return PG_CONNECTION(host=pg_host, port=pg_port, user=pg_username, pwd=pg_password, database=pg_database,
                         conn_ext_args=pgc_conn_extargs)

def make_tune_request(
        is_os_user_managed: bool = False, enable_os_backup: bool = True,
        enable_pgconf_os_backup_filepath: str | None = None, enable_pgconf_db_backup: bool = True,
        enable_sysctl_general_tuning: bool = True, enable_sysctl_correction_tuning: bool = False,
        enable_database_general_tuning: bool = True, enable_database_correction_tuning: bool = True,
        pg_db_conn: PG_CONNECTION = make_connection('localhost', 5432, 'postgres',
                                                    'postgres', 'postgres', None),

        ## User-Tuning Profiles
        overall_profile: str = "large", cpu_profile: str = "large", mem_profile: str = "large",
        net_profile: str = "large", disk_profile: str = "large", pgsql_version: str = "17",

        ## Disk Performance
        disk_template: PG_DISK_PERF = make_disk(_DATA_INDEX_DISK_STRING_CODE, _DATA_INDEX_DISK_STRING_CODE),
        os_db_disk: PG_DISK_PERF = make_disk(_OS_DB_DISK_STRING_CODE, _OS_DB_DISK_STRING_CODE),
        data_index_disk: PG_DISK_PERF = make_disk(_DATA_INDEX_DISK_STRING_CODE, _DATA_INDEX_DISK_STRING_CODE),
        wal_disk: PG_DISK_PERF = make_disk(_WAL_DISK_STRING_CODE, _WAL_DISK_STRING_CODE),
        db_log_disk: PG_DISK_PERF = make_disk(_DB_LOG_DISK_STRING_CODE, _DB_LOG_DISK_STRING_CODE),

        ## PostgreSQL Tuning Configuration
        workload_type: PG_WORKLOAD = PG_WORKLOAD.HTAP,
        read_workload: float = 0.8,
        insert_workload_per_write: float = 0.95,
        opt_memory: PG_PROFILE_OPTMODE = PG_PROFILE_OPTMODE.OPTIMUS_PRIME,
        opt_memory_precision: PG_PROFILE_OPTMODE = PG_PROFILE_OPTMODE.SPIDEY,
        bypass_system_reserved_memory: bool = False,
        base_kernel_memory_usage: _SIZING = -1,
        base_monitoring_memory_usage: _SIZING = -1,
        tuning_keywords: PG_TUNE_USR_KWARGS = make_tuning_keywords(),

        ## PostgreSQL Data Integrity
        allow_lost_transaction_during_crash: bool = False,
        max_num_stream_replicas_on_primary: PositiveInt = 0,
        max_num_logical_replicas_on_primary: PositiveInt = 0,
        max_level_backup_tool: str = "pg_basebackup",
        offshore_replication: bool = False,

        ## How to output item
        output_if_difference_only: bool = False,
        include_comment: bool = False,
) -> PG_TUNE_REQUEST:

    options = PG_TUNE_USR_OPTIONS(
        ## Operation Mode
        is_os_user_managed=is_os_user_managed, enable_os_backup=enable_os_backup,
        pgconf_os_backup_filepath=enable_pgconf_os_backup_filepath,
        enable_pgconf_db_backup=enable_pgconf_db_backup,
        enable_sysctl_general_tuning=enable_sysctl_general_tuning,
        enable_sysctl_correction_tuning=enable_sysctl_correction_tuning,
        enable_database_general_tuning=enable_database_general_tuning,
        enable_database_correction_tuning=enable_database_correction_tuning,
        ## User-Tuning Profiles
        overall_profile=overall_profile,
        cpu_profile=cpu_profile,
        mem_profile=mem_profile,
        net_profile=net_profile,
        disk_profile=disk_profile,
        pgsql_version=pgsql_version,
        ## Disk Performance
        os_db_spec=os_db_disk or disk_template, data_index_spec=data_index_disk or disk_template,
        wal_spec=wal_disk or disk_template, db_log_spec=db_log_disk or disk_template,
        ## PostgreSQL Tuning Configuration
        workload_type=workload_type, opt_memory=opt_memory, read_workload=read_workload,
        insert_workload_per_write=insert_workload_per_write, bypass_system_reserved_memory=bypass_system_reserved_memory,
        base_kernel_memory_usage=base_kernel_memory_usage, base_monitoring_memory_usage=base_monitoring_memory_usage,
        tuning_kwargs=tuning_keywords, opt_memory_precision=opt_memory_precision,
        ## PostgreSQL Data Integrity
        allow_lost_transaction_during_crash=allow_lost_transaction_during_crash,
        max_num_stream_replicas_on_primary=max_num_stream_replicas_on_primary,
        max_num_logical_replicas_on_primary=max_num_logical_replicas_on_primary,
        max_level_backup_tool=max_level_backup_tool,
        offshore_replication=offshore_replication
    )
    return PG_TUNE_REQUEST(connection=pg_db_conn, options=options, output_if_difference_only=output_if_difference_only,
                           include_comment=include_comment)


def make_sys_info(request: PG_TUNE_REQUEST, vcpu: int = 4, memory: _SIZING = 16 * Gi,
                  hyperthreading: bool = False) -> PG_SYS_SHARED_INFO:
    sysctl = None
    if request.options.enable_os_backup:
        sysctl_filepath = glob.glob(os.path.join(BACKUP_ENTRY_READER_DIR, "sysctl_*.bkp"))
        sysctl_filepath.sort(reverse=True)  # Get the most recent backup
        if sysctl_filepath:
            with open(sysctl_filepath[0], 'r') as f:
                sysctl = toml.load(f)['SYSCTL']

    # We not support the database-config backup yet
    vm_snapshot = SERVER_SNAPSHOT.sample(vcpu=vcpu, memory=memory, hyperthreading=hyperthreading)
    if request.options.is_os_user_managed:
        _logger.warning("The OS is managed by the user. The system snapshot is not available.")
        vm_snapshot = SERVER_SNAPSHOT.take()

    return PG_SYS_SHARED_INFO(vm_snapshot=vm_snapshot, backup={'kernel-sysctl': sysctl})