// ==================================================================================
/**
 * Original Source File: ./src/tuner/profile/database/shared.py
 * This module is to perform specific tuning and calculation on the PostgreSQL database server.
 */

// The time required to create, opened and close a file. This has been tested with all disk cache flushed,
// Windows (NTFS) and Linux (EXT4/XFS) on i7-8700H with Python 3.12 on NVMEv3 SSD and old HDD
const _FILE_ROTATION_TIME_MS = 0.21 * 2  // 0.21 ms on average when direct bare-metal, 2-3x on virtualized (0.72-0.75ms tested on GCP VM)
const _DISK_ZERO_SPEED = 2.5 * Ki        // The speed of creating a zero-filled file, measured by MiB/s
function wal_time(wal_buffers, data_amount_ratio, wal_segment_size, wal_writer_delay_in_ms, wal_throughput) {
    // The time required to flush the full WAL buffers to disk (assuming we have no write after the flush)
    // or wal_writer_delay is being woken up or 2x of wal_buffers are synced
    console.debug('Estimate the time required to flush the full WAL buffers to disk');
    const data_amount = Math.floor(wal_buffers * data_amount_ratio);
    const num_wal_files_required = Math.floor(data_amount / wal_segment_size) + 1;
    const rotate_time_in_ms = num_wal_files_required * (_FILE_ROTATION_TIME_MS + _DISK_ZERO_SPEED / (wal_segment_size / Mi) * K10);
    const write_time_in_ms = (data_amount / Mi) / wal_throughput * K10;

    // Calculate maximum how many delay time
    let delay_time = 0;
    if (data_amount_ratio > 1) {
        let num_delay = Math.floor(data_amount_ratio);
        const fractional = data_amount_ratio - num_delay;
        if (fractional === 0) {
            num_delay -= 1;
        }
        delay_time = num_delay * wal_writer_delay_in_ms;
    }
    const total_time = rotate_time_in_ms + write_time_in_ms + delay_time;
    const msg = `Estimate the time required to flush the full-queued WAL buffers ${bytesize_to_hr(data_amount)} to disk: rotation time: ${rotate_time_in_ms.toFixed(2)} ms, write time: ${write_time_in_ms.toFixed(2)} ms, delay time: ${delay_time.toFixed(2)} ms --> Total: ${total_time.toFixed(2)} ms with ${num_wal_files_required} WAL files.`;
    return {
        'num_wal_files': num_wal_files_required,
        'rotate_time': rotate_time_in_ms,
        'write_time': write_time_in_ms,
        'delay_time': delay_time,
        'total_time': total_time,
        'msg': msg
    };
}

function checkpoint_time(checkpoint_timeout_second, checkpoint_completion_target, shared_buffers,
                         shared_buffers_ratio, effective_cache_size, max_wal_size, data_disk_iops) {
    console.debug('Estimate the time required to flush the full WAL buffers to disk');
    const checkpoint_duration = Math.ceil(checkpoint_timeout_second * checkpoint_completion_target);
    const data_tran_tput = PG_DISK_PERF.iops_to_throughput(data_disk_iops)
    const data_max_mib_written = data_tran_tput * checkpoint_duration;

    let data_amount = Math.floor(shared_buffers * shared_buffers_ratio);    // Measured in bytes
    data_amount = Math.min(data_amount, effective_cache_size, max_wal_size);  // Measured in bytes
    const page_amount = Math.floor(data_amount / DB_PAGE_SIZE);
    const data_write_time = Math.floor((data_amount / Mi) / data_tran_tput);  // Measured in seconds
    const data_disk_utilization = data_write_time / checkpoint_duration;
    return {
        'checkpoint_duration': checkpoint_duration,
        'data_disk_translated_tput': data_tran_tput,
        'data_disk_max_mib_written': data_max_mib_written,

        'data_amount': data_amount,
        'page_amount': page_amount,

        'data_write_time': data_write_time,
        'data_disk_utilization': data_disk_utilization,
    }
}

