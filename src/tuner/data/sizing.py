from enum import Enum
from functools import lru_cache
from math import floor, ceil
from typing import Literal

from src.utils.static import K10, THROUGHPUT

__all__ = ['PG_DISK_SIZING']

# -----------------------------------------------------------------------------
## Note that in the list, we choose the value based on the minimum of read/write IOPS/throughput, and doing
## some averaging across value (and smally reduce the number); so the value here may not be reflected on your disk
## storage. But thinking about disk degradation after time and other factor. Thus to make use of this, it is best to
## choose based on the nearest value of minimum of read/write IOPS/throughput and round down (not up).

## These values are gained from TechPowerUp's SSD IOPS Database.
## Please note that the naming model with suffix _v1, _v2, _v3, etc. is used to differentiate the IOPS value based on
## the read/write ratio, rather than the comparison of the disk itself. Also, we don't take into the consideration of
## DRAM-availability on the SSD as we are focusing on the disk read/write after (p)SLC cache is full and not full.
## For NVME drive, when pseudo-SLC cache is full, unless you are using too small drive such as 128 GB or 256 GB, or flaw
## SSD with corrupted pSLC, or the drive is nearly full (80% full) the drive could write as around 60-80% of the
## throughput provided by the manufacturer

## For random IOPS or throughput metric, we never achieve their advertised value due to the noise, external conditions,
## but importantly the OS or driver operations, and the page-size of the I/O request. For example, the WD SN770 1 TiB
## NVME PCIe 4.0x4 has 740k IOPs read and 800k IOPs write, but measurement shows on 4K request as data disk that it
## could achieve maximum 180K IOPs and 125K - 155K for mixed read/write (50% - 99%) at 80% full capacity. Please note
## that SSD performance is degraded overtime when the drive capacity is running out due to usage, so it is best
## not to use the advertised value

