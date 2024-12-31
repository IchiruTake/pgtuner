from typing import Any

from pydantic import BaseModel, Field, ByteSize
from pydantic.types import PositiveFloat, PositiveInt

from src.static.c_toml import LoadAppToml
from src.static.vars import Gi, Mi, APP_NAME_UPPER, DEFAULT_INSTRUCTION_PROFILE, SUPPORTED_POSTGRES_VERSIONS
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.keywords import PG_TUNE_USR_KWARGS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.data.utils import FactoryForPydanticWithUserFn as PydanticFact
import logging

__all__ = ["PG_TUNE_USR_OPTIONS", 'backup_description']
_PG_OPT_KEYS = PG_PROFILE_OPTMODE.__members__.values()
_logger = logging.getLogger(APP_NAME_UPPER)
_TomlProfileData = list(LoadAppToml()['profile'].keys())
assert DEFAULT_INSTRUCTION_PROFILE in _TomlProfileData, "The default instruction profile must be in the profile data."

# =============================================================================
# Ask user which tuning options they choose for
def backup_description() -> dict[str, tuple[str, int]]:
    return {
        'disk_snapshot': ('Backup by Disk Snapshot', 0),
        'pg_dump': ('pg_dump/pg_dumpall: Textual backup', 1),
        'pg_basebackup': ('pg_basebackup [--incremental] or streaming replication (byte-capture change): Byte-level backup', 2),
        'pg_logical': ('pg_logical and alike: Logical replication', 3),
    }

def _backup_translation(value: str) -> str:
    if value.strip() not in backup_description():
        raise ValueError(f"The backup tool {value} is not in the supported list.")
    return value.strip()

