from enum import Enum
from datetime import datetime

from src.static.c_timezone import GetTimezone
from src.static.vars import __VERSION__, APP_NAME_UPPER

__all__ = ['PG_SCOPE', 'PGTUNER_SCOPE']


class PG_SCOPE(Enum):
    VM = "vm"
    CONNECTION = "conn"
    FILESYSTEM = "fs"
    MEMORY = "memory"
    DISK_IOPS = "iops"

    NETWORK = "net"
    LOGGING = "log"
    QUERY_TUNING = "query"
    MAINTENANCE = "maint"
    ARCHIVE_RECOVERY_BACKUP_RESTORE = "backup"
    EXTRA = "extra"
    OTHERS = "others"


class PGTUNER_SCOPE(Enum):
    KERNEL_SYSCTL = 'kernel_sysctl'
    KERNEL_BOOT = 'kernel_boot'
    DATABASE_CONFIG = 'database_config'

    def disclaimer(self) -> str:
        dt = datetime.now(GetTimezone()[0])
        if self == PGTUNER_SCOPE.KERNEL_SYSCTL:
            return f"""# Read this disclaimer before applying the tuning result
# ============================================================
# {APP_NAME_UPPER}-v{__VERSION__}: The tuning is started at {dt} 
# -> Target Scope: {PGTUNER_SCOPE.KERNEL_SYSCTL}
# DISCLAIMER: The kernel tuning options is based on our experience, and should not be applied directly 
# to the system. There is ZERO guarantee that this tuning guideline is the best for your system. Please 
# consult with your system administrator or database administrator or software/system delivery manager 
# before applying the tuning result.
# HOWTO: It is recommended to apply the tuning result by copying the file and pasting it under the 
# /etc/sysctl.d/* directory. Please DO NOT apply the tuning result directly to the system by any means.
# Ensure that the system is capable of rolling back the changes if the system is not working as expected. 
# ============================================================
"""
        elif self == PGTUNER_SCOPE.DATABASE_CONFIG:
            return f"""# Read this disclaimer before applying the tuning result
# ============================================================
# {APP_NAME_UPPER}-v{__VERSION__}: The tuning is started at {dt} 
# -> Target Scope: {PGTUNER_SCOPE.DATABASE_CONFIG}
# DISCLAIMER: The kernel tuning options is based on our experience, and should not be applied directly 
# to the system. There is ZERO guarantee that this tuning guideline is the best for your system. Please 
# consult with your system administrator or database administrator or software/system delivery manager 
# before applying the tuning result.
# HOWTO: It is recommended to apply the tuning result under the /etc/postgresql/* directory or inside
# the $PGDATA/conf/* or $PGDATA/* directory depending on how you start the PostgreSQL server. In the 
# primary entry (default), remember the field 'include' is active and the corresponding directory is 
# included there. Please double check the system from the SQL interactive sessions to ensure things 
# are working as expected. Whilst it is possible to start the PostgreSQL server with the new configuration,
# it could result in lost of configuration (such as new version update, unknown configuration changes, 
# extension or external configuration from 3rd-party tools, ...), it is NOT recommended to apply the
# tuning result directly to the system without a proper backup and testing.
# Ensure that the system is capable of rolling back the changes if the system is not working as expected.
# ============================================================
"""
        return ""
