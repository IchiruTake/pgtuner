from enum import Enum
from functools import total_ordering

__all__ = ["PG_PROFILE_OPTMODE", "PG_BACKUP_TOOL"]


# =============================================================================
# ENUM choices
class PG_PROFILE_OPTMODE(str, Enum):
    """
    The PostgreSQL optimization mode during workload, maintenance, logging experience for DEV/DBA, and probably other
    options. Note that please do not rely on this tuning profile to be a single source of truth, but ignoring other
    forms of allowing maximum performance and data integrity.

    Parameters:
    ----------

    NONE: str = "none"
        This mode would bypass the second phase of the tuning process and just apply the general tuning. Note that
        if set to this mode, if our preset turns out to be wrong and not suit with your server, no adjustment on the
        tuning is made.

    SPIDEY: str = "lightweight"
        This mode is suitable for the server with limited resources, or you just want to apply the easiest basic
        workload optimization profile on your server that is expected to be safe for most cases. Please note that there
        is no guarantee that this mode is safe for all cases, and no guarantee that this mode brings the best
        performance as compared to the other modes.

    OPTIMUS_PRIME: str = "general"
        This mode is suitable for the server with more resources, or you want to apply the general workload (which is
        also the default setting), where we would balance between the data integrity and the performance.

    PRIMORDIAL: str = "aggressive"
        This mode is suitable for the server with more resources, or you want to apply the aggressive workload with
        more focused on the data integrity.

    """
    NONE: str = "none"
    SPIDEY: str = "lightweight"
    OPTIMUS_PRIME: str = "general"
    PRIMORDIAL: str = "aggressive"

    @staticmethod
    def profile_ordering() -> tuple[str, ...]:
        return (PG_PROFILE_OPTMODE.NONE, PG_PROFILE_OPTMODE.SPIDEY, PG_PROFILE_OPTMODE.OPTIMUS_PRIME,
                PG_PROFILE_OPTMODE.PRIMORDIAL)

# =============================================================================
@total_ordering
class PG_BACKUP_TOOL(Enum):
    DISK_SNAPSHOT = 'Backup by Disk Snapshot'
    PG_DUMP = 'pg_dump/pg_dumpall: Textual backup'
    PG_BASEBACKUP = 'pg_basebackup [--incremental] or streaming replication (byte-capture change): Byte-level backup'
    PG_LOGICAL = 'pg_logical and alike: Logical replication'

    @classmethod
    def __missing__(cls, key):
        if isinstance(key, str):
            k = key.strip().lower()
            match k:
                case 'disk_snapshot':
                    return PG_BACKUP_TOOL.DISK_SNAPSHOT
                case 'pg_dump':
                    return PG_BACKUP_TOOL.PG_DUMP
                case 'pg_basebackup':
                    return PG_BACKUP_TOOL.PG_BASEBACKUP
                case 'pg_logical':
                    return PG_BACKUP_TOOL.PG_LOGICAL
                case _:
                    raise ValueError(f'Unknown backup tool: {key}')
        elif isinstance(key, int):
            if key < 0 or key >= len(cls):
                raise ValueError(f'Unknown backup tool: {key}')
            return list(cls)[key]
        return super()._missing_(key)