class PG_TUNE_USR_OPTIONS(BaseModel):
    # The basic profile for the system tuning for profile-guided tuning
    overall_profile: str = (
        Field(default_factory=PydanticFact(f"Enter the overall profile: ", user_fn=str,
                                           default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The overall profile to be used for tuning')
    )
    cpu_profile: str = (
        Field(default_factory=PydanticFact(f"Enter the CPU profile: ", user_fn=str,
                                           default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The CPU profile to be used for profile-based tuning')
    )
    mem_profile: str = (
        Field(default_factory=PydanticFact(f"Enter the Memory profile: ", user_fn=str,
                                           default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The Memory profile to be used for profile-based tuning')
    )
    net_profile: str = (
        Field(default_factory=PydanticFact(f"Enter the Network profile: ", user_fn=str,
                                           default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The Network profile to be used for profile-based tuning')
    )
    disk_profile: str = (
        Field(default_factory=PydanticFact(f"Enter the Disk profile: ", user_fn=str,
                                           default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The Disk profile to be used for profile-based tuning')
    )
    pgsql_version: str = (
        Field(default_factory=PydanticFact("Enter the PostgreSQL version: ", user_fn=str, default_value='13'),
              description="The PostgreSQL version to be used for tuning")
    )

    # Disk options for data partitions
    os_db_spec: PG_DISK_PERF
    data_index_spec: PG_DISK_PERF
    wal_spec: PG_DISK_PERF
    db_log_spec: PG_DISK_PERF


    # Data Integrity, Transaction, Crash Recovery, and Replication
    allow_lost_transaction_during_crash: bool = (
        Field(default=True,
              description="Default to False would allow the lost transaction during the crash recovery. This is "
                          "not a recommended behaviour and may lead to data loss."
              )
    )
    max_num_stream_replicas_on_primary: int = (
        Field(default=0, ge=0, le=32,
              description="The maximum number of streaming replicas for the PostgreSQL primary server. The supported "
                          "range is [0, 32], default is 0."
              )
    )
    max_num_logical_replicas_on_primary: int = (
        Field(default=0, ge=0, le=32,
              description="The maximum number of logical replicas for the PostgreSQL primary server. The supported "
                          "range is [0, 32], default is 0."
              )
    )
    max_level_backup_tool: str = (
        Field(default_factory=PydanticFact(f"Enter the backup tool {tuple(backup_description().keys())}: ",
                                           user_fn=_backup_translation, default_value='pg_basebackup'),
              description=f"The backup tool to be used for the PostgreSQL server (3 modes are supported). "
                          f"Default is pg_basebackup."
              )
    )
    offshore_replication: bool = (
        Field(default=False,
              description="If set it to True, you are wishing to have an geo-replicated replicas in the offshore "
                          "country or continent."
              )
    )

    # These are for the database tuning options
    workload_type: PG_WORKLOAD = (
        Field(default_factory=PydanticFact(f"Enter the PostgreSQL workload type as {_PG_OPT_KEYS}): ",
                                           user_fn=PG_WORKLOAD, default_value=PG_WORKLOAD.HTAP),
              description="The PostgreSQL workload type. This would affect the tuning options and the risk level.")
    )
    read_workload: PositiveFloat = (
        Field(default_factory=PydanticFact("Enter the read workload ratio from 0 to 1: ", user_fn=float,
                                           default_value=0.8),
              description="The PostgreSQL read workload in percentage. Default to 0.8 (80%)",
              ge=0, le=1, strict=False, allow_inf_nan=False)
    )
    insert_workload_per_write: PositiveFloat = (
        Field(default_factory=PydanticFact("Enter the insert workload per write ratio from 0 to 1: ",
                                           user_fn=float, default_value=0.95),
              description="The PostgreSQL insert workload of write. Default to 0.95 (95%)",
              ge=0, le=1, strict=False, allow_inf_nan=False)
    )

    opt_memory: PG_PROFILE_OPTMODE = (
        Field(default_factory=PydanticFact(f"Enter the PostgreSQL memory optimization profile as {_PG_OPT_KEYS}: ",
                                           user_fn=PG_PROFILE_OPTMODE, default_value=PG_PROFILE_OPTMODE.OPTIMUS_PRIME),
              description="The PostgreSQL optimization mode on workload type to tune overall memory usage by allowing "
                          "total disk cache in buffer (shared_buffer + effective_cache_size).")
    )
    opt_memory_precision: PG_PROFILE_OPTMODE = (
        Field(default_factory=PydanticFact(f"Enter the PostgreSQL memory precision profile as {_PG_OPT_KEYS}: ",
                                           user_fn=PG_PROFILE_OPTMODE, default_value=PG_PROFILE_OPTMODE.SPIDEY),
              description="If not none, it would proceed the extra tuning to increase the memory buffer usage to "
                          "reach to your expectation (shared_buffers, work_mem, temp_buffer, wal_buffer if wal_level "
                          "is set to replica nad higher). Set to SPIDEY (default) use the worst case as the condition; "
                          "OPTIMUS_PRIME take the average between normal and worst case as the stopping condition; "
                          "PRIMORDIAL take the normal case as the stopping condition.")
    )
    tuning_kwargs: PG_TUNE_USR_KWARGS


    # ========================================================================
    # This is used for analyzing the memory available.
    bypass_system_reserved_memory: bool = (
        Field(default=False, frozen=False,
              description="Default to False meant that the application assumes the server memory reported by the psutil "
                          "library is incorrect and has hidden system reserved memory. Normally the system reserved "
                          "around 64 - 128 MiB and this would be added up into the total memory that the server have."
                          "If the :attr:`is_os_user_managed` is False, this value would be set to True. This option "
                          "may not bring large memory safeguard when the server memory is larger than 2 to 4 GiB when"
                          "set to True, and may not be correctly represented the current server."
              )
    )
    base_kernel_memory_usage: ByteSize | int = (
        Field(default_factory=PydanticFact("Enter the kernel memory when idle (in MiB): ",
                                           user_fn=None, default_value=-1),
              description="The PostgreSQL base kernel memory during when idle. This value is used to estimate the "
                          "impact during memory-related tuning configuration and server as a safeguard against memory "
                          "overflow. Default value is -1 to meant that this application would assume the kernel memory "
                          "is taken 768 MiB (3/4 of 1 GiB) during idle and 0 MiB if the system is not user-managed. "
                          "Maximum allowed value is 8 GiB and the input must be a multiple of 2 MiB. The 768 MiB is "
                          "taken from Ubuntu 24.10 during idle.",
              ge=-1, le=8 * Gi, frozen=False, allow_inf_nan=False)
    )

    base_monitoring_memory_usage: ByteSize | int = (
        Field(default_factory=PydanticFact("Enter the monitoring memory usage (in MiB): ",
                                           user_fn=None, default_value=-1),
              description="The PostgreSQL peak used monitoring memory (format 1 GiB = 1024 MiB). This value is used to "
                          "estimate the impact during memory-related tuning configuration and server as a safeguard "
                          "against memory overflow. For default OS management by user, the monitoring agent would be "
                          "installed on that machine and consume around 128 - 512 MiB (default) to monitor both OS "
                          "and database. Maximum allowed value is 4 GiB and the input must be a default of 2 MiB. "
                          "Default value is -1 to meant that this application would assume the monitoring would take"
                          "the database server (from database query usage) 64 MiB and 512 MiB (if agent is installed)."
                          "Note that this value is not limited to the monitoring only, but also antivirus, ...",
              ge=-1, le=4 * Gi, frozen=False, allow_inf_nan=False)
    )

    # ========================================================================
    # We may not have this at end-user on the website
    # Questions of System Management and Operation to be done
    is_os_user_managed: bool = (
        Field(default=True, frozen=True,
              description="Default to True would assume that the server is managed by the user under the form of bare "
                          "metal or virtual machine or cloud instance (VM). If you are using a managed service, "
                          "cloud-provided PaaS database (DBaaS), self-hosted cluster/container, or the host is WSL, "
                          "this value must be set to False. Set this to False means that enable_os_backup, "
                          "enable_sysctl_general_tuning, enable_pgconf_os_backup, and enable_sysctl_correction_tuning "
                          "would be disabled."
              )
    )
    enable_os_backup: bool = (
        Field(default=True, frozen=False,
              description="Default to True would enable this to backup the system configuration files. This is a "
                          "safety measure to backup the system configuration files before tuning the system kernel "
                          "parameters (sysctl). This flag is only valid if is_os_user_managed is True."
              )
    )
    pgconf_os_backup_filepath: str | None = (
        Field(default=None, frozen=False,
              description="Default to None. If set to a valid filepath, this option would enable the backup the assumed"
                          "PostgreSQL configuration files. This is a safety measure to backup the PostgreSQL "
                          "configuration files before tuning the PostgreSQL parameters. While it is OK to enable this "
                          "option, our application would supply a full-spec configuration that you can re-trigger the "
                          "running daemon with the new configuration file."
              )
    )
    enable_pgconf_db_backup: bool = (
        Field(default=True, frozen=False,
              description="Default to True would enable this to backup the PostgreSQL database files. This is a "
                          "safety measure to backup the PostgreSQL configuration files by login into the database "
                          "and capture all settings in the pg_catalog.pg_settings table before tuning the PostgreSQL "
                          "parameters. This flag is not impacted by the is_os_user_managed flag."
              )
    )
    enable_sysctl_general_tuning: bool = (
        Field(default=True, frozen=False,
              description="Default to True would enable this to tune the system kernel parameters (sysctl). If you "
                          "host your database on a managed service or container, this value must be set to False. "
                          "This flag is only valid if is_os_user_managed is True."
              )
    )
    enable_sysctl_correction_tuning: bool = (
        Field(default=False, frozen=False,
              description="Default to False. Set to True would enable this to revise the system kernel parameters "
                          "(sysctl) to more fit with your server. Currently, the improvement of second OS tuning is"
                          "in consideration and may not bring large improvement. This flag is only valid if "
                          "is_os_user_managed is True."
              )
    )
    enable_database_general_tuning: bool = (
        Field(default=True, frozen=False,
              description="Default to True would enable this to tune the PostgreSQL database parameters. "
              )
    )
    enable_database_correction_tuning: bool = (
        Field(default=True, frozen=False,
              description="Default to True would enable this to revise the PostgreSQL database parameters to more fit "
                          "with your server. Currently, the improvement of second database is implemented."
              )
    )

    # ========================================================================
    # Revert some invalid options as described in :attr:`is_os_user_managed`
    def model_post_init(self, __context: Any) -> None:
        if not self.is_os_user_managed:
            _logger.debug("The system is not user-managed, revert some invalid options.")
            self.bypass_system_reserved_memory = True       # Enforce to True for assumption of correct memory server
            self.enable_os_backup = False
            self.enable_pgconf_db_backup = False
            self.enable_sysctl_general_tuning = False
            self.enable_sysctl_correction_tuning = False

        if not self.enable_sysctl_general_tuning:
            self.enable_sysctl_correction_tuning = False
        if not self.enable_database_general_tuning:
            self.enable_database_correction_tuning = False

        # Set back memory usage in non user-managed system
        if self.base_monitoring_memory_usage in (-1, 0):
            if self.is_os_user_managed:
                self.base_monitoring_memory_usage = ByteSize(256 * Mi)
            else:
                self.base_monitoring_memory_usage = ByteSize(64 * Mi)
            _logger.debug(f"Set the monitoring memory usage to {self.base_monitoring_memory_usage.human_readable(separator=' ')}")
        if self.base_kernel_memory_usage in (-1, 0):
            if self.is_os_user_managed:
                self.base_kernel_memory_usage = ByteSize(768 * Mi)
            else:
                self.base_kernel_memory_usage = ByteSize(64 * Mi)
            _logger.debug(f"Set the kernel memory usage to {self.base_kernel_memory_usage.human_readable(separator=' ')}")

        # Check the database version is in the supported version
        if self.pgsql_version not in SUPPORTED_POSTGRES_VERSIONS:
            _logger.warning(f"The PostgreSQL version {self.pgsql_version} is not in the supported version list. "
                            f"Please ensure that the version is correct and the tuning may not be accurate. "
                            f"Forcing the version to the common version (which is the shared configuration across"
                            f"all supported versions).")
            self.pgsql_version = 'common'

        # Set the profile for non-custom profile
        if self.overall_profile != 'custom' and self.overall_profile not in _TomlProfileData:
            self.overall_profile = DEFAULT_INSTRUCTION_PROFILE
        if self.overall_profile == 'custom':
            self.cpu_profile = self.cpu_profile or self.overall_profile
            self.mem_profile = self.mem_profile or self.overall_profile
            self.net_profile = self.net_profile or self.overall_profile
            self.disk_profile = self.disk_profile or self.overall_profile
        else:
            self.cpu_profile = self.cpu_profile or DEFAULT_INSTRUCTION_PROFILE
            self.mem_profile = self.mem_profile or DEFAULT_INSTRUCTION_PROFILE
            self.net_profile = self.net_profile or DEFAULT_INSTRUCTION_PROFILE
            self.disk_profile = self.disk_profile or DEFAULT_INSTRUCTION_PROFILE

        assert self.overall_profile in _TomlProfileData, "The overall profile must be in the profile data."
        assert self.cpu_profile in _TomlProfileData, "The CPU profile must be in the profile data."
        assert self.mem_profile in _TomlProfileData, "The Memory profile must be in the profile data."
        assert self.net_profile in _TomlProfileData, "The Network profile must be in the profile data."
        assert self.disk_profile in _TomlProfileData, "The Disk profile must be in the profile data."

        return None