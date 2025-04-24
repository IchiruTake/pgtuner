import logging
from functools import cached_property, partial
from math import ceil
from typing import Any, Annotated, Literal

from pydantic import BaseModel, Field, ByteSize, AfterValidator
from pydantic.types import PositiveInt

from src.static.vars import Gi, Mi, APP_NAME_UPPER, SUPPORTED_POSTGRES_VERSIONS, K10, M10, Ki
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.keywords import PG_TUNE_USR_KWARGS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.sizing import PG_SIZING, SIZE_PROFILES
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
_PG_OS_KEYS = ['linux', 'windows', 'macos', 'containerd', 'PaaS']


_allowed_backup_tool = partial(_allowed_values, values=list(backup_description().keys()))


# =============================================================================
class PG_TUNE_USR_OPTIONS(BaseModel):
    # The basic profile for the system tuning for profile-guided tuning
    workload_profile: PG_SIZING = Field(
        default=PG_SIZING.LARGE,
        description=f'The workload profile to be used for tuning. Supported profiles are {SIZE_PROFILES}. The '
                    f'associated value meant for the workload scale, amount of data in/out, ...'
    )
    pgsql_version: PositiveInt = Field(
        default=17, ge=13, le=17,
        description='The PostgreSQL version to be used for tuning. The supported range is [13, 17]. The default '
                    'is 17. The version is used to determine the tuning options and the risk level.'
    )
    # Disk options for data partitions
    data_index_spec: PG_DISK_PERF = Field(..., description='The disk specification for the data and index partition.')
    wal_spec: PG_DISK_PERF = Field(..., description='The disk specification for the WAL partition.')

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
    opt_transaction_lost: PG_PROFILE_OPTMODE = Field(
        default=PG_PROFILE_OPTMODE.NONE,
        description='The PostgreSQL mode for allow the transaction loss to tune the transaction loss recovery '
                    'mechanism. If you are working in on the mission-critical system where the atomicity and '
                    'consistency are the top priorities, then set to NONE (default) to not allow the lost transaction '
                    'loss by change the synchronous_commit. Set to SPIDEY would convert the synchronous_commit to off, '
                    'local, or remote_write (depending on the wal_level and number of replicas). Set to OPTIMUS_PRIME '
                    'would convert the full_page_writes to off. Set to PRIMORDIAL would convert the fsync to off. '
                    'Use with your own risk and caution. ',
    )
    opt_wal_buffers: PG_PROFILE_OPTMODE = Field(
        default=PG_PROFILE_OPTMODE.SPIDEY,
        description='The optimization mode for the WAL buffers to ensure the WAL buffers in the correction '
                    'tuning phase during outage lose data less than the maximum time of lossy transaction. '
                    'Set to PRIMORDIAL ensure 2x WAL buffers can be written to disk in our estimation. Similarly '
                    'with OPTIMUS_PRIME at 1.5x and SPIDEY at 1.0x. Set to NONE would not tune the WAL setting. '
                    'Only set to NONE when you feel the maximum of data integrity is not required integrity. '
                    'Otherwise, this would be enforced to SPIDEY.',
    )
    # Don't set this too high or too low as they don't guarantee stability and consistency
    max_time_transaction_loss_allow_in_second: PositiveInt = Field(
        default=650, ge=100, le=10000, frozen=True,
        description='The maximum time (in milli-second) that user allow for transaction loss, to flush the page '
                    'in memory to WAL partition by WAL writer. The supported range is [100, 10000] and default '
                    'is 650 (translated to the default 200ms or 3.25x of wal_writer_delay). The lost ratio is '
                    'twice the value and three times in worst case (so we buffer to 3.25x) because the WAL writer '
                    'is designed to favor writing whole pages at a time during busy periods. The wal_writer_delay '
                    'can only be impacted when wal_level is set to replica and higher.',
    )
    max_num_stream_replicas_on_standby: int = Field(
        default=0, ge=0, le=32, frozen=True,
        description='The maximum number of streaming replicas for the PostgreSQL primary server. The supported '
                    'range is [0, 32], default is 0. If you are deployed on replica or receiving server, set '
                    'this number as low. ',
    )
    max_num_logical_replicas_on_standby: int = Field(
        default=0, ge=0, le=32, frozen=True,
        description='The maximum number of logical replicas for the PostgreSQL primary server. The supported '
                    'range is [0, 32], default is 0. If you are deployed on replica or receiving server, set '
                    'this number as low. ',
    )
    offshore_replication: bool = Field(
        default=False, frozen=True,
        description='If set it to True, you are wishing to have an geo-replicated replicas in the offshore country '
                    'or continent. Enable it would increase the wal_sender_timeout to 2 minutes or more',
    )

    # These are for the database tuning options
    workload_type: PG_WORKLOAD = Field(
        default=PG_WORKLOAD.HTAP,
        description='The PostgreSQL workload type. This would affect the tuning options and the risk level, '
                    'and many other options. Default is HTAP (Hybrid Transactional/Analytical Processing).'
    )
    opt_mem_pool: PG_PROFILE_OPTMODE = Field(
        default=PG_PROFILE_OPTMODE.OPTIMUS_PRIME,
        description='If not NONE, it would proceed the extra tuning to increase the memory buffer usage to reach to '
                    'your expectation (shared_buffers, work_mem, temp_buffer). Set to SPIDEY use the worst case of '
                    'memory usage by assuming all connections are under high load. Set to OPTIMUS_PRIME (default) '
                    'take the average between normal (active connections) and worst case as the stopping condition. '
                    'Set to PRIMORDIAL take the normal case as the stopping condition.'
    )
    tuning_kwargs: PG_TUNE_USR_KWARGS = Field(
        default=PG_TUNE_USR_KWARGS(),
        description='The PostgreSQL tuning keywords/options for the user to customize or perform advanced '
                    'tuning control; which is not usually available in the general tuning phase (except some '
                    'specific tuning options). '
    )
    # These are for the estimation of anti-wraparound vacuum tuning
    database_size_in_gib: int = Field(
        default=0, ge=0, le=32 * Ki,
        description='The largest database size (in GiB), including the data files and index files. This value is used '
                    'to estimate the maximum database size for anti-wraparound vacuum. If this field is zero, the '
                    'assumption is about 60 % usage of the data volume. The supported range is [0, 32768], default is '
                    '0 (GiB); but its maximum threshold silently capped at 90% of the data volume'
    )
    num_write_transaction_per_hour_on_workload: PositiveInt = Field(
        default=int(50 * K10), ge=K10, le=20 * M10, frozen=True,
        description='The peak number of workload WRITE transaction per hour (including sub-transactions, accounting '
                    'all attempts to make data changes (not SELECT) regardless of COMMIT and ROLLBACK). Note that '
                    'this number requires you to have good estimation on how much your server can be handled during '
                    'its busy workload and idle workload. It is best to collect your real-world data pattern before '
                    'using this value.'
    )   # https://www.postgresql.org/docs/13/functions-info.html -> pg_current_xact_id_if_assigned
    # ========================================================================
    # This is used for analyzing the memory available.
    operating_system: Literal['linux', 'windows', 'macos', 'containerd', 'PaaS'] = Field(
        default='linux', frozen=True,
        description='The operating system that the PostgreSQL server is running on. Default is Linux.'
    )

    vcpu: PositiveInt = Field(
        default=4, ge=1, frozen=True, allow_inf_nan=False,
        description='The number of vCPU (logical CPU) that the PostgreSQL server is running on. Default is 4 vCPUs.'
    )
    total_ram: ByteSize | PositiveInt = Field(
        default=16 * Gi, ge=2 * Gi, multiple_of=256 * Mi, frozen=True,
        description='The amount of RAM capacity that the PostgreSQL server is running on (measured by bytes). Default '
                    'is 16 GiB, but minimum amount is 2 GiB. PostgreSQL would performs better when your server has '
                    'more RAM available. Note that the amount of RAM on the server must be larger than the in-place '
                    'kernel and monitoring memory usage. The value must be a multiple of 256 MiB.'
    )
    base_kernel_memory_usage: ByteSize | int = Field(
        default=-1, ge=-1, le=8 * Gi, frozen=False, allow_inf_nan=False,
        description='The PostgreSQL base kernel memory during when idle. This value is used to estimate the impact '
                    'during memory-related tuning configuration and server as a safeguard against memory overflow. '
                    'Default value is -1 to meant that this application would assume the kernel memory is taken 768 '
                    'MiB (3/4 of 1 GiB) during idle and 0 MiB if the system is not user-managed. Maximum allowed value '
                    'is 8 GiB and the input must be a multiple of 2 MiB. The 768 MiB is taken from Ubuntu 24.10 during '
                    'idle.'
    )
    base_monitoring_memory_usage: ByteSize | int = Field(
        default=-1, ge=-1, le=4 * Gi, frozen=False, allow_inf_nan=False,
        description='The PostgreSQL base monitoring memory when idle. This value is used to estimate the impact during '
                    'memory-related tuning configuration and server as a safeguard against memory overflow. Default '
                    'value is -1 meant that this application would assume the monitoring memory is taken 256 MiB '
                    'if user-managed OS, and 64 MiB to 0 MiB depending on the self-hosted container or 3rd-party DB '
                    'server. Note that this value is not limited to the monitoring only, but also antivirus, ...',
    )

    # ========================================================================
    # We may not have this at end-user on the website
    # Questions of System Management and Operation to be done
    enable_sysctl_general_tuning: bool = Field(
        default=False, frozen=False,
        description='Set to True would enable general tuning on the system kernel parameters (sysctl). If you '
                    'host your database on a managed service or container, this value is recommended to be '
                    'False. Default to False.'
    )
    enable_sysctl_correction_tuning: bool = Field(
        default=False, frozen=False,
        description='Set to True would enable correction tuning on the system kernel parameters (sysctl). If you '
                    'host your database on a managed service or container, this value is recommended to be '
                    'False. Default to False. Only valid when :attr:`enable_sysctl_general_tuning` is True.'
    )
    enable_database_general_tuning: bool = Field(
        default=True, frozen=False,
        description='Set to True would enable general tuning on the PostgreSQL database parameters. Default to True.'
    )
    enable_database_correction_tuning: bool = Field(
        default=True, frozen=False,
        description='Set to True would enable correction tuning on the PostgreSQL database parameters. Default to '
                    'True. Only valid when :attr:`enable_database_general_tuning` is True.'
    )
    align_index: Literal[0, 1] = Field(
        default=0, ge=0, le=1,
        description='This is the index used to pick the value during number alignment. Default is 0.'
    )

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
            if self.operating_system == 'containerd':
                self.base_monitoring_memory_usage = ByteSize(64 * Mi)
            elif self.operating_system == 'PaaS':
                self.base_monitoring_memory_usage = ByteSize(0 * Mi)
            _logger.debug(f"Set the monitoring memory usage to "
                          f"{self.base_monitoring_memory_usage.human_readable(separator=' ')}")

        if self.base_kernel_memory_usage == -1:
            self.base_kernel_memory_usage = ByteSize(768 * Mi)
            if self.operating_system == 'containerd':
                self.base_kernel_memory_usage = ByteSize(64 * Mi)
            elif self.operating_system == 'windows':
                self.base_kernel_memory_usage = ByteSize(2 * Gi)
            elif self.operating_system == 'PaaS':
                self.base_kernel_memory_usage = ByteSize(0 * Mi)
            _logger.debug(f"Set the kernel memory usage to "
                          f"{self.base_kernel_memory_usage.human_readable(separator=' ')}")

        # Check the database version is in the supported version
        if self.pgsql_version not in SUPPORTED_POSTGRES_VERSIONS:
            _logger.warning(f'The PostgreSQL version {self.pgsql_version} is not in the supported version list. '
                            f'Please ensure that the version is correct and the tuning may not be accurate. '
                            f'Forcing the version to the latest version.')
            self.pgsql_version = SUPPORTED_POSTGRES_VERSIONS[-1]

        # Check minimal RAM usage
        if self.usable_ram < 4 * Gi:
            _sign = '+' if self.usable_ram >= 0 else '-'
            _msg: str = (f'The usable RAM {_sign}{bytesize_to_hr(self.usable_ram)} is less than the PostgreSQL '
                         'minimum 4 GiB, and your workload is not self tested or local testing. The tuning may not be '
                         'accurate. It is recommended to increase the total RAM of your server, or switch to a more '
                         'lightweight monitoring system, kernel usage, or even the operating system.')
            _logger.warning(_msg)

        # Check database size to be smaller than 90% of data volume
        _database_limit = ceil((self.data_index_spec.disk_usable_size / Gi) * 0.90)
        if self.database_size_in_gib == 0:
            _logger.warning('The database size is set to 0 GiB. The database size is estimated to be 60% of the data '
                            'volume, which is a common but highest amount of data I observed in general. Even for '
                            'TiB-scaled data, in usual they add in 1 TiB storage every review interval (1-3 years) '
                            'depending on use-case and growth (not accounting media files such as images or videos).')
            self.database_size_in_gib = ceil((self.data_index_spec.disk_usable_size / Gi) * 0.60)
        if self.database_size_in_gib > _database_limit:
            _logger.warning(f'The database size {self.database_size_in_gib} GiB is larger than the data volume. The '
                            f'database size is silently capped at 90% of the data volume.')
            self.database_size_in_gib = _database_limit

        return None

    @cached_property
    def hardware_scope(self) -> dict[str, PG_SIZING]:
        """ Translate the hardware scope into the dictionary format """
        # return {'cpu': self.cpu_profile, 'mem': self.mem_profile, 'net': self.net_profile, 'disk': self.disk_profile,
        #         'overall': self.workload_profile}
        return {k: self.workload_profile for k in ('cpu', 'mem', 'net', 'disk', 'overall')}

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
    def usable_ram(self) -> ByteSize | int:
        mem_available: ByteSize | int = self.total_ram
        mem_available -= self.base_kernel_memory_usage
        mem_available -= self.base_monitoring_memory_usage
        assert mem_available >= 0, 'The available memory is less than 0. Please check the memory usage.'
        return mem_available
