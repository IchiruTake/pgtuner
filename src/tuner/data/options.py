import logging
from functools import cached_property, partial
from typing import Any, Annotated, Literal

from pydantic import BaseModel, Field, ByteSize, AfterValidator
from pydantic.types import PositiveInt

from src.static.vars import Gi, Mi, APP_NAME_UPPER, SUPPORTED_POSTGRES_VERSIONS
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.keywords import PG_TUNE_USR_KWARGS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.sizing import PG_SIZING
from src.tuner.data.utils import FactoryForPydanticWithUserFn as PydanticFact
from src.tuner.data.workload import PG_WORKLOAD
from src.utils.pydantic_utils import bytesize_to_hr

__all__ = ['PG_TUNE_USR_OPTIONS', 'backup_description']
_logger = logging.getLogger(APP_NAME_UPPER)


# =============================================================================
# Ask user which tuning options they choose for
def backup_description() -> dict[str, tuple[str, int]]:
    return {
        'disk_snapshot': ('Backup by Disk Snapshot', 0),
        'pg_dump': ('pg_dump/pg_dumpall: Textual backup', 1),
        'pg_basebackup': ('pg_basebackup [--incremental] or streaming replication '
                          '(byte-capture change): Byte-level backup', 2),
        'pg_logical': ('pg_logical and alike: Logical replication', 3),
    }


def _backup_translation(value: str) -> str:
    if value.strip() not in backup_description():
        raise ValueError(f'The backup tool {value} is not in the supported list.')
    return value.strip()


# =============================================================================
# Ask user which tuning options they choose for
def _allowed_values(v, values: list[str] | tuple[str, ...]):
    # https://stackoverflow.com/questions/61238502/how-to-require-predefined-string-values-in-python-pydantic-basemodels
    # Since Literal does not support dynamic values, we have to use this method
    assert v in values, f'Invalid value {v} for the tuning options. The allowed values are {values}'
    return v

_backup_items = list(backup_description().keys())
_PG_WORKLOAD_KEYS = PG_WORKLOAD.__members__.values()
_PG_OPT_KEYS = PG_PROFILE_OPTMODE.__members__.values()
_PG_OS_KEYS = ['linux', 'windows', 'macos', 'containerd', 'PaaS']

_allowed_opt_mode = partial(_allowed_values, values=_PG_OPT_KEYS)
_allowed_workload = partial(_allowed_values, values=_PG_WORKLOAD_KEYS)
_allowed_profile = partial(_allowed_values, values=['mini', 'medium', 'large', 'mall', 'bigt'])
_allowed_postgres_version = partial(_allowed_values, values=list(SUPPORTED_POSTGRES_VERSIONS) + ['latest', 'stable'])
_allowed_backup_tool = partial(_allowed_values, values=list(backup_description().keys()))
_allowed_os = partial(_allowed_values, values=_PG_OS_KEYS)