function vacuum_time(hit_cost, miss_cost, dirty_cost, delay_ms, cost_limit, data_disk_iops) {
    console.debug('Estimate the time required to vacuum the dirty pages');
    const budget_per_sec = Math.ceil(cost_limit / delay_ms * K10);
    // Estimate the maximum number of pages that can be vacuumed in one second
    const max_num_hit_page = Math.floor(budget_per_sec / hit_cost);
    const max_num_miss_page = Math.floor(budget_per_sec / miss_cost);
    const max_num_dirty_page = Math.floor(budget_per_sec / dirty_cost);
    // Calculate the data amount in MiB per cycle
    const max_hit_data = PG_DISK_PERF.iops_to_throughput(max_num_hit_page);
    const max_miss_data = PG_DISK_PERF.iops_to_throughput(max_num_miss_page);
    const max_dirty_data = PG_DISK_PERF.iops_to_throughput(max_num_dirty_page);
    // Some informative message
    const _disk_tput = PG_DISK_PERF.iops_to_throughput(data_disk_iops);
    const _msg = `Reporting the time spent for normal vacuuming with the cost budget of ${budget_per_sec} in 1 second. 
HIT (page in shared_buffers): ${max_num_hit_page} page -> Throughput: ${max_hit_data.toFixed(2)} MiB/s -> Safe to GO: ${max_hit_data < 10 * K10} (< 10 GiB/s for low DDR3)
MISS (page in disk cache): ${max_num_miss_page} page -> Throughput: ${max_miss_data.toFixed(2)} MiB/s -> Safe to GO: ${max_miss_data < 5 * K10} (< 5 GiB/s for low DDR3)
DIRTY (page in disk): ${max_num_dirty_page} page -> Throughput: ${max_dirty_data.toFixed(2)} MiB/s -> Safe to GO: ${max_dirty_data < _disk_tput} (< Data Disk IOPS)`;

    // Scenario: 5:5:1 (frequent vacuum) or 1:1:1 (rarely vacuum)
    const _551page = Math.floor(budget_per_sec / (5 * hit_cost + 5 * miss_cost + dirty_cost));
    const _551data = PG_DISK_PERF.iops_to_throughput(_551page * 5 + _551page);
    const _111page = Math.floor(budget_per_sec / (hit_cost + miss_cost + dirty_cost));
    const _111data = PG_DISK_PERF.iops_to_throughput(_111page * 1 + _111page);
    return {
        max_num_hit_page: max_num_hit_page,
        max_num_miss_page: max_num_miss_page,
        max_num_dirty_page: max_num_dirty_page,
        max_hit_data: max_hit_data,
        max_miss_data: max_miss_data,
        max_dirty_data: max_dirty_data,
        '5:5:1_page': _551page,
        '5:5:1_data': _551data,
        '1:1:1_page': _111page,
        '1:1:1_data': _111data,
        msg: _msg
    }
}

function vacuum_scale(threshold, scale_factor) {
    console.debug('Estimate the number of changed or dead tuples to trigger normal vacuum');
    const _fn = (num_rows) => Math.floor(threshold + scale_factor * num_rows);
    // Table Size (small): 10K rows
    const dead_at_10k = _fn(10_000);
    // Table Size (medium): 300K rows
    const dead_at_300k = _fn(300_000);
    // Table Size (large): 10M rows
    const dead_at_10m = _fn(10_000_000);
    // Table Size (giant): 300M rows
    const dead_at_100m = _fn(100_000_000);
    // Table Size (huge): 1B rows
    const dead_at_1b = _fn(1_000_000_000);
    // Table Size (giant): 10B rows
    const dead_at_10b = _fn(10_000_000_000);

    const msg = `The threshold of ${threshold} will trigger the normal vacuum when the number of changed or dead tuples exceeds ${threshold * scale_factor} tuples.
-> Table Size: 10K rows -> Dead Tuples: ${dead_at_10k} tuples
-> Table Size: 300K rows -> Dead Tuples: ${dead_at_300k} tuples
-> Table Size: 10M rows -> Dead Tuples: ${dead_at_10m} tuples
-> Table Size: 100M rows -> Dead Tuples: ${dead_at_100m} tuples
-> Table Size: 1B rows -> Dead Tuples: ${dead_at_1b} tuples
-> Table Size: 10B rows -> Dead Tuples: ${dead_at_10b} tuples`;
    return {
        '10k': dead_at_10k,
        '300k': dead_at_300k,
        '10m': dead_at_10m,
        '100m': dead_at_100m,
        '1b': dead_at_1b,
        '10b': dead_at_10b,
        msg: msg
    }
}
