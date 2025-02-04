"""
This module is to perform specific tuning on the PostgreSQL database server.

"""
import logging
from math import floor, ceil

from pydantic import ByteSize

from src.static.vars import APP_NAME_UPPER, Mi, K10, DB_PAGE_SIZE
from src.tuner.data.disks import PG_DISK_PERF
from src.utils.pydantic_utils import bytesize_to_hr

__all__ = ['wal_time', 'checkpoint_time', 'vacuum_time', 'vacuum_scale']
_logger = logging.getLogger(APP_NAME_UPPER)

# The time required to create, opened and close a file. This has been tested with all disk cache flushed,
# Windows (NTFS) and Linux (EXT4/XFS) on i7-8700H with Python 3.12 on NVMEv3 SSD and old HDD
_FILE_ROTATION_TIME_MS = 0.21 * 2  # 0.21 ms on average when direct bare-metal, 2-3x on virtualized


def wal_time(wal_buffers: ByteSize, data_amount_ratio: int | float, wal_segment_size: ByteSize | int,
             wal_writer_delay_in_ms: int, wal_throughput: ByteSize | int, ) -> dict:
    # The time required to flush the full WAL buffers to disk (assuming we have no write after the flush)
    # or wal_writer_delay is being woken up or 2x of wal_buffers are synced
    _logger.debug('Estimate the time required to flush the full WAL buffers to disk')
    data_amount = int(wal_buffers * data_amount_ratio)
    num_wal_files_required = data_amount // wal_segment_size + 1
    rotate_time_in_ms = num_wal_files_required * _FILE_ROTATION_TIME_MS
    write_time_in_ms = (data_amount / Mi) / wal_throughput * K10

    # Calculate maximum how many delay time
    delay_time = 0
    if data_amount_ratio > 1:
        num_delay = floor(data_amount_ratio)
        _fractional = data_amount_ratio - num_delay
        if _fractional == 0:
            num_delay -= 1
        delay_time = num_delay * wal_writer_delay_in_ms
    total_time = rotate_time_in_ms + write_time_in_ms + delay_time
    _msg = (f'Estimate the time required to flush the full-queued WAL buffers {bytesize_to_hr(data_amount)} '
            f'to disk: rotation time: {rotate_time_in_ms:.2f} ms, write time: {write_time_in_ms:.2f} ms, '
            f'delay time: {delay_time:.2f} ms --> Total: {total_time:.2f} ms with {num_wal_files_required} '
            f'WAL files.')
    return {
        'num_wal_files': num_wal_files_required,
        'rotate_time': rotate_time_in_ms,
        'write_time': write_time_in_ms,
        'delay_time': delay_time,
        'total_time': total_time,
        'msg': _msg
    }

def checkpoint_time(checkpoint_timeout_second: int, checkpoint_completion_target,
                    wal_disk_tput: int, data_disk_iops: int,
                    wal_buffers: ByteSize, data_amount_ratio: int | float, wal_segment_size: ByteSize) -> dict:
    # Validate the maximum number of times to complete the checkpoint
    # or wal_writer_delay is being woken up or 2x of wal_buffers are synced
    _logger.debug('Estimate the time required to flush the full WAL buffers to disk')
    checkpoint_duration = ceil(checkpoint_timeout_second * checkpoint_completion_target)  # Measured in seconds
    data_disk_translated_tput = PG_DISK_PERF.iops_to_throughput(data_disk_iops) # Measured in MiB/s
    data_disk_max_mib_written = data_disk_translated_tput * checkpoint_duration

    data_amount = int(wal_buffers * data_amount_ratio)  # Measured in bytes
    page_amount: int = floor(data_amount / DB_PAGE_SIZE)
    wal_amount: int = floor(data_amount / wal_segment_size)

    wal_read_time: int = floor((data_amount / Mi) / wal_disk_tput)  # Measured in seconds
    wal_disk_utilization = wal_read_time / checkpoint_duration

    data_write_time: int = floor((data_amount / Mi) / data_disk_translated_tput)  # Measured in seconds
    data_disk_utilization = data_write_time / checkpoint_duration

    return {
        'checkpoint_duration': checkpoint_duration,
        'data_disk_translated_tput': data_disk_translated_tput,
        'data_disk_max_mib_written': data_disk_max_mib_written,

        'data_amount': data_amount,
        'page_amount': page_amount,
        'wal_amount': wal_amount,

        'wal_read_time': wal_read_time,
        'wal_disk_utilization': wal_disk_utilization,
        'data_write_time': data_write_time,
        'data_disk_utilization': data_disk_utilization,
    }