class PG_DISK_SIZING(Enum):
    """
    This class contains the PostgreSQL disk sizing profile (taken from bare-metal server, not virtualized server).
    First value is the disk code
    Second value is the throughput in sequential read/write in MiB/s
    Third value is the number of IOPS in random read/write

    """
    # SATA HDDs
    HDDv1 = ('hddv1', 100, 250)     # Some old HDDs or SD cards (efficiency around 80 - 120 MiB/s)
    HDDv2 = ('hddv2', 200, 1 *K10)
    HDDv3 = ('hddv3', 260, 2500)    # Some Western Digital HDDs, or modern HDDs with small SSD/DRAM cache (220 - 290 MiB/s)

    # SAN/NAS SSDs
    SANv1 = ('sanv1', 300, 5 * K10)
    SANv2 = ('sanv2', 330, 8 * K10)
    SANv3 = ('sanv3', 370, 12 * K10)
    SANv4 = ('sanv4', 400, 16 * K10)

    # SATA SSDs (Local)
    SSDv1 = ('ssdv1', 450, 20 * K10)
    SSDv2 = ('ssdv2', 500, 30 * K10)
    SSDv3 = ('ssdv3', 533, 40 * K10)
    SSDv4 = ('ssdv4', 566, 50 * K10)
    SSDv5 = ('ssdv5', 600, 60 * K10)

    # Remote NVMe SSD (Usually the NVMe Box)
    NVMeBOXv1 = ('nvmeboxv1', 800, 80 * K10)
    NVMeBOXv2 = ('nvmeboxv2', 1000, 100 * K10)
    NVMeBOXv3 = ('nvmeboxv3', 1400, 120 * K10)
    NVMeBOXv4 = ('nvmeboxv4', 1700, 140 * K10)

    # We don't make custom value of NVME SSD such as PCIe 3.0/4.0 x8 or 3.0/4.0 x16, as it's extremely rare to nothing.
    # NVMe PCIe Gen 3 SSDs
    NVMePCIev3x4v1 = ('nvmepciev3x4v1', 2000, 150 * K10)
    NVMePCIev3x4v2 = ('nvmepciev3x4v2', 2500, 200 * K10)
    NVMePCIev3x4v3 = ('nvmepciev3x4v3', 3000, 250 * K10)
    NVMePCIev3x4v4 = ('nvmepciev3x4v4', 3500, 300 * K10)
    NVMePCIev3x4v5 = ('nvmepciev3x4v5', 4000, 350 * K10)
    NVMePCIev3x4v6 = ('nvmepciev3x4v6', 4500, 400 * K10)
    # NVMe PCIe Gen 4 SSDs
    NVMePCIev4x4v1 = ('nvmepciev4x4v1', 4500, 300 * K10)
    NVMePCIev4x4v2 = ('nvmepciev4x4v2', 5000, 375 * K10)
    NVMePCIev4x4v3 = ('nvmepciev4x4v3', 5500, 450 * K10)
    NVMePCIev4x4v4 = ('nvmepciev4x4v4', 6000, 525 * K10)
    NVMePCIev4x4v5 = ('nvmepciev4x4v5', 6500, 600 * K10)
    NVMePCIev4x4v6 = ('nvmepciev4x4v6', 7000, 700 * K10)
    # NVMe PCIe Gen 5 SSDs
    NVMePCIev5x4v1 = ('nvmepciev5x4v1', 7000, 750 * K10)
    NVMePCIev5x4v2 = ('nvmepciev5x4v2', 8500, 850 * K10)
    NVMePCIev5x4v3 = ('nvmepciev5x4v3', 9500, 950 * K10)
    NVMePCIev5x4v4 = ('nvmepciev5x4v4', 11000, 1100 * K10)
    NVMePCIev5x4v5 = ('nvmepciev5x4v5', 12500, 1250 * K10)
    NVMePCIev5x4v6 = ('nvmepciev5x4v6', 14000, 1400 * K10)

    @staticmethod
    @lru_cache(maxsize=1)
    def _disk_type_list_v1() -> list[str]:
        return ['hdd', 'san', 'ssd', 'nvmebox', 'nvmepciev3', 'nvmepciev4', 'nvmepciev5']

    @staticmethod
    @lru_cache(maxsize=1)
    def _disk_type_list_v2() -> list[str]:
        return ['hdd', 'san', 'ssd', 'nvmebox', 'nvmepciev3', 'nvmepciev4', 'nvmepciev5', 'nvmepcie', 'nvme']

    def disk_code(self) -> str:
        return self.value[0]

    def throughput(self) -> int:
        return self.value[1]

    def iops(self) -> int:
        return self.value[2]

    def _check_disk_type(self, disk_type: str) -> bool:
        disk_type = disk_type.lower()
        if disk_type not in PG_DISK_SIZING._disk_type_list_v2():
            raise ValueError(f'Disk type {disk_type} is not available')
        return self.disk_code().startswith(disk_type)

    @staticmethod
    @lru_cache(maxsize=32)
    def _list(disk_type: str | None, performance_type: str | None = None) -> list['PG_DISK_SIZING']:
        result = [disk for disk in PG_DISK_SIZING if disk_type is None or disk._check_disk_type(disk_type)]
        if performance_type is not None:
            fn = lambda x: (x.throughput(), x.iops()) if performance_type == THROUGHPUT else (x.iops(), x.throughput())
            result.sort(key=fn, reverse=False)
        return result

    @staticmethod
    def _find_midpoints(disks: list['PG_DISK_SIZING'], performance_type: str) -> int | float:
        midpoint, remainder = divmod(len(disks), 2)
        # For even number of disks, we choose between two disks
        if remainder == 0:
            tmp_disk01 = disks[midpoint - 1]
            tmp_disk02 = disks[midpoint]
            if performance_type == THROUGHPUT:
                spec = (tmp_disk01.throughput() + tmp_disk02.throughput()) / 2
            else:
                spec = (tmp_disk01.iops() + tmp_disk02.iops()) / 2
        else:
            if performance_type == THROUGHPUT:
                spec = disks[midpoint + remainder].throughput()
            else:
                spec = disks[midpoint + remainder].iops()
        return spec

    # Maximum number of cache entry (if just int) is 2 * (num_type_of_disk * 2) ^ 2
    # But we never reach that. The current codebase (Jan 28th 2025 said we only have 13 entries only).
    # So for future-proof, we would use 32 as the maximum cache entry
    @staticmethod
    @lru_cache(maxsize=32)
    def _get_bound(performance_type: str, disk_01: 'PG_DISK_SIZING', disk_02: 'PG_DISK_SIZING') -> tuple[int, int]:
        """
        This function try to get the upper and lower bound for comparison. Designed to leverage the lru_cache
        caching mechanism.

        Arguments:
        ---------

        performance_type: str
            The performance type, either THROUGHPUT or RANDOM_IOPS

        disk_01: PG_DISK_SIZING | int | float
            The first disk or the performance value. If the input is numeric, we used it as the definite bound with
            no resizing.

        disk_02: PG_DISK_SIZING | int | float
            The second disk or the performance value. If the input is numeric, we used it as the definite bound with
            no resizing.

        Returns:
        -------

        tuple[int, int]
            The lower and upper bound for comparison
        """
        _disk_table = PG_DISK_SIZING._list(disk_type=None, performance_type=performance_type)
        if isinstance(disk_01, PG_DISK_SIZING):
            disk01_index = _disk_table.index(disk_01)
            prev_disk01 = _disk_table[max(0, disk01_index - 1)]
            # Deal when no weaker disk
            if disk_01 == prev_disk01:
                lower_bound = 0
            elif performance_type == THROUGHPUT:
                lower_bound = (disk_01.throughput() + prev_disk01.throughput()) / 2
            else:
                lower_bound = (disk_01.iops() + prev_disk01.iops()) / 2
        else:
            lower_bound = disk_01

        if isinstance(disk_02, PG_DISK_SIZING):
            disk02_index = _disk_table.index(disk_02)
            latt_disk02 = _disk_table[min(len(_disk_table) - 1, disk02_index + 1)]
            # Deal when no stronger disk
            if disk_02 == latt_disk02:
                # Any positive number larger than 1
                upper_bound = 2 * (disk_02.throughput() if performance_type == THROUGHPUT else disk_02.iops())
            elif performance_type == THROUGHPUT:
                upper_bound = (disk_02.throughput() + latt_disk02.throughput()) / 2
            else:
                upper_bound = (disk_02.iops() + latt_disk02.iops()) / 2
        else:
            upper_bound = disk_02

        # Swap if the lower bound is greater than the upper bound
        if upper_bound < lower_bound:
            lower_bound, upper_bound = upper_bound, lower_bound

        return floor(lower_bound), ceil(upper_bound)

    @staticmethod
    def match_between(performance: int, performance_type: str, disk_01: 'PG_DISK_SIZING',
                      disk_02: 'PG_DISK_SIZING') -> bool:
        # Fill the gap when the expected disk is strong (probably when we allowed higher disk performance)
        # but the disk here is not available
        _disk_table = PG_DISK_SIZING._list(disk_type=None, performance_type=performance_type)
        if performance_type == THROUGHPUT and performance >= _disk_table[-1].throughput():
            return True
        elif performance_type != THROUGHPUT and performance >= _disk_table[-1].iops():
            return True

        lower_bound, upper_bound = PG_DISK_SIZING._get_bound(performance_type, disk_01, disk_02)
        return lower_bound <= performance < upper_bound

    @staticmethod
    def match_disk_series(performance: int, performance_type: str, disk_type: str,
                          interval: Literal['all', 'weak', 'strong'] = 'all') -> bool:
        disks = PG_DISK_SIZING._list(disk_type, performance_type)
        if not disks:
            raise ValueError(f'No disk type found when matching {disk_type}')
        if interval == 'all':
            return PG_DISK_SIZING.match_between(performance, performance_type, disks[0], disks[-1])

        middle_specification = PG_DISK_SIZING._find_midpoints(disks, performance_type=performance_type)
        pairs = (disks[0], middle_specification) if interval == 'weak' else (middle_specification, disks[-1])
        return PG_DISK_SIZING.match_between(performance, performance_type, *pairs)

    @staticmethod
    def match_one_disk(performance: int, performance_type: str, disk: 'PG_DISK_SIZING') -> bool:
        return PG_DISK_SIZING.match_between(performance, performance_type, disk_01=disk, disk_02=disk)

    @staticmethod
    def match_disk_series_in_range(performance: int, performance_type: str, disk01_type: str, disk02_type: str) -> bool:
        # Check if we are in between the transition between two disks
        if disk01_type == disk02_type:
            return PG_DISK_SIZING.match_disk_series(performance, performance_type, disk_type=disk01_type)

        disk01s = PG_DISK_SIZING._list(disk01_type, performance_type)
        disk02s = PG_DISK_SIZING._list(disk02_type, performance_type)

        if not disk01s or not disk02s:
            raise ValueError(f'No disk type found when matching {disk01_type} and {disk02_type}')

        disk_collection = [disk01s[0], disk01s[-1], disk02s[0], disk02s[-1]]
        fn = lambda x: (x.throughput(), x.iops()) if performance_type == THROUGHPUT else (x.iops(), x.throughput())
        disk_collection.sort(key=fn, reverse=False)
        return PG_DISK_SIZING.match_between(performance, performance_type, disk_01=disk_collection[0],
                                            disk_02=disk_collection[-1])


