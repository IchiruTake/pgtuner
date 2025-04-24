// --------------------------------------------------------------------------
import { K10, THROUGHPUT } from '../../static/vars.js';

// -------------------------------------------------------------
// ENUM choices
const SIZE_PROFILE = ['mini', 'medium', 'large', 'mall', 'bigt'];
const _ascending_specs = {
    size: SIZE_PROFILE,
    vcpu_min: [1, 2, 6, 12, 32],
    vcpu_max: [4, 8, 16, 48, 128],
    ram_gib_min: [2, 8, 24, 48, 128],
    ram_gib_max: [16, 32, 64, 192, 512],
    storage_gib_max: [50, 300, 1024, 5120, 32768],
    network_mbps_max: [500, 1000, 5000, 12500, 30000],
};
function _str_to_num(value) {
    return _ascending_specs.size.indexOf(value);
}

// --------------------------------------------------------------
// PG_SIZING: Represents a PostgreSQL sizing profile
class PG_SIZING {
    constructor(value) {
        this.value = value; // one of 'mini', 'medium', etc.
    }

    num() {
        return _str_to_num(this.value);
    }

    lt(other) {
        return this.num() < other.num();
    }

    eq(other) {
        return this.num() === other.num();
    }
}

// Define the PG_SIZING enum members
PG_SIZING.MINI = new PG_SIZING(SIZE_PROFILE[0]);
PG_SIZING.MEDIUM = new PG_SIZING(SIZE_PROFILE[1]);
PG_SIZING.LARGE = new PG_SIZING(SIZE_PROFILE[2]);
PG_SIZING.MALL = new PG_SIZING(SIZE_PROFILE[3]);
PG_SIZING.BIGT = new PG_SIZING(SIZE_PROFILE[4]);

// ----------------------------------------------------------------
// PG_DISK_SIZING: Represents a PostgreSQL disk sizing profile
class PG_DISK_SIZING {
    constructor(code, throughput, iops) {
        this._code = code;
        this._throughput = throughput;
        this._iops = iops;
    }

    diskCode() {
        return this._code;
    }

    throughput() {
        return this._throughput;
    }

    iops() {
        return this._iops;
    }

    _checkDiskType(diskType) {
        const dt = diskType.toLowerCase();
        if (!PG_DISK_SIZING._diskTypeListV2().includes(dt)) {
            throw new Error(`Disk type ${dt} is not available`);
        }
        return this._code.startsWith(dt);
    }

    // Static helper methods and caching
    static _diskTypeListV1() {
        return ['hdd', 'san', 'ssd', 'nvmebox', 'nvmepciev3', 'nvmepciev4', 'nvmepciev5'];
    }

    static _diskTypeListV2() {
        return ['hdd', 'san', 'ssd', 'nvmebox', 'nvmepciev3', 'nvmepciev4', 'nvmepciev5', 'nvmepcie', 'nvme'];
    }

    static _all() {
        return PG_DISK_SIZING.ALL;
    }

    static _list(diskType = null, performanceType = null) {
        let result = PG_DISK_SIZING._all().filter(disk => {
            return diskType === null || disk._checkDiskType(diskType);
        });
        if (performanceType !== null) {
            const keyFn = performanceType === THROUGHPUT ?
                (d) => [d.throughput(), d.iops()] :
                (d) => [d.iops(), d.throughput()];
            result.sort((a, b) => {
                const ka = keyFn(a), kb = keyFn(b);
                return ka[0] - kb[0] || ka[1] - kb[1];
            });
        }
        return result;
    }

    static _findMidpoints(disks, performanceType) {
        const len = disks.length;
        const midpoint = Math.floor(len / 2);
        if (len % 2 === 0) {
            const disk1 = disks[midpoint - 1];
            const disk2 = disks[midpoint];
            return performanceType === THROUGHPUT ?
                (disk1.throughput() + disk2.throughput()) / 2 :
                (disk1.iops() + disk2.iops()) / 2;
        } else {
            const disk = disks[midpoint];
            return performanceType === THROUGHPUT ? disk.throughput() : disk.iops();
        }
    }

    static _getBound(performanceType, disk01, disk02) {
        const diskTable = PG_DISK_SIZING._list(null, performanceType);
        let lowerBound;
        if (disk01 instanceof PG_DISK_SIZING) {
            const idx = diskTable.indexOf(disk01);
            const prev = idx > 0 ? diskTable[idx - 1] : disk01;
            lowerBound = disk01 === prev ? 0 :
                (performanceType === THROUGHPUT ?
                    (disk01.throughput() + prev.throughput()) / 2 :
                    (disk01.iops() + prev.iops()) / 2);
        } else {
            lowerBound = disk01;
        }

        let upperBound;
        if (disk02 instanceof PG_DISK_SIZING) {
            const idx = diskTable.indexOf(disk02);
            const next = idx < diskTable.length - 1 ? diskTable[idx + 1] : disk02;
            upperBound = disk02 === next ?
                2 * (performanceType === THROUGHPUT ? disk02.throughput() : disk02.iops()) :
                (performanceType === THROUGHPUT ?
                    (disk02.throughput() + next.throughput()) / 2 :
                    (disk02.iops() + next.iops()) / 2);
        } else {
            upperBound = disk02;
        }

        if (upperBound < lowerBound) {
            [lowerBound, upperBound] = [upperBound, lowerBound];
        }

        return [Math.floor(lowerBound), Math.ceil(upperBound)];
    }

