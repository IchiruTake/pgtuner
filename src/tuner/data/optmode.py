from enum import Enum

__all__ = ["PG_PROFILE_OPTMODE"]


# =============================================================================
# ENUM choices
class PG_PROFILE_OPTMODE(str, Enum):
    """
    The PostgreSQL optimization mode during workload, maintenance, logging experience for DEV/DBA,
    and probably other options.
    Note that please do not rely this tuning profile to be a single source of truth, but ignoring other form of
    allowing maximum performance and data integrity. This is just a general tuning profile that is expected to be
    safe for most cases, but not all cases. For further more, you should looking at a faster and more reliable
    disk (Enterprise-graded SSD, NVME, ...), transaction isolation level, and other factors.


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
        Regarding the performance boost, a safety margin of 5-10% is expected in the "worst" scenario (average at
        7.5%), but for the data integrity, this is usually not preferred in this mode. Please note that this mode
        allows longer duration for memory or buffer page to be flushed to the disk, risking the data integrity.

    OPTIMUS_PRIME: str = "general"
        This mode is suitable for the server with more resources, or you want to apply the general workload (which is
        also the default setting), where we would balance between the data integrity and the performance.
        Regarding the performance boost, a safety margin of 10-20% is expected in the "worst" scenario (average at 15%).
        For the data integrity, we balance these two aspects along with the performance, but still, the 100% data
        integrity may not be applied.

    PRIMORDIAL: str = "aggressive"
        This mode is suitable for the server with more resources, or you want to apply the aggressive workload with
        more focused on the data integrity.
        Regarding the performance boost, a safety margin of 20-30% is expected in the "worst" scenario (average at 25%).
        For the data integrity, we are more preferring about the data integrity over the performance. The 100% of
        data integrity is expected in this mode, but still not 100% true in the real-world.



    """
    NONE: str = "none"
    SPIDEY: str = "lightweight"
    OPTIMUS_PRIME: str = "general"
    PRIMORDIAL: str = "aggressive"

    def risk_factor_range(self) -> tuple[float, float]:
        """
        Get the risk factor of the optimization mode.
        """
        return {
            self.NONE: (0.0, 0.0),
            self.SPIDEY: (0.05, 0.10),
            self.OPTIMUS_PRIME: (0.10, 0.20),
            self.PRIMORDIAL: (0.20, 0.30),
        }[self]

    def risk_factor(self) -> float:
        """
        Get the risk factor of the optimization mode.
        """
        return round(sum(self.risk_factor_range()) / 2, 3)