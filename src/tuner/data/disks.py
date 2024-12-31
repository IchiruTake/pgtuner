
"""


"""

import logging
from functools import partial
from typing import Any

from pydantic import BaseModel, Field, ByteSize, PositiveFloat, PositiveInt
from src.static.c_toml import LoadAppToml
from src.tuner.data.utils import FactoryForPydanticWithUserFn as PydanticFact

from src.static.vars import APP_NAME_LOWER, APP_NAME_UPPER, RANDOM_IOPS, THROUGHPUT

__all__ = ["PG_DISK_PERF"]
_SIZING = ByteSize | int | float

# =============================================================================
# This section is managed by the application. Default setup is the value of SSDv2

_logger = logging.getLogger(APP_NAME_UPPER)
_DISK_TOML: dict[str, dict[str, int]] | None = LoadAppToml()['disk']
_BASE_DEFAULT_FALLBACK = 'hddv2'
_DEFAULT_DISK_STRING_CODE = 'ssdv2'

def _string_disk_to_performance(value: str, mode: str) -> _SIZING:
    if not isinstance(value, str):
        return int(value)

    if not value.strip() or not value.strip().isnumeric():
        output = _DISK_TOML[mode][_DEFAULT_DISK_STRING_CODE]
        _logger.warning(f"The disk performance value is not a digit. Using the default value profile of disk "
                        f"{_DEFAULT_DISK_STRING_CODE} of mode {mode} -> Output: {output}.")

        return output

    try:
        return int(_DISK_TOML[mode][value])
    except KeyError:
        _logger.warning(f"The disk performance value of {value} is not found in the TOML file. "
                        f"Using the default value of {_DISK_TOML[mode][_BASE_DEFAULT_FALLBACK]}")
        return int(_DISK_TOML[mode][_BASE_DEFAULT_FALLBACK])


_string_disk_to_iops = partial(_string_disk_to_performance, mode=RANDOM_IOPS)
_string_disk_to_throughput = partial(_string_disk_to_performance, mode=THROUGHPUT)


class PG_DISK_PERF(BaseModel):
    read_random_iops_spec: _SIZING | str = (
        Field(default_factory=PydanticFact("Enter the read performance of the single disk in random IOPs metric: ",
                                           default_value=int(_DISK_TOML[RANDOM_IOPS][_DEFAULT_DISK_STRING_CODE]),
                                           user_fn=_string_disk_to_iops),
              description="The read specification of the disk performance measured as either 4 KiB (OS default) or "
                          "using 8 KiB in random IOPS metric. In Linux general, the filesystem blocksize is compiled "
                          "with 4K and change to 8 KiB may not be feasible. Since most of the time the measured IOPs "
                          "is less than the number advertised so it is best to use the 4 KiB blocksize in measurement. "
                          "Note that this setup does not pair well with heterogeneous disk type. For example, the "
                          "performance of the SATA SSD is non-comparable to the NVMe SSD. When empty capacity, reduce"
                          "this value by measurement again.",
              )
    )
    write_random_iops_spec: _SIZING | str = (
        Field(default_factory=PydanticFact("Enter the write performance of the single disk in random IOPs metric: ",
                                           default_value=int(_DISK_TOML[RANDOM_IOPS][_DEFAULT_DISK_STRING_CODE]),
                                           user_fn=_string_disk_to_iops),
              description="The write specification of the disk performance measured as either 4 KiB (OS default) or "
                          "using 8 KiB in random IOPS metric. In Linux general, the filesystem blocksize is compiled "
                          "with 4K and change to 8 KiB may not be feasible. Since most of the time the measured IOPs "
                          "is less than the number advertised so it is best to use the 4 KiB blocksize in measurement. "
                          "Note that this setup does not pair well with heterogeneous disk type. For example, the "
                          "performance of the SATA SSD is non-comparable to the NVMe SSD. When empty capacity, reduce"
                          "this value by measurement again.",
              )
    )
    random_iops_scale_factor: PositiveFloat = (
        Field(default=0.9, gt=0, le=1.0,
              description="The random IOPS scale factor of the single disk. If you provide the random IOPS performance"
                          "by benchmark (fio, CrystalDiskMark), then set this value from 0.95 to 1.0 (due to extra "
                          "overhead) from other application and kernel. For base bare metal, personal computer, or  "
                          "direct container, set this value approximately 0.9. If you host the workload over hypervisor"
                          "or container in virtualization, set this value at 0.8 to 0.85. If your disk spec is not "
                          "matched with the interface (PC at PCIe 3.0x4 and NVME PCIe 4.0x4), choose the lower value."
                          "In any case, please set up your disk host, RAID, disk pool before, then benchmark the disk "
                          "and submit your value here rather than using the manufacturer's specification.",
              )
    )

    read_throughput_spec: _SIZING | str = (
        Field(default_factory=PydanticFact("Enter the read performance of the single disk in MiB/s: ",
                                           default_value=int(_DISK_TOML[THROUGHPUT][_DEFAULT_DISK_STRING_CODE]),
                                           user_fn=_string_disk_to_throughput),
              description="The read specification of the disk performance. Its value can be random IOPS or read/write "
                          "throughput in MB/s. Note that this setup does not pair well with heterogeneous disk type. "
                          "For example, the performance of the SATA SSD is non-comparable to the NVMe SSD.",
              )
    )
    write_throughput_spec: _SIZING | str = (
        Field(default_factory=PydanticFact("Enter the write performance of the single disk in MiB/s: ",
                                           default_value=int(_DISK_TOML[THROUGHPUT][_DEFAULT_DISK_STRING_CODE]),
                                           user_fn=_string_disk_to_throughput),
              description="The write specification of the disk performance. Its value can be random IOPS or read/write "
                          "throughput in MB/s. Note that this setup does not pair well with heterogeneous disk type. "
                          "For example, the performance of the SATA SSD is non-comparable to the NVMe SSD.",
              )
    )
    throughput_scale_factor: PositiveFloat = (
        Field(default=0.9, gt=0, le=1.0,
              description="The performance scale factor of the single disk. If you provide the read/write performance"
                          "by benchmark (fio, CrystalDiskMark), then set this value from 0.95 to 1.0 (due to extra "
                          "overhead) from other application and kernel. For base bare metal, personal computer, or  "
                          "direct container, set this value approximately 0.9. If you host the workload over hypervisor"
                          "or container in virtualization, set this value at 0.8 to 0.85. If your disk spec is not "
                          "matched with the interface (PC at PCIe 3.0x4 and NVME PCIe 4.0x4), choose the lower value."
                          "In any case, please set up your disk host, RAID, disk pool before, then benchmark the disk "
                          "and submit your value here rather than using the manufacturer's specification.",
              )
    )

    # =============================================================================
    # Only use this for RAID-
    per_scale_in_raid: PositiveFloat = (
        Field(default=0.75, ge=1e-8, le=1.0,
              description="The performance scale factor of the disk system in RAID configuration. The default factor "
                          "is 0.75 means that for each disk drive added into the RAID, you can only achieve maximum "
                          "75% more of its performance and it would be degraded overtime due to the diminishing return. ",
              )
    )

    num_disks: PositiveInt = (
        Field(default=1, ge=1, lt=2 ** 6,
              description="The number of disks in the system. This is used to calculate the total performance of the "
                          "disk system, especially in RAID configuration. However, remembering the diminishing return "
                          "law based on controller bandwidth, interface bandwidth, workload characteristics, drive "
                          "performance variability, CPU overhead, RAID controller software reservations and overhead, "
                          "and so on. In general, the diminishing return law in RAID(0) is met when going beyond "
                          "4 to 6 (HDD) to 8 (SSD) drives.",
              )
    )

    def model_post_init(self, __context: Any) -> None:
        if isinstance(self.read_random_iops_spec, str):
            self.read_random_iops_spec = _string_disk_to_iops(self.read_random_iops_spec)
        if isinstance(self.write_random_iops_spec, str):
            self.write_random_iops_spec = _string_disk_to_iops(self.write_random_iops_spec)
        if isinstance(self.read_throughput_spec, str):
            self.read_throughput_spec = _string_disk_to_throughput(self.read_throughput_spec)
        if isinstance(self.write_throughput_spec, str):
            self.write_throughput_spec = _string_disk_to_throughput(self.write_throughput_spec)

        pass

    def raid_scale_factor(self) -> PositiveFloat:
        return round(max(1.0, (self.num_disks - 1) * self.per_scale_in_raid + 1.0), 2)

    def single_perf(self)  -> tuple[_SIZING, _SIZING]:
        single_throughput = min(self.read_throughput_spec, self.write_throughput_spec) * self.throughput_scale_factor
        single_random_iops = min(self.read_random_iops_spec, self.write_random_iops_spec) * self.random_iops_scale_factor
        return single_throughput, single_random_iops