def vacuum_time(hit_cost: int, miss_cost: int, dirty_cost: int, delay_ms: int, cost_limit: int,
                data_disk_iops: int) -> dict:
    # The time required to vacuum the dirty pages
    _logger.debug('Estimate the time required to vacuum the dirty pages')
    budget_per_sec: int = ceil(cost_limit / delay_ms * K10)

    # Estimate the maximum number of pages that can be vacuumed in one second
    max_num_hit_page: int = budget_per_sec // hit_cost
    max_num_miss_page: int = budget_per_sec // miss_cost
    max_num_dirty_page: int = budget_per_sec // dirty_cost

    # Calculate the data amount in MiB per cycle
    max_hit_data: int = PG_DISK_PERF.iops_to_throughput(max_num_hit_page)
    max_miss_data: int = PG_DISK_PERF.iops_to_throughput(max_num_miss_page)
    max_dirty_data: int = PG_DISK_PERF.iops_to_throughput(max_num_dirty_page)

    # Some informative message
    _disk_tput = PG_DISK_PERF.iops_to_throughput(data_disk_iops)
    _msg = (f'Reporting the time spent for normal vacuuming with the cost budget of {budget_per_sec} in 1 second. '
            f'\nHIT (page in shared_buffers): {max_num_hit_page} page -> Throughput: {max_hit_data:.2f} MiB/s '
            f'-> Safe to GO: {max_hit_data < 10 * K10} (< 10 GiB/s for low DDR3)'
            f'\nMISS (page in disk cache): {max_num_miss_page} page -> Throughput: {max_miss_data:.2f} MiB/s '
            f'-> Safe to GO: {max_miss_data < 5 * K10} (< 5 GiB/s for low DDR3)'
            f'\nDIRTY (page in disk): {max_num_dirty_page} page -> Throughput: {max_dirty_data:.2f} MiB/s '
            f'-> Safe to GO: {max_dirty_data < data_disk_iops} (< Data Disk IOPS)')

    # Scenario: 5:5:1 (frequent vacuum) or 1:1:1 (rarely vacuum)
    _551page = budget_per_sec // (5 * hit_cost + 5 * miss_cost + dirty_cost)
    _551data = PG_DISK_PERF.iops_to_throughput(_551page * 5 + _551page)

    _111page = budget_per_sec // (hit_cost + miss_cost + dirty_cost)
    _111data = PG_DISK_PERF.iops_to_throughput(_111page * 1 + _111page)

    return {
        'max_num_hit_page': max_num_hit_page,
        'max_num_miss_page': max_num_miss_page,
        'max_num_dirty_page': max_num_dirty_page,
        'max_hit_data': max_hit_data,
        'max_miss_data': max_miss_data,
        'max_dirty_data': max_dirty_data,
        '5:5:1_page': _551page,
        '5:5:1_data': _551data,
        '1:1:1_page': _111page,
        '1:1:1_data': _111data,
        'msg': _msg
    }

def vacuum_scale(threshold: int, scale_factor: float) -> dict:
    _logger.debug('Estimate the number of changed or dead tuples to trigger normal vacuum')
    _fn = lambda num_rows: floor(threshold + scale_factor * num_rows)

    # Table Size (small): 10K rows
    dead_at_10k = _fn(10_000)

    # Table Size (medium): 300K rows
    dead_at_300k = _fn(300_000)

    # Table Size (large): 5M rows
    dead_at_5m = _fn(5_000_000)

    # Table Size (huge): 25M rows
    dead_at_25m = _fn(25_000_000)

    # Table Size (giant): 300M rows
    dead_at_400m = _fn(300_000_000)

    # Table Size (huge): 1B rows
    dead_at_1b = _fn(1_000_000_000)

    # Table Size (giant): 10B rows
    dead_at_10b = _fn(10_000_000_000)

    _msg = (f'The threshold of {threshold} will trigger the normal vacuum when the number of changed or dead tuples '
            f'exceeds {threshold * scale_factor} tuples.'
            f'\n-> Table Size: 10K rows -> Dead Tuples: {dead_at_10k} tuples'
            f'\n-> Table Size: 300K rows -> Dead Tuples: {dead_at_300k} tuples'
            f'\n-> Table Size: 5M rows -> Dead Tuples: {dead_at_5m} tuples'
            f'\n-> Table Size: 25M rows -> Dead Tuples: {dead_at_25m} tuples'
            f'\n-> Table Size: 300M rows -> Dead Tuples: {dead_at_400m} tuples'
            f'\n-> Table Size: 1B rows -> Dead Tuples: {dead_at_1b} tuples'
            f'\n-> Table Size: 10B rows -> Dead Tuples: {dead_at_10b} tuples')
    return {
        '10k': dead_at_10k,
        '300k': dead_at_300k,
        '5m': dead_at_5m,
        '25m': dead_at_25m,
        '400m': dead_at_400m,
        '1b': dead_at_1b,
        '10b': dead_at_10b,
        'msg': _msg
    }
