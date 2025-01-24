"""
This module is to perform specific tuning on the PostgreSQL database server.

"""
import logging
from math import floor

from pydantic import ByteSize

from src.static.vars import APP_NAME_UPPER, Mi, K10
from src.utils.pydantic_utils import bytesize_to_hr

__all__ = ['wal_time']
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
