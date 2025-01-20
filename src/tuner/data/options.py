import logging
from functools import cached_property, partial
from math import ceil
from typing import Any, Annotated

from pydantic import BaseModel, Field, ByteSize, AfterValidator
from pydantic.types import PositiveInt

from src.static.c_toml import LoadAppToml
from src.static.vars import Gi, Mi, APP_NAME_UPPER, DEFAULT_INSTRUCTION_PROFILE, SUPPORTED_POSTGRES_VERSIONS
from src.tuner.data.disks import PG_DISK_PERF
from src.tuner.data.keywords import PG_TUNE_USR_KWARGS
from src.tuner.data.optmode import PG_PROFILE_OPTMODE
from src.tuner.data.utils import FactoryForPydanticWithUserFn as PydanticFact
from src.tuner.data.workload import PG_WORKLOAD
from src.tuner.external import psutil_api
from src.utils.pydantic_utils import bytesize_to_hr


__all__ = ["PG_TUNE_USR_OPTIONS", 'backup_description']
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

_backup_itms = list(backup_description().keys())
_TomlProfileData = list(LoadAppToml()['profile'].keys())
assert DEFAULT_INSTRUCTION_PROFILE in _TomlProfileData, 'The default instruction profile must be in the profile data.'
_PG_WORKLOAD_KEYS = PG_WORKLOAD.__members__.values()
_PG_OPT_KEYS = PG_PROFILE_OPTMODE.__members__.values()
_PG_OS_KEYS = ['linux', 'windows', 'macos', 'docker', 'k8s', 'containerd', 'wsl', 'PaaS', 'DBaaS']

_allowed_opt_mode = partial(_allowed_values, values=_PG_OPT_KEYS)
_allowed_workload = partial(_allowed_values, values=_PG_WORKLOAD_KEYS)
_allowed_profile = partial(_allowed_values, values=_TomlProfileData)
_allowed_postgres_version = partial(_allowed_values, values=list(SUPPORTED_POSTGRES_VERSIONS) + ['latest', 'stable'])
_allowed_backup_tool = partial(_allowed_values, values=_backup_itms)
_allowed_os = partial(_allowed_values, values=_PG_OS_KEYS)