    static matchBetween(performance, performanceType, disk01, disk02) {
        const diskTable = PG_DISK_SIZING._list(null, performanceType);
        const lastDisk = diskTable[diskTable.length - 1];
        if (performanceType === THROUGHPUT && performance >= lastDisk.throughput()) {
            return true;
        } else if (performanceType !== THROUGHPUT && performance >= lastDisk.iops()) {
            return true;
        }
        const [lowerBound, upperBound] = PG_DISK_SIZING._getBound(performanceType, disk01, disk02);
        return performance >= lowerBound && performance < upperBound;
    }

    static matchDiskSeries(performance, performanceType, diskType, interval = 'all') {
        const disks = PG_DISK_SIZING._list(diskType, performanceType);
        if (!disks.length) {
            throw new Error(`No disk type found when matching ${diskType}`);
        }
        if (interval === 'all') {
            return PG_DISK_SIZING.matchBetween(performance, performanceType, disks[0], disks[disks.length - 1]);
        }
        if (interval === 'weak') {
            return PG_DISK_SIZING.matchBetween(performance, performanceType, disks[0], disks[Math.floor(disks.length / 2)]);
        } else { // 'strong'
            return PG_DISK_SIZING.matchBetween(performance, performanceType, disks[Math.floor(disks.length / 2)], disks[disks.length - 1]);
        }
    }

    static matchOneDisk(performance, performanceType, disk) {
        return PG_DISK_SIZING.matchBetween(performance, performanceType, disk, disk);
    }

    static matchDiskSeriesInRange(performance, performanceType, disk01Type, disk02Type) {
        if (disk01Type === disk02Type) {
            return PG_DISK_SIZING.matchDiskSeries(performance, performanceType, disk01Type);
        }
        const disk01s = PG_DISK_SIZING._list(disk01Type, performanceType);
        const disk02s = PG_DISK_SIZING._list(disk02Type, performanceType);
        if (!disk01s.length || !disk02s.length) {
            throw new Error(`No disk type found when matching ${disk01Type} and ${disk02Type}`);
        }
        const diskCollection = [
            disk01s[0],
            disk01s[disk01s.length - 1],
            disk02s[0],
            disk02s[disk02s.length - 1]
        ];
        const sortFn = performanceType === THROUGHPUT ?
            (a, b) => a.throughput() - b.throughput() || a.iops() - b.iops() :
            (a, b) => a.iops() - b.iops() || a.throughput() - b.throughput();
        diskCollection.sort(sortFn);
        return PG_DISK_SIZING.matchBetween(performance, performanceType, diskCollection[0], diskCollection[diskCollection.length - 1]);
    }
}

// Define the PG_DISK_SIZING enum members
// SATA HDDs
PG_DISK_SIZING.HDDv1 = new PG_DISK_SIZING('hddv1', 100, 250);
PG_DISK_SIZING.HDDv2 = new PG_DISK_SIZING('hddv2', 200, K10);
PG_DISK_SIZING.HDDv3 = new PG_DISK_SIZING('hddv3', 260, 2500);

// SAN/NAS SSDs
PG_DISK_SIZING.SANv1 = new PG_DISK_SIZING('sanv1', 300, 5 * K10);
PG_DISK_SIZING.SANv2 = new PG_DISK_SIZING('sanv2', 330, 8 * K10);
PG_DISK_SIZING.SANv3 = new PG_DISK_SIZING('sanv3', 370, 12 * K10);
PG_DISK_SIZING.SANv4 = new PG_DISK_SIZING('sanv4', 400, 16 * K10);

// SATA SSDs (Local)
PG_DISK_SIZING.SSDv1 = new PG_DISK_SIZING('ssdv1', 450, 20 * K10);
PG_DISK_SIZING.SSDv2 = new PG_DISK_SIZING('ssdv2', 500, 30 * K10);
PG_DISK_SIZING.SSDv3 = new PG_DISK_SIZING('ssdv3', 533, 40 * K10);
PG_DISK_SIZING.SSDv4 = new PG_DISK_SIZING('ssdv4', 566, 50 * K10);
PG_DISK_SIZING.SSDv5 = new PG_DISK_SIZING('ssdv5', 600, 60 * K10);

// Remote NVMe SSD (Usually the NVMe Box)
PG_DISK_SIZING.NVMeBOXv1 = new PG_DISK_SIZING('nvmeboxv1', 800, 80 * K10);
PG_DISK_SIZING.NVMeBOXv2 = new PG_DISK_SIZING('nvmeboxv2', 1000, 100 * K10);
PG_DISK_SIZING.NVMeBOXv3 = new PG_DISK_SIZING('nvmeboxv3', 1400, 120 * K10);
PG_DISK_SIZING.NVMeBOXv4 = new PG_DISK_SIZING('nvmeboxv4', 1700, 140 * K10);

