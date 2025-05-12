from datetime import datetime
from enum import Enum, StrEnum
from src.utils.static import __VERSION__, APP_NAME_UPPER, TIMEZONE

__all__ = ['PG_SCOPE', 'PGTUNER_SCOPE']

# The applied scope for each of the tuning items
class PG_SCOPE(Enum):
    VM = 'vm'
    CONNECTION = 'conn'
    FILESYSTEM = 'fs'
    MEMORY = 'memory'
    NETWORK = 'net'
    LOGGING = 'log'
    QUERY_TUNING = 'query'
    MAINTENANCE = 'maint'
    ARCHIVE_RECOVERY_BACKUP_RESTORE = 'backup'
    EXTRA = 'extra'
    OTHERS = 'others'

# The internal managed scope for the tuning items
class PGTUNER_SCOPE(StrEnum):
    KERNEL_SYSCTL = 'kernel_sysctl'
    DATABASE_CONFIG = 'database_config'

    def disclaimer(self) -> str:
        dt = datetime.now(TIMEZONE)
        if self == PGTUNER_SCOPE.KERNEL_SYSCTL:
            return f"""# Read this disclaimer before applying the tuning result
# ============================================================
# {APP_NAME_UPPER}-v{__VERSION__}: The tuning is started at {dt} 
# -> Target Scope: {PGTUNER_SCOPE.KERNEL_SYSCTL}
# DISCLAIMER: This kernel tuning options is based on our experience, and should not be 
# applied directly to the system. Please consult with your database administrator, system
# administrator, or software/system delivery manager before applying the tuning result.
# HOWTO: It is recommended to apply the tuning result by copying the file and pasting it 
# as the final configuration under the /etc/sysctl.d/* directory rather than overwrite 
# previous configuration. Please DO NOT apply the tuning result directly to the system 
# by any means, and ensure that the system is capable of rolling back the changes if the
# system is not working as expected.
# ============================================================
"""
        elif self == PGTUNER_SCOPE.DATABASE_CONFIG:
            return f"""# Read this disclaimer before applying the tuning result
# ============================================================
# {APP_NAME_UPPER}-v{__VERSION__}: The tuning is started at {dt} 
# -> Target Scope: {PGTUNER_SCOPE.DATABASE_CONFIG}
# DISCLAIMER: This database tuning options is based on our experience, and should not be 
# applied directly to the system. There is ZERO guarantee that this tuning guideline is 
# the best for your system, for every tables, indexes, workload, and queries. Please 
# consult with your database administrator or software/system delivery manager before
# applying the tuning result.
# HOWTO: It is recommended to apply the tuning result under the /etc/postgresql/* directory 
# or inside the $PGDATA/conf/* or $PGDATA/* directory depending on how you start your
# PostgreSQL server. Please double check the system from the SQL interactive sessions to 
# ensure things are working as expected. Whilst it is possible to start the PostgreSQL 
# server with the new configuration, it could result in lost of configuration (such as new 
# version update, unknown configuration changes, extension or external configuration from 
# 3rd-party tools, or no inherited configuration from the parent directory). Please DO NOT 
# apply the tuning result directly to the system by any means, and ensure that the system 
# is capable of rolling back the changes if the system is not working as expected.
# ============================================================
"""
        return ""