# =============================================================================
class PG_TUNE_USR_OPTIONS(BaseModel):
    # The basic profile for the system tuning for profile-guided tuning
    workload_profile: Annotated[
        str, AfterValidator(_allowed_profile),
        Field(default_factory=PydanticFact(f'Enter the workload profile in {_TomlProfileData}: ',
                                           user_fn=str, default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The workload profile to be used for tuning')
    ]
    cpu_profile: Annotated[
        str, AfterValidator(_allowed_profile),
        Field(default_factory=PydanticFact(f'Enter the CPU profile in {_TomlProfileData}: ',
                                           user_fn=str, default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The CPU profile to be used for profile-based tuning')
    ]
    mem_profile: Annotated[
        str, AfterValidator(_allowed_profile),
        Field(default_factory=PydanticFact(f'Enter the Memory profile in {_TomlProfileData}: ',
                                           user_fn=str, default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The Memory profile to be used for profile-based tuning')
    ]
    net_profile: Annotated[
        str, AfterValidator(_allowed_profile),
        Field(default_factory=PydanticFact(f'Enter the Network profile in {_TomlProfileData}: ',
                                           user_fn=str, default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The Network profile to be used for profile-based tuning')
    ]
    disk_profile: Annotated[
        str, AfterValidator(_allowed_profile),
        Field(default_factory=PydanticFact(f'Enter the Disk profile in {_TomlProfileData}: ',
                                           user_fn=str, default_value=DEFAULT_INSTRUCTION_PROFILE),
              description='The Disk profile to be used for profile-based tuning')
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
        Field(default_factory=PydanticFact(f'Enter the backup tool {_backup_itms}: ',
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
                                           user_fn=PG_PROFILE_OPTMODE, default_value=PG_PROFILE_OPTMODE.NONE),
              description='Higher profile would reduce the maximum space for WAL buffers. Default to NONE means we '
                          'reuse the value taken from the general tuning phase. Switch to SPIDEY would cap its maximum '
                          'to a lower value (defined when the wal_level is minimal). Increase to OPTIMUS_PRIME would '
                          'half the value return from the general tuning phase, but ensuring the WAL buffers minimum '
                          'to be the size of a WAL segment (16 MiB). Increase to PRIMORDIAL would set the WAL buffers '
                          'to zero. Unless you are working in on the mission-critical system where the atomicity and '
                          'consistency are the top priorities; otherwise, we recommended to use the value equal or '
                          'below the OPTIMUS_PRIME. This flag is not being impacted regardless the wal_level value',
              )
    ]
    repurpose_wal_buffers: Annotated[
        bool,
        Field(default=True,
              description='Set to True (default) would take the difference of WAL buffers to be used in temp_buffers '
                          'and work_mem, by increasing its pool size. This would be conducted after the final memory '
                          'tuning. The reason not to re-purpose into the shared_buffers is that the shared_buffers is '
                          'usually persistent when the database is online. This argument is only valid when the '
                          'opt_wal_buffers is set to SPIDEY or higher.',
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
                          'range is [0, 32], default is 0.',
              )
    ]
    max_num_logical_replicas_on_primary: Annotated[
        int,
        Field(default=0, ge=0, le=32,
              description='The maximum number of logical replicas for the PostgreSQL primary server. The supported '
                          'range is [0, 32], default is 0.',
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
        PG_WORKLOAD, # AfterValidator(_allowed_workload),
        Field(default_factory=PydanticFact(f'Enter the PostgreSQL workload type as {_PG_WORKLOAD_KEYS}: ',
                                           user_fn=PG_WORKLOAD, default_value=PG_WORKLOAD.HTAP),
              description='The PostgreSQL workload type. This would affect the tuning options and the risk level, '
                          'and many other options. Default is HTAP (Hybrid Transactional/Analytical Processing).')
    ]
    opt_memory: Annotated[
        PG_PROFILE_OPTMODE, # AfterValidator(_allowed_opt_mode),
        Field(default_factory=PydanticFact(f'Enter the PostgreSQL memory optimization profile as {_PG_OPT_KEYS}: ',
                                           user_fn=PG_PROFILE_OPTMODE, default_value=PG_PROFILE_OPTMODE.OPTIMUS_PRIME),
              description='The PostgreSQL optimization mode on workload type to tune overall memory usage by allowing '
                          'total disk cache (effective_cache_size) in buffer to higher ratio (shared_buffers + '
                          'effective_cache_size ~= RAM).')
    ]
    opt_memory_precision: Annotated[
        PG_PROFILE_OPTMODE, # AfterValidator(_allowed_opt_mode),
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
    vcpu_sample: Annotated[
        PositiveInt,
        Field(default=4, ge=1,
              description='The number of vCPU (logical CPU) that the PostgreSQL server is running on. Default is 4 '
                          'vCPUs. Minimum number of vCPUs is 1. ')
    ]
    ram_sample: Annotated[
        ByteSize,
        Field(default=16 * Gi, ge=1 * Gi, multiple_of=256 * Mi,
              description='The amount of RAM capacity that the PostgreSQL server is running on. Default is 16 GiB.'
                          'Minimum amount of RAM is 1 GiB. PostgreSQL would performs better when your server has '
                          'more RAM available. Note that the amount of RAM on the server must be larger than the '
                          'in-place kernel and monitoring memory usage. The value must be a multiple of 256 MiB.'
              )
    ]
    hyperthreading: Annotated[
        bool,
        Field(default=False,
              description='Set to True if your server is running on the hyper-threading environment (it is usually '
                          'available on many recent consumer CPUs or server CPUs). Default is False meant the number'
                          'of physical cores is equal to the number of logical cores. Only enable it when you are '
                          'running on dedicated hardware without virtualization or containerization.'
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
    sample_hardware: Annotated[
        bool,
        Field(default=True, frozen=False,
              description='Default to True. Set to True if you want to collect the hardware profile by us. Enable '
                          'this requires the library :lib:`psutil` to be installed on this Python virtual environment. '
                          'This would ignore the vCPU_sample, RAM_sample, and hyperthreading. Only use this when you '
                          'you install this on server. Otherwise, you are just backing up your system. '
              )
    ]
    vm_snapshot: Annotated[
        psutil_api.SERVER_SNAPSHOT | None,
        Field(default=None, frozen=False,
              description='The hardware snapshot of the server you want to tune. This variable is managed exclusively '
                          'by this application and should not be changed by the user. Default is None.')
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
            _logger.debug(f'Set the monitoring memory usage to {self.base_monitoring_memory_usage.human_readable(separator=' ')}')

        if self.base_kernel_memory_usage == -1:
            self.base_kernel_memory_usage = ByteSize(768 * Mi)
            if self.operating_system in ('docker', 'k8s', 'containerd', 'wsl'):
                self.base_kernel_memory_usage = ByteSize(64 * Mi)
            elif self.operating_system == 'windows':
                self.base_kernel_memory_usage = ByteSize(2 * Gi)
            elif self.operating_system in ('PaaS', 'DBaaS'):
                self.base_kernel_memory_usage = ByteSize(0 * Mi)
            _logger.debug(f'Set the kernel memory usage to {self.base_kernel_memory_usage.human_readable(separator=' ')}')

        # Check the database version is in the supported version
        if self.pgsql_version not in SUPPORTED_POSTGRES_VERSIONS:
            _logger.warning(f'The PostgreSQL version {self.pgsql_version} is not in the supported version list. '
                            f'Please ensure that the version is correct and the tuning may not be accurate. '
                            f'Forcing the version to the common version (which is the shared configuration across'
                            f'all supported versions).')
            self.pgsql_version = SUPPORTED_POSTGRES_VERSIONS[-1]

        # Set the VM snapshot
        if self.vm_snapshot is not None:
            _logger.info('The VM snapshot is already set. The hardware profile would be ignored made by ourself '
                         'is ignored.')
        else:
            if self.operating_system not in ('docker', 'k8s', 'containerd', 'wsl', 'PaaS', 'DBaaS') and \
                    not self.sample_hardware:
                self.vm_snapshot = psutil_api.SERVER_SNAPSHOT.profile_current_server()
            elif not self.sample_hardware:
                _logger.error('Unable to collect the hardware information. It is required to either set the operating '
                              'system (:var:`operating_system`) to the supported list (linux, windows, macos) or '
                              'enable :attr:`sample_hardware` to True -> Fallback to use the hardware sampling.')
                self.sample_hardware = True
            if self.vm_snapshot is None:
                # It is best to set this value to at least 4 GiB
                self.vm_snapshot = psutil_api.snapshot_sample(vcpu=self.vcpu_sample, memory=self.ram_sample,
                                                              hyperthreading=self.hyperthreading)

        self.mem_init_test()
        return None

    @cached_property
    def hardware_scope(self) -> dict[str, str]:
        """ Translate the hardware scope into the dictionary format """
        return {'cpu': self.cpu_profile, 'mem': self.mem_profile, 'net': self.net_profile, 'disk': self.disk_profile,
                'overall': self.workload_profile}

    def translate_hardware_scope(self, term: str | None) -> str:
        if term:
            term = term.lower().strip()
            try:
                return self.hardware_scope[term]
            except KeyError:
                _logger.debug(f'The hardware scope {term} is not in the supported list '
                              f'-> Fall back to overall profile.')

        return self.workload_profile

    def versioning(self, delimiter: str = '.') -> tuple[int, ...]:
        result = [int(x) for x in self.pgsql_version.split(delimiter)]
        if len(result) < 3:
            result.extend([0] * (3 - len(result)))
        return tuple(result)

    def mem_init_test(self, hash_mem_multiplier: float = 2.0, wal_buffers: ByteSize | int = None,
                      user_connection: int = None, use_full_connection: bool = False) -> str:
        # This function should only being used during the initial guessing. The connection overhead and WAL buffers
        # is updated by triggering function and not correct in this function.
        # Please refer to the gtune_common_db_config.py
        _logger.info('Start validating and estimate memory after general tuning phase and/or correction tuning phase '
                     'using ratio. The number of connection and WAL buffer usage are just for estimation.')

        # Cache directly after the VM snapshot is set
        usable_ram_noswap = self.usable_ram_noswap
        ram_noswap = self.ram_noswap
        usable_ram_noswap_ratio = usable_ram_noswap / ram_noswap
        if usable_ram_noswap <= 0:
            raise ValueError('The usable RAM must be larger than 0.')

        # Since all algorithms in the general-tuning phase and correction-tuning phase are based on the usable RAM
        # (not the total RAM), we need to estimate the memory usage after the general tuning phase and correction
        # tuning phase. The estimation is based on the ratio of the memory usage over the usable RAM
        _kwargs = self.tuning_kwargs

        # We used the minimum number of connections based on the hardware scope -> profile
        # The magic number 3 here is the basic number of reserved connections
        _conns = {'mini': 10, 'medium': 20, 'large': 30, 'mall': 40, 'bigt': 50}
        _est_max_conns = user_connection or _kwargs.user_max_connections or (_conns.get(self.cpu_profile, 30) - 3 * 2)

        # Shared Buffers
        postgres_expected_mem_ratio: float = 0.0
        shared_buffer_ratio = max(128 * Mi / usable_ram_noswap, _kwargs.shared_buffers_ratio) * _kwargs.shared_buffers_fill_ratio
        postgres_expected_mem_ratio += shared_buffer_ratio

        # Connections Overhead
        _mem_conn_ratio = ((_est_max_conns if use_full_connection else ceil(_est_max_conns * _kwargs.effective_connection_ratio)) *
                           _kwargs.single_memory_connection_overhead *
                           _kwargs.memory_connection_to_dedicated_os_ratio / usable_ram_noswap)
        postgres_expected_mem_ratio += _mem_conn_ratio

        # Temp buffers and Work Mem
        tbuff_wmem_ratio = (_kwargs.work_mem_scale_factor * hash_mem_multiplier * (1 - _kwargs.temp_buffers_ratio) +
                            _kwargs.temp_buffers_ratio)
        if use_full_connection:
            tbuff_wmem_ratio *= (1 / _kwargs.effective_connection_ratio)

        _mem_conn_ratio_full = (_est_max_conns * _kwargs.single_memory_connection_overhead *
                                _kwargs.memory_connection_to_dedicated_os_ratio / usable_ram_noswap)
        tbuff_wmem_pool_ratio = _kwargs.max_work_buffer_ratio * (1.0 - shared_buffer_ratio - _mem_conn_ratio_full)
        postgres_expected_mem_ratio += max(_est_max_conns * (4 * Mi + 4 * Mi * hash_mem_multiplier) / usable_ram_noswap,
                                           tbuff_wmem_pool_ratio * tbuff_wmem_ratio)

        # Wal Buffers (if replica or higher) -> Default to replica
        _wal = {'mini': 16 * Mi, 'medium': 32 * Mi, 'large': 64 * Mi, 'mall': 128 * Mi, 'bigt': 192 * Mi}
        _est_wal_buffers = wal_buffers or _wal.get(self.mem_profile, 64 * Mi)
        postgres_expected_mem_ratio += (_est_wal_buffers / usable_ram_noswap)

        # This is the maximum we can allow in the on the whole server before collapsed
        is_ok: bool = True
        if postgres_expected_mem_ratio >= 1.0:
            is_ok = False
            _logger.warning('The memory PostgreSQL (estimate) is larger than the usable RAM (in the general tuning '
                            'phase and probably in correction tuning). You may not receive the optimal performance '
                            'configuration files.')
        if usable_ram_noswap_ratio < 2/3:
            is_ok = False
            _logger.warning(f'The usable RAM ({bytesize_to_hr(usable_ram_noswap)}) is less than 50% of the total RAM '
                            f'({bytesize_to_hr(ram_noswap)}). This may cause the performance issue as you have set the '
                            f'\nRAM capacity too low (which could affect the general tuning phase and correction tuning '
                            f'phase. Please ensure that the usable RAM is at least 50% of the total RAM. On the '
                            f'\nsmallest server (2-4 GiB), we expect the ratio to be larger than 75% or more.')
        if usable_ram_noswap < 2.5 * Gi:
            is_ok = False
            _logger.warning(f'The usable RAM ({bytesize_to_hr(usable_ram_noswap)}) is less than 2.5 GiB. If you are '
                            f'having this low memory (unless you are tuning a mini or testing DB server on your '
                            f'\npersonal computer, you should switch to SQLite DB.')

        postgres_expected_mem = int(usable_ram_noswap * postgres_expected_mem_ratio)
        _logger.info(f'''
# ===========================================================================================================
# Memory Estimation Test
From server-side, the PostgreSQL memory usable arena is at most {bytesize_to_hr(usable_ram_noswap)} or {usable_ram_noswap_ratio * 100:.2f} (%) of the total RAM ({bytesize_to_hr(ram_noswap)}).
All other variables must be bounded and computed within the available memory. 
Arguments: use_full_connection={use_full_connection}, user_connection={user_connection}, wal_buffers={wal_buffers}, hash_mem_multiplier={hash_mem_multiplier}

Reports (over usable RAM capacity {bytesize_to_hr(usable_ram_noswap)} or {usable_ram_noswap_ratio * 100:.2f} (%) of total):
-------
* PostgreSQL memory (estimate): {bytesize_to_hr(postgres_expected_mem)} or {postgres_expected_mem_ratio * 100:.2f} (%) over usable RAM.
    - The shared_buffers ratio is {shared_buffer_ratio * 100:.2f} (%)
    - The total connections overhead ratio is {_mem_conn_ratio * 100:.2f} (%) with {_est_max_conns} user connections (active={_kwargs.effective_connection_ratio * 100:.1f}%)
    - The temp_buffers and work_mem ratio is {tbuff_wmem_pool_ratio * tbuff_wmem_ratio * 100:.2f} (%) -> Each connection used {(tbuff_wmem_pool_ratio * tbuff_wmem_ratio * 100) / _est_max_conns:.2f} (%)
    - The wal_buffers ratio is {_est_wal_buffers / usable_ram_noswap * 100:.2f} (%)

Reports (over total RAM capacity {bytesize_to_hr(ram_noswap)}):
-------
* PostgreSQL memory (estimate): {bytesize_to_hr(postgres_expected_mem)} or {postgres_expected_mem_ratio * usable_ram_noswap_ratio * 100:.2f} (%) over total RAM
    - The shared_buffers ratio is {shared_buffer_ratio * usable_ram_noswap_ratio * 100:.2f} (%)
    - The total connections overhead ratio is {_mem_conn_ratio * usable_ram_noswap_ratio * 100:.2f} (%) with {_est_max_conns} user connections (active={_kwargs.effective_connection_ratio * 100:.1f}%)
    - The temp_buffers and work_mem ratio is {tbuff_wmem_pool_ratio * tbuff_wmem_ratio * usable_ram_noswap_ratio * 100:.2f} (%) -> Each connection used {(tbuff_wmem_pool_ratio * tbuff_wmem_ratio * usable_ram_noswap_ratio * 100) / _est_max_conns:.2f} (%)
    - The wal_buffers ratio is {_est_wal_buffers / ram_noswap * 100:.2f} (%)

WARNING: These calculations could be incorrect due to capping, precision adjustment, rounding.
# ===========================================================================================================
''')

        return 'NOK' if not is_ok else 'OK'

    # ========================================================================
    # Some VM Snapshot Function
    @cached_property
    def vcpu(self) -> int:
        return self.vm_snapshot.logical_cpu_count

    def get_total_ram(self, add_swap: bool = False) -> ByteSize | int:
        mem_total: ByteSize = self.vm_snapshot.mem_virtual.total
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
            elif self.operating_system in ('windows', ):
                _extra = 256 * Mi
            elif self.operating_system in ('containerd', 'docker', 'k8s', 'wsl', 'PaaS', 'DBaaS'):
                _extra = 32 * Mi

            if _extra > 0:  # We do the rounding here.
                mem_total = ByteSize(mem_total + _extra)
                self.vm_snapshot.mem_virtual.total = mem_total

        if add_swap:
            mem_total += self.vm_snapshot.mem_swap.total
        return mem_total

    def get_available_ram(self, add_swap: bool = False) -> ByteSize | int:
        mem_available: ByteSize = self.get_total_ram(add_swap=add_swap)
        mem_available -= self.base_kernel_memory_usage
        mem_available -= self.base_monitoring_memory_usage
        return mem_available

    @cached_property
    def ram_noswap(self) -> ByteSize | int:
        return self.get_total_ram(add_swap=False)

    @cached_property
    def usable_ram_noswap(self) -> ByteSize | int:
        return self.get_available_ram(add_swap=False)