// NVMe PCIe Gen 3 SSDs
PG_DISK_SIZING.NVMePCIev3x4v1 = new PG_DISK_SIZING('nvmepciev3x4v1', 2000, 150 * K10);
PG_DISK_SIZING.NVMePCIev3x4v2 = new PG_DISK_SIZING('nvmepciev3x4v2', 2500, 200 * K10);
PG_DISK_SIZING.NVMePCIev3x4v3 = new PG_DISK_SIZING('nvmepciev3x4v3', 3000, 250 * K10);
PG_DISK_SIZING.NVMePCIev3x4v4 = new PG_DISK_SIZING('nvmepciev3x4v4', 3500, 300 * K10);
PG_DISK_SIZING.NVMePCIev3x4v5 = new PG_DISK_SIZING('nvmepciev3x4v5', 4000, 350 * K10);
PG_DISK_SIZING.NVMePCIev3x4v6 = new PG_DISK_SIZING('nvmepciev3x4v6', 4500, 400 * K10);

// NVMe PCIe Gen 4 SSDs
PG_DISK_SIZING.NVMePCIev4x4v1 = new PG_DISK_SIZING('nvmepciev4x4v1', 4500, 300 * K10);
PG_DISK_SIZING.NVMePCIev4x4v2 = new PG_DISK_SIZING('nvmepciev4x4v2', 5000, 375 * K10);
PG_DISK_SIZING.NVMePCIev4x4v3 = new PG_DISK_SIZING('nvmepciev4x4v3', 5500, 450 * K10);
PG_DISK_SIZING.NVMePCIev4x4v4 = new PG_DISK_SIZING('nvmepciev4x4v4', 6000, 525 * K10);
PG_DISK_SIZING.NVMePCIev4x4v5 = new PG_DISK_SIZING('nvmepciev4x4v5', 6500, 600 * K10);
PG_DISK_SIZING.NVMePCIev4x4v6 = new PG_DISK_SIZING('nvmepciev4x4v6', 7000, 700 * K10);

// NVMe PCIe Gen 5 SSDs
PG_DISK_SIZING.NVMePCIev5x4v1 = new PG_DISK_SIZING('nvmepciev5x4v1', 7000, 750 * K10);
PG_DISK_SIZING.NVMePCIev5x4v2 = new PG_DISK_SIZING('nvmepciev5x4v2', 8500, 850 * K10);
PG_DISK_SIZING.NVMePCIev5x4v3 = new PG_DISK_SIZING('nvmepciev5x4v3', 9500, 950 * K10);
PG_DISK_SIZING.NVMePCIev5x4v4 = new PG_DISK_SIZING('nvmepciev5x4v4', 11000, 1100 * K10);
PG_DISK_SIZING.NVMePCIev5x4v5 = new PG_DISK_SIZING('nvmepciev5x4v5', 12500, 1250 * K10);
PG_DISK_SIZING.NVMePCIev5x4v6 = new PG_DISK_SIZING('nvmepciev5x4v6', 14000, 1400 * K10);

// Populate ALL list
PG_DISK_SIZING.ALL = [
    PG_DISK_SIZING.HDDv1, PG_DISK_SIZING.HDDv2, PG_DISK_SIZING.HDDv3,
    PG_DISK_SIZING.SANv1, PG_DISK_SIZING.SANv2, PG_DISK_SIZING.SANv3, PG_DISK_SIZING.SANv4,
    PG_DISK_SIZING.SSDv1, PG_DISK_SIZING.SSDv2, PG_DISK_SIZING.SSDv3, PG_DISK_SIZING.SSDv4, PG_DISK_SIZING.SSDv5,
    PG_DISK_SIZING.NVMeBOXv1, PG_DISK_SIZING.NVMeBOXv2, PG_DISK_SIZING.NVMeBOXv3, PG_DISK_SIZING.NVMeBOXv4,
    PG_DISK_SIZING.NVMePCIev3x4v1, PG_DISK_SIZING.NVMePCIev3x4v2, PG_DISK_SIZING.NVMePCIev3x4v3,
    PG_DISK_SIZING.NVMePCIev3x4v4, PG_DISK_SIZING.NVMePCIev3x4v5, PG_DISK_SIZING.NVMePCIev3x4v6,
    PG_DISK_SIZING.NVMePCIev4x4v1, PG_DISK_SIZING.NVMePCIev4x4v2, PG_DISK_SIZING.NVMePCIev4x4v3,
    PG_DISK_SIZING.NVMePCIev4x4v4, PG_DISK_SIZING.NVMePCIev4x4v5, PG_DISK_SIZING.NVMePCIev4x4v6,
    PG_DISK_SIZING.NVMePCIev5x4v1, PG_DISK_SIZING.NVMePCIev5x4v2, PG_DISK_SIZING.NVMePCIev5x4v3,
    PG_DISK_SIZING.NVMePCIev5x4v4, PG_DISK_SIZING.NVMePCIev5x4v5, PG_DISK_SIZING.NVMePCIev5x4v6,
];

export { PG_DISK_SIZING, PG_SIZING, SIZE_PROFILE };