# =============================================================================
class PG_TUNE_USR_OPTIONS(BaseModel):
    # The basic profile for the system tuning for profile-guided tuning
    workload_profile: Annotated[
        PG_SIZING,
        Field(default_factory=PydanticFact(f'Enter the workload profile as mini, medium, large, mall, bigt: ',
                                           user_fn=PG_SIZING, default_value=PG_SIZING.LARGE),
              description='The workload profile to be used for tuning')
    ]
    cpu_profile: Annotated[
        PG_SIZING,
        Field(default_factory=PydanticFact(f'Enter the CPU profile as mini, medium, large, mall, bigt: ',
                                           user_fn=PG_SIZING, default_value=PG_SIZING.LARGE),
              description='The CPU profile to be used for profile-based tuning')
    ]
    mem_profile: Annotated[
        PG_SIZING,
        Field(default_factory=PydanticFact(f'Enter the Memory profile as mini, medium, large, mall, bigt: ',
                                           user_fn=PG_SIZING, default_value=PG_SIZING.LARGE),
              description='The memory profile to be used for profile-based tuning')
    ]
    disk_profile: Annotated[
        PG_SIZING,
        Field(default_factory=PydanticFact(f'Enter the Disk profile as mini, medium, large, mall, bigt: ',
                                           user_fn=PG_SIZING, default_value=PG_SIZING.LARGE),
              description='The disk profile to be used for profile-based tuning')
    ]
    net_profile: Annotated[
        PG_SIZING,
        Field(default_factory=PydanticFact(f'Enter the Network profile as mini, medium, large, mall, bigt: ',
                                           user_fn=PG_SIZING, default_value=PG_SIZING.LARGE),
              description='The network profile to be used for profile-based tuning')
    ]
    pgsql_version: Annotated[
        str, AfterValidator(_allowed_postgres_version),
        Field(default_factory=PydanticFact('Enter the PostgreSQL version: ', user_fn=str, default_value='17'),
              description='The PostgreSQL version to be used for tuning')
    ]
    # Disk options for data partitions
    os_db_spec: Annotated[
        PG_DISK_PERF | None,
        Field(default=None,
              description='The disk specification for the operating system and database (This is not used)')
    ]
    data_index_spec: Annotated[
        PG_DISK_PERF,
        Field(description='The disk specification for the data and index partition.')
    ]
    wal_spec: Annotated[
        PG_DISK_PERF,
        Field(description='The disk specification for the WAL partition.')
    ]
    db_log_spec: Annotated[
        PG_DISK_PERF | None,
        Field(default=None,
              description='The disk specification for the database logging and backup (This is not used)')
    ]

    # Data Integrity, Transaction, Crash Recovery, and Replication
    max_backup_replication_tool: Annotated[
        str, AfterValidator(_allowed_backup_tool),
        Field(default_factory=PydanticFact(f'Enter the backup tool {_backup_items}: ',
                                           user_fn=str, default_value='pg_basebackup'),
              description=f'The backup tool to be used for the PostgreSQL server (3 modes are supported). Default '
                          f'is pg_basebackup. This argument is also helps to set the wal_level variable. The level of '
                          f'wal_level can be determined by maximum of achieved replication tool and number of replicas '
                          f'but would not impact on the data/transaction integrity choice.',
              )
    ]
    opt_transaction_lost: Annotated[
        PG_PROFILE_OPTMODE,
        Field(default_factory=PydanticFact(f'Enter the PostgreSQL transaction loss profile as {_PG_OPT_KEYS}: ',
                                           user_fn=PG_PROFILE_OPTMODE, default_value=PG_PROFILE_OPTMODE.NONE),
              description='The PostgreSQL mode for allow the transaction loss to tune the transaction loss recovery '
                          'mechanism. If you are working in on the mission-critical system where the atomicity and '
                          'consistency are the top priorities, then set to NONE (default) to not allow the lost '
                          'transaction loss by change the synchronous_commit. Set to SPIDEY would convert the '
                          'synchronous_commit to off, local, or remote_write (depending on the wal_level and number '
                          'of replicas). Set to OPTIMUS_PRIME would convert the full_page_writes to off. Set to '
                          'PRIMORDIAL would convert the fsync to off. Use with your own risk and caution. ',
              )
    ]
    opt_wal_buffers: Annotated[
        PG_PROFILE_OPTMODE,
        Field(default_factory=PydanticFact(f'Enter the PostgreSQL WAL buffers profile as {_PG_OPT_KEYS}: ',
                                           user_fn=PG_PROFILE_OPTMODE, default_value=PG_PROFILE_OPTMODE.SPIDEY),
              description='The optimization mode for the WAL buffers to ensure the WAL buffers in the correction '
                          'tuning phase during outage lose data less than the maximum time of lossy transaction. '
                          'Set to PRIMORDIAL ensure 2x WAL buffers can be written to disk in our estimation. Similarly '
                          'with OPTIMUS_PRIME at 1.5x and SPIDEY at 1.0x. Set to NONE would not tune the WAL setting. '
                          'Only set to NONE when you feel the maximum of data integrity is not required integrity. '
                          'Otherwise, this would be enforced to SPIDEY.',
              )
    ]
    repurpose_wal_buffers: Annotated[
        bool,
        Field(default=True,
              description='Set to True (default) would take the difference of WAL buffers to be used in temp_buffers '
                          'and work_mem, by increasing its pool size. This would be conducted after the final memory '
                          'tuning. The reason not to re-purpose into the shared_buffers is that the shared_buffers is '
                          'usually persistent when the database is online. This argument is only valid when the '
                          'WAL buffers is reduced because your disk cannot handle between transaction loss when the '
                          'opt_wal_buffers is different than NONE.',
              )
    ]
    max_time_transaction_loss_allow_in_millisecond: Annotated[
        PositiveInt,
        Field(default=650, ge=1, le=10000,
              description='The maximum time (in milli-second) that user allow for transaction loss, to flush the page '
                          'in memory to WAL partition by WAL writer. The supported range is [1, 10000] and default '
                          'is 650 (translated to the default 200ms or 3.25x of wal_writer_delay). The lost ratio is '
                          'twice the value and three times in worst case (so we buffer to 3.25x) because the WAL writer '
                          'is designed to favor writing whole pages at a time during busy periods. The wal_writer_delay '
                          'can only be impacted when wal_level is set to replica and higher.',
              )
    ]
    max_num_stream_replicas_on_primary: Annotated[
        int,
        Field(default=0, ge=0, le=32,
              description='The maximum number of streaming replicas for the PostgreSQL primary server. The supported '
                          'range is [0, 32], default is 0. If you are deployed on replica or receiving server, set '
                          'this number as low. ',
              )
    ]
    max_num_logical_replicas_on_primary: Annotated[
        int,
        Field(default=0, ge=0, le=32,
              description='The maximum number of logical replicas for the PostgreSQL primary server. The supported '
                          'range is [0, 32], default is 0. If you are deployed on replica or receiving server, set '
                          'this number as low. ',
              )
    ]
    offshore_replication: Annotated[
        bool,
        Field(default=False,
              description='If set it to True, you are wishing to have an geo-replicated replicas in the offshore '
                          'country or continent. Enable it would increase the wal_sender_timeout to 2 minutes or more',
              )
    ]

    # These are for the database tuning options
    workload_type: Annotated[
        PG_WORKLOAD,  # AfterValidator(_allowed_workload),
        Field(default_factory=PydanticFact(f'Enter the PostgreSQL workload type as {_PG_WORKLOAD_KEYS}: ',
                                           user_fn=PG_WORKLOAD, default_value=PG_WORKLOAD.HTAP),
              description='The PostgreSQL workload type. This would affect the tuning options and the risk level, '
                          'and many other options. Default is HTAP (Hybrid Transactional/Analytical Processing).')
    ]

    opt_mem_pool: Annotated[
        PG_PROFILE_OPTMODE,  # AfterValidator(_allowed_opt_mode),
        Field(default_factory=PydanticFact(f'Enter the PostgreSQL memory precision profile as {_PG_OPT_KEYS}: ',
                                           user_fn=PG_PROFILE_OPTMODE, default_value=PG_PROFILE_OPTMODE.OPTIMUS_PRIME),
              description='If not NONE, it would proceed the extra tuning to increase the memory buffer usage to '
                          'reach to your expectation (shared_buffers, work_mem, temp_buffer, wal_buffer). Set to SPIDEY '
                          'use the worst case of memory usage by assuming all connections are under high load. Set to '
                          'OPTIMUS_PRIME (default) take the average between normal (active connections) and worst case '
                          'as the stopping condition; PRIMORDIAL take the normal case as the stopping condition.')
    ]
    tuning_kwargs: Annotated[
        PG_TUNE_USR_KWARGS,
        Field(default=PG_TUNE_USR_KWARGS(),
              description='The PostgreSQL tuning keywords/options for the user to customize or perform advanced '
                          'tuning control; which is not usually available in the general tuning phase (except some '
                          'specific tuning options). ')
    ]

    # ========================================================================
    # This is used for analyzing the memory available.
    operating_system: Annotated[
        str, AfterValidator(_allowed_os),
        Field(default_factory=PydanticFact(f'Enter the operating system in {_PG_OS_KEYS}: ',
                                           user_fn=str, default_value='linux'),
              description='The operating system that the PostgreSQL server is running on. Default is Linux.')
    ]
    vcpu: Annotated[
        PositiveInt,
        Field(default=4, ge=1,
              description='The number of vCPU (logical CPU) that the PostgreSQL server is running on. Default is 4 '
                          'vCPUs. Minimum number of vCPUs is 1. ')
    ]
    ram_sample: Annotated[
        ByteSize,
        Field(default=16 * Gi, ge=2 * Gi, multiple_of=256 * Mi,
              description='The amount of RAM capacity that the PostgreSQL server is running on. Default is 16 GiB.'
                          'Minimum amount of RAM is 2 GiB. PostgreSQL would performs better when your server has '
                          'more RAM available. Note that the amount of RAM on the server must be larger than the '
                          'in-place kernel and monitoring memory usage. The value must be a multiple of 256 MiB.'
              )
    ]
    add_system_reserved_memory_into_ram: Annotated[
        bool,
        Field(default=False, frozen=False,
              description='Set to True if your server input the RAM memory by measurement (free -m on Linux, Task '
                          'Manager on Windows, etc). However, we do not recommend to set this as it could assume your '
                          'PostgreSQL can use the reserved memory which are already dedicated for the kernel, booting '
                          'process, and other system processes. The amount of hidden system reserved memory is varied '
                          'depending on the operating system (and probably if you made custom change on top of it). '
              )
    ]
    base_kernel_memory_usage: Annotated[
        ByteSize | int,
        Field(default_factory=PydanticFact('Enter the kernel memory when idle (in MiB): ',
                                           user_fn=None, default_value=-1),
              description='The PostgreSQL base kernel memory during when idle. This value is used to estimate the '
                          'impact during memory-related tuning configuration and server as a safeguard against memory '
                          'overflow. Default value is -1 to meant that this application would assume the kernel memory '
                          'is taken 768 MiB (3/4 of 1 GiB) during idle and 0 MiB if the system is not user-managed. '
                          'Maximum allowed value is 8 GiB and the input must be a multiple of 2 MiB. The 768 MiB is '
                          'taken from Ubuntu 24.10 during idle.',
              ge=-1, le=8 * Gi, frozen=False, allow_inf_nan=False)
    ]
    base_monitoring_memory_usage: Annotated[
        ByteSize | int,
        Field(default_factory=PydanticFact('Enter the monitoring memory usage (in MiB): ',
                                           user_fn=None, default_value=-1),
              description='The PostgreSQL peak used monitoring memory (format 1 GiB = 1024 MiB). This value is used to '
                          'estimate the impact during memory-related tuning configuration and server as a safeguard '
                          'against memory overflow. For default OS management by user, the monitoring agent would be '
                          'installed on that machine and consume around 128 - 512 MiB (default) to monitor both OS '
                          'and database. Maximum allowed value is 4 GiB and the input must be a default of 2 MiB. '
                          'Default value is -1 to meant that this application would assume the monitoring would take'
                          'the database server (from database query usage) 64 MiB and 512 MiB (if agent is installed).'
                          'Note that this value is not limited to the monitoring only, but also antivirus, ...',
              ge=-1, le=4 * Gi, frozen=False, allow_inf_nan=False)
    ]
    # ========================================================================
    # We may not have this at end-user on the website
    # Questions of System Management and Operation to be done
    enable_sysctl_general_tuning: Annotated[
        bool,
        Field(default=False, frozen=False,
              description='Set to True would enable general tuning on the system kernel parameters (sysctl). If you '
                          'host your database on a managed service or container, this value is recommended to be '
                          'False. Default to False.'
              )
    ]
    enable_sysctl_correction_tuning: Annotated[
        bool,
        Field(default=False, frozen=False,
              description='Set to True would enable correction tuning on the system kernel parameters (sysctl). If you '
                          'host your database on a managed service or container, this value is recommended to be '
                          'False. Default to False. Only valid when :attr:`enable_sysctl_general_tuning` is True.'
              )
    ]
    enable_database_general_tuning: Annotated[
        bool,
        Field(default=True, frozen=False,
              description='Set to True would enable general tuning on the PostgreSQL database parameters. Default to '
                          'True.'
              )
    ]
    enable_database_correction_tuning: Annotated[
        bool,
        Field(default=True, frozen=False,
              description='Set to True would enable correction tuning on the PostgreSQL database parameters. Default '
                          'to True. Only valid when :attr:`enable_database_general_tuning` is True.'
              )
    ]
    align_index: Annotated[
        Literal[0, 1],
        Field(default=0, ge=0, le=1,
              description='This is the index used to pick the value during number alignment. Default is 0'
              )
    ]

    # ========================================================================
    # Revert some invalid options as described in :attr:`is_os_user_managed`
    def model_post_init(self, __context: Any) -> None:
        if not self.enable_sysctl_general_tuning:
            self.enable_sysctl_correction_tuning = False
        if not self.enable_database_general_tuning:
            self.enable_database_correction_tuning = False

        # Set back memory usage in non user-managed system
        if self.base_monitoring_memory_usage == -1:
            self.base_monitoring_memory_usage = ByteSize(256 * Mi)
            if self.operating_system in ('docker', 'k8s', 'containerd', 'wsl'):
                self.base_monitoring_memory_usage = ByteSize(64 * Mi)
            elif self.operating_system in ('PaaS', 'DBaaS'):
                self.base_monitoring_memory_usage = ByteSize(0 * Mi)
            _logger.debug(
                f"Set the monitoring memory usage to {self.base_monitoring_memory_usage.human_readable(separator=' ')}")

        if self.base_kernel_memory_usage == -1:
            self.base_kernel_memory_usage = ByteSize(768 * Mi)
            if self.operating_system in ('docker', 'k8s', 'containerd', 'wsl'):
                self.base_kernel_memory_usage = ByteSize(64 * Mi)
            elif self.operating_system == 'windows':
                self.base_kernel_memory_usage = ByteSize(2 * Gi)
            elif self.operating_system in ('PaaS', 'DBaaS'):
                self.base_kernel_memory_usage = ByteSize(0 * Mi)
            _logger.debug(
                f"Set the kernel memory usage to {self.base_kernel_memory_usage.human_readable(separator=' ')}")

        # Check the database version is in the supported version
        if self.pgsql_version not in SUPPORTED_POSTGRES_VERSIONS:
            _logger.warning(f'The PostgreSQL version {self.pgsql_version} is not in the supported version list. '
                            f'Please ensure that the version is correct and the tuning may not be accurate. '
                            f'Forcing the version to the common version (which is the shared configuration across'
                            f'all supported versions).')
            self.pgsql_version = SUPPORTED_POSTGRES_VERSIONS[-1]
        if self.usable_ram_noswap < 2 * Gi:
            _sign = '+' if self.usable_ram_noswap >= 0 else '-'
            _msg: str = (f'The usable RAM {_sign}{bytesize_to_hr(self.usable_ram_noswap)} is less than the PostgreSQL '
                         'minimum 2 GiB. It is recommended to increase the total RAM of your server, or switch to a '
                         'more lightweight monitoring system, kernel usage, or even the operating system. The tuning '
                         'could be inaccurate.')
            _logger.warning(_msg)
            raise ValueError(_msg)
        return None

    @cached_property
    def hardware_scope(self) -> dict[str, PG_SIZING]:
        """ Translate the hardware scope into the dictionary format """
        return {'cpu': self.cpu_profile, 'mem': self.mem_profile, 'net': self.net_profile, 'disk': self.disk_profile,
                'overall': self.workload_profile}

    def translate_hardware_scope(self, term: str | None) -> PG_SIZING:
        if term:
            term = term.lower().strip()
            try:
                return self.hardware_scope[term]
            except KeyError as e:
                # This should never be happened.
                _logger.debug(f'The hardware scope {term} is not in the supported list '
                              f'-> Fall back to overall profile.')

        return self.workload_profile

    def versioning(self, delimiter: str = '.') -> tuple[int, ...]:
        result = [int(x) for x in self.pgsql_version.split(delimiter)]
        if len(result) < 3:
            result.extend([0] * (3 - len(result)))
        return tuple(result)

    # ========================================================================
    # Some VM Snapshot Function
    @cached_property
    def ram_noswap(self) -> ByteSize | int:
        mem_total: ByteSize = self.ram_sample
        if self.add_system_reserved_memory_into_ram:
            # Unless the user is managing the OS and they supply the input of RAM by using free -m in Linux
            # or Task Manager on Windows. The system reserved memory in usual should not be added into the total
            # memory estimation as it is made for kernel and PostgreSQL cannot use it properly. Unfortunately,
            # not every OS can retrieve the system reserved memory so we just made the estimation here.
            # In Linux-managed OS, the number is 64 - 128 MiB. In Windows, the usual number is 235 - 256 MiB.
            # In containerd, docker, k8s, WSL, ... we usually made 100% memory usage unless some distros and things
            # are used, but they are not reserved memory.
            _extra: int = 0
            if self.operating_system in ('linux', ):
                _extra = 128 * Mi
            elif self.operating_system in ('windows',):
                _extra = 256 * Mi
            elif self.operating_system in ('containerd', ):
                _extra = 32 * Mi

            if _extra > 0:  # We do the rounding here.
                mem_total = ByteSize(mem_total + _extra)

        return mem_total

    @cached_property
    def usable_ram_noswap(self) -> ByteSize | int:
        mem_available: ByteSize = self.ram_noswap
        mem_available -= self.base_kernel_memory_usage
        mem_available -= self.base_monitoring_memory_usage
        return mem_available
