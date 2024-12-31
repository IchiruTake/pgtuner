from enum import Enum

__all__ = ["PG_SCOPE"]


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
    OTHERS = "others"
