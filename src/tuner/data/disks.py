import logging
from functools import partial, cached_property
from typing import Any

from pydantic import BaseModel, Field, ByteSize, PositiveFloat, PositiveInt

from src.static.vars import APP_NAME_UPPER, RANDOM_IOPS, THROUGHPUT, Gi, Mi, DB_PAGE_SIZE
from src.tuner.data.sizing import PG_DISK_SIZING

__all__ = ['PG_DISK_PERF']
_SIZING = ByteSize | int

# =============================================================================
# This section is managed by the application. Default setup is the value of SSDv2

_logger = logging.getLogger(APP_NAME_UPPER)
def _string_disk_to_performance(value: str | int | ByteSize, mode: str) -> int | ByteSize:
    if isinstance(value, (int, ByteSize)):
        return value
    if not isinstance(value, str):
        msg = f'The disk performance value is not a string or integer.'
        _logger.error(msg)
        raise ValueError(msg)
    if value.strip().isnumeric():
        return int(value)

    # Get the disk based on its name:
    for disk in PG_DISK_SIZING:
        disk_code = disk.disk_code()
        if disk_code == value:
            return disk.iops() if mode == RANDOM_IOPS else disk.throughput()
        # If they just provide the disk code, we supply their minimum specification:
        elif disk_code.startswith(value) and disk.disk_code().endswith('v1'):
            return disk.iops() if mode == RANDOM_IOPS else disk.throughput()

    # If the disk is not found, we fallback to the default value:
    _logger.warning(f'The performance value is not found specification list of PG_DISK_SIZING. ')
    return PG_DISK_SIZING.SANv1.iops() if mode == RANDOM_IOPS else PG_DISK_SIZING.SANv1.throughput()


class PG_DISK_PERF(BaseModel):
    random_iops_spec: _SIZING | str = (
        Field(default=PG_DISK_SIZING.SANv1.iops(),
              description='The random IOPS metric of a single disk measured as either the 4 KiB page size (OS default) '
                          'or using 8 KiB as PostgreSQL block size. It is best that user should provided measured '
                          'result from the benchmark (fio, CrystalDiskMark). If you are working on NVME SSD drive, '
                          'and the performance is strongly dependent on the current disk capacity, then you should '
                          'provide it with lower value, or reduce our scale factor.',
              )
    )
    random_iops_scale_factor: PositiveFloat = (
        Field(default=0.9, gt=0, le=1.0,
              description='The random IOPS scale factor of the single disk. If you provide the random IOPS performance'
                          'by benchmark (fio, CrystalDiskMark), then set this value from 0.95 to 1.0 (due to extra '
                          'overhead) from other application and kernel. For base bare metal, personal computer, or  '
                          'direct container, set this value approximately 0.9. If you host the workload over hypervisor'
                          'or container in virtualization, set this value at 0.8 to 0.85. If your disk spec is not '
                          'matched with the interface (PC at PCIe 3.0x4 and NVME PCIe 4.0x4), choose the lower value.'
                          'In any case, please set up your disk host, RAID, disk pool before, then benchmark the disk '
                          'and submit your value here rather than using the manufacturers specification.',
              )
    )
    throughput_spec: _SIZING | str = (
        Field(default=PG_DISK_SIZING.SANv1.throughput(),
              description='The read specification of the disk performance. Its value can be random IOPS or read/write '
                          'throughput in MiB/s. Note that this setup does not pair well with heterogeneous disk type. '
                          'For example, the performance of the SATA SSD is non-comparable to the NVMe SSD.',
              )
    )
    throughput_scale_factor: PositiveFloat = (
        Field(default=0.9, gt=0, le=1.0,
              description='The performance scale factor of the single disk. If you provide the read/write performance'
                          'by benchmark (fio, CrystalDiskMark), then set this value from 0.95 to 1.0 (due to extra '
                          'overhead) from other application and kernel. For base bare metal, personal computer, or '
                          'direct container, set this value approximately 0.9. If you host the workload over hypervisor'
                          'or container in virtualization, set this value at 0.8 to 0.85. If your disk spec is not '
                          'matched with the interface (PC at PCIe 3.0x4 and NVME PCIe 4.0x4), choose the lower value.'
                          'In any case, please set up your disk host, RAID, disk pool before, then benchmark the disk '
                          'and submit your value here rather than using the manufacturer specification.',
              )
    )

    # =============================================================================
    # Only use this for RAID-
    per_scale_in_raid: PositiveFloat = (
        Field(default=0.75, ge=0.0, le=1.0,
              description='The performance scale factor of the disk system in RAID configuration. The default factor '
                          'is 0.75 means that for each disk drive added into the RAID, you can only achieve maximum '
                          '75% more of its performance and it would be degraded overtime due to the diminishing return. ',
              )
    )

    num_disks: PositiveInt = (
        Field(default=1, ge=1, le=24,
              description='The number of disks in the system. This is used to calculate the total performance of the '
                          'disk system, especially in RAID configuration. However, remembering the diminishing return '
                          'law based on controller bandwidth, interface bandwidth, workload characteristics, drive '
                          'performance variability, CPU overhead, RAID controller software reservations and overhead, '
                          'and so on. In general, the diminishing return law in RAID(0) is met when going beyond '
                          '4 to 6 (HDD) to 8 (SSD) drives.',
              )
    )
    disk_usable_size: PositiveInt = (
        Field(default=20 * Gi, ge=5 * Gi,
              description='The usable size of the disk system (in bytes). The supported value must be larger than 5 '
                          'GiB. Default to be 20 GiB (followed by Azure minimum strategy) (ignored the reserved space '
                          'for the OS filesystem and round-down the number).',
              )
    )

    def model_post_init(self, __context: Any) -> None:
        if isinstance(self.random_iops_spec, str):
            self.random_iops_spec = _string_disk_to_performance(self.random_iops_spec, mode=RANDOM_IOPS)
        if isinstance(self.throughput_spec, str):
            self.throughput_spec = _string_disk_to_performance(self.throughput_spec, mode=THROUGHPUT)
        pass

    @cached_property
    def raid_scale_factor(self) -> PositiveFloat:
        return round(max(1.0, (self.num_disks - 1) * self.per_scale_in_raid + 1.0), 2)

    @cached_property
    def single_perf(self) -> tuple[_SIZING, _SIZING]:
        s_tput = int(self.throughput_spec * self.throughput_scale_factor)
        s_iops = int(self.random_iops_spec * self.random_iops_scale_factor)
        return s_tput, s_iops

    def perf(self) -> tuple[_SIZING, _SIZING]:
        raid_scale_factor = self.raid_scale_factor
        s_tput, s_iops = self.single_perf
        # Add fastpath when number of disk/raid_scale_factor == 1 ???
        return int(s_tput * raid_scale_factor), int(s_iops * raid_scale_factor)

    @staticmethod
    def iops_to_throughput(iops: int) -> int | float:
        # IOPS -> Measured by number of 8 KiB blocks
        # Throughput -> Measured in MiB or MiB/s
        return iops * DB_PAGE_SIZE / Mi

    @staticmethod
    def throughput_to_iops(throughput: int | float) -> int | float:
        # IOPS -> Measured by number of 8 KiB blocks
        # Throughput -> Measured in MiB or MiB/s
        return throughput * (Mi // DB_PAGE_SIZE)