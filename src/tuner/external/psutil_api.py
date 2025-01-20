"""
MIT License

Copyright (c) 2024 - 2025 Ichiru

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---------------------------------------------------------------------------
This script attempts to collect the server information and snapshot the current
status of the server such as CPU, Memory, Disk, Network, Swap, Services, Processes,
and other system information through the :mod:`psutil` library. Our work from this
is to generate a report that can be used for monitoring, debugging, and tuning
the server. For future-proof operation, we attempt to create a machine-learning
SLM that co-operate with PostgreSQL log analytics (pgBadger) for better performance
tuning, and probably make it real-time optimization

"""
import os.path
import socket
from collections import namedtuple

import psutil
from typing import Literal
from psutil import (CONN_ESTABLISHED, CONN_SYN_SENT, CONN_SYN_RECV, CONN_FIN_WAIT1, CONN_FIN_WAIT2, CONN_TIME_WAIT,
                    CONN_CLOSE, CONN_CLOSE_WAIT, CONN_LAST_ACK, CONN_LISTEN, CONN_CLOSING, CONN_NONE, NIC_DUPLEX_FULL,
                    NIC_DUPLEX_HALF, NIC_DUPLEX_UNKNOWN)
from pydantic import BaseModel, Field, ByteSize
from datetime import datetime, timezone
from src.static.vars import Gi

__all__ = ['SERVER_SNAPSHOT', 'snapshot_sample']




# ==================================================================================================
class _CPU_TIMES(BaseModel):
    user: float = Field(description="The time spent by normal processes executing in user mode")
    system: float = Field(description="The time spent by processes executing in kernel mode")
    idle: float = Field(description="The time spent doing nothing")


class _CPU_STATS(BaseModel):
    ctx_switches: int = Field(description="The number of context switches (voluntary + involuntary) since boot")
    interrupts: int = Field(description="The number of interrupts since boot")
    soft_interrupts: int = Field(description="The number of software interrupts since boot (always 0 in Wins and SunOS)")
    syscalls: int = Field(description="The number of system calls since boot (always 0 in Linux)")


# ==================================================================================================
# Memory
class _MEM_VIRTUAL(BaseModel):
    total: ByteSize = Field(description="The total amount of physical memory, in bytes")
    available: ByteSize = Field(description="The amount of memory available, in bytes")
    percent: float = Field(description="The percentage of memory that is used")


class _MEM_SWAP(BaseModel):
    total: ByteSize = Field(description="The total amount of swap memory, in bytes")
    used: ByteSize = Field(description="The amount of swap memory used, in bytes")
    free: ByteSize = Field(description="The amount of swap memory available, in bytes")
    percent: float = Field(description="The percentage of swap memory that is used")
    sin: ByteSize = Field(description="The number of bytes the system has swapped in from disk")
    sout: ByteSize = Field(description="The number of bytes the system has swapped out to disk")


# ==================================================================================================
# Disk
class _DISK_USAGE(BaseModel):
    path: str = Field(description="The mount point path")   # Add as not available in psutil.disk_usage
    total: ByteSize = Field(description="The total amount of disk space, in bytes")
    used: ByteSize = Field(description="The amount of disk space used, in bytes")
    free: ByteSize = Field(description="The amount of disk space available, in bytes")
    percent: float = Field(description="The percentage of disk space that is used")


class _DISK_IO_COUNTER(BaseModel):
    read_count: int = Field(description="The number of reads completed")
    write_count: int = Field(description="The number of writes completed")
    read_bytes: ByteSize = Field(description="The number of bytes read")
    write_bytes: ByteSize = Field(description="The number of bytes written")


class _DISK_PARTITION(BaseModel):
    device: str = Field(description="The device path")
    mountpoint: str = Field(description="The mount point path")
    fstype: str = Field(description="The filesystem type")
    opts: str = Field(description="The mount options associated with the filesystem")
    usage: _DISK_USAGE = Field(description="The disk usage")  # Add more for df -hT
    io_counter: _DISK_IO_COUNTER = Field(description="The disk I/O counters")





# ==================================================================================================
# Network
class _NET_IO_COUNTERS(BaseModel):
    bytes_sent: ByteSize = Field(description="The number of bytes sent")
    bytes_recv: ByteSize = Field(description="The number of bytes received")
    packets_sent: int = Field(description="The number of packets sent")
    packets_recv: int = Field(description="The number of packets received")
    errin: int = Field(description="The number of receive errors encountered")
    errout: int = Field(description="The number of transmit errors encountered")
    dropin: int = Field(description="The number of incoming packets dropped")
    dropout: int = Field(description="The number of outgoing packets dropped")


CONN_STATUS = "|".join((CONN_ESTABLISHED, CONN_SYN_SENT, CONN_SYN_RECV, CONN_FIN_WAIT1, CONN_FIN_WAIT2, CONN_TIME_WAIT,
                        CONN_CLOSE, CONN_CLOSE_WAIT, CONN_LAST_ACK, CONN_LISTEN, CONN_CLOSING, CONN_NONE))


class _NET_CONN(BaseModel):
    fd: int = Field(description="The socket file descriptor number")
    family: socket.AddressFamily | int = Field(description="The address family, either AF_INET, AF_INET6 or AF_UNIX.")
    type: socket.SocketKind | int = Field(description="The socket type, either SOCK_STREAM, SOCK_DGRAM or SOCK_SEQPACKET.")
    laddr: tuple[str, int] = Field(description="The local address as a (ip, port) tuple")
    raddr: tuple[str, int] = Field(description="The remote address as a (ip, port) tuple")
    status: str = Field(description="The connection status", pattern=CONN_STATUS)
    pid: int | None = Field(description="The PID of the process which opened the socket")


class _NET_IF_ADDR(BaseModel):
    family: socket.AddressFamily | int = Field(description="The address family, either AF_INET, AF_INET6 or AF_LINK.") # AF_LINK available on Linux as alias
    address: str = Field(description="The primary address associated with the network interface")
    netmask: str | None = Field(description="The netmask associated with the network interface")
    broadcast: str | None = Field(description="The broadcast address associated with the network interface")
    ptp: str | None = Field(description="The point-to-point address associated with the network interface")


class _NET_IF_STAT(BaseModel):
    isup: bool = Field(description="The network interface is up")
    duplex: Literal[NIC_DUPLEX_FULL, NIC_DUPLEX_HALF, NIC_DUPLEX_UNKNOWN] = (
        Field(description="The network interface duplex setting")
    )
    speed: int = Field(description="The network interface speed in Mbps")
    mtu: int = Field(description="The network interface MTU")
    flags: str = Field(description="A string of comma-separated flags on the interface (platform-dependent)")


# ==================================================================================================
# Snapshot at Time
class SERVER_SNAPSHOT(BaseModel):
    start_time: datetime = Field(description="The time when the snapshot was taken")
    end_time: datetime = Field(description="The time when the snapshot was taken")

    # CPU
    physical_cpu_count: int = Field(default_factory=lambda: psutil.cpu_count(logical=False))
    logical_cpu_count: int = Field(default_factory=lambda: psutil.cpu_count(logical=True))
    cpu_times: _CPU_TIMES
    cpu_stats: _CPU_STATS

    # Memory
    mem_virtual: _MEM_VIRTUAL
    mem_swap: _MEM_SWAP

    # Disk
    disk_partitions: list[_DISK_PARTITION]

    # Network
    # net_connections: list[_NET_CONN]      # We don't need this for now
    net_io_counters: dict[str, _NET_IO_COUNTERS]
    net_if_addrs: dict[str, list[_NET_IF_ADDR]]
    net_if_stats: dict[str, _NET_IF_STAT]

    # Others
    boot_time: float = Field(default_factory=lambda: psutil.boot_time(),
                             description="The system boot time expressed in seconds since the epoch", )

    @staticmethod
    def profile_current_server():
        start_time: datetime = datetime.now(tz=timezone.utc)
        # CPU: https://psutil.readthedocs.io/en/latest/#psutil.cpu_times
        cpu_times: namedtuple = psutil.cpu_times(percpu=False)
        cpu_stats: namedtuple = psutil.cpu_stats()
        # Memory:
        mem_virtual: namedtuple = psutil.virtual_memory()
        mem_swap: namedtuple = psutil.swap_memory()
        # Disk
        c_partitions: list[_DISK_PARTITION] = []
        partitions = psutil.disk_partitions(all=False)  # Check for LVM ?
        io_counters = psutil.disk_io_counters(perdisk=True, nowrap=True)
        for idx, p in enumerate(partitions):
            mountpoint = p.mountpoint
            is_lvm = mountpoint.count('/') > (1 + mountpoint.startswith('/'))
            is_dev_mapper = is_lvm and mountpoint.startswith('dev/mapper')
            mnt_name = mountpoint.split('/')[-1]
            if is_dev_mapper:
                mnt_name = '-'.join(mnt_name.split('-')[1:])
            d_usage = _DISK_USAGE(path=mountpoint, **psutil.disk_usage(mountpoint)._asdict())
            try:
                d_io_counter = _DISK_IO_COUNTER(**io_counters[mnt_name]._asdict()) or None
            except KeyError as e:   # Probably on Windows
                d_io_counter = _DISK_IO_COUNTER(**io_counters[list(io_counters.keys())[idx]]._asdict()) or None
            c_partitions.append(_DISK_PARTITION(**p._asdict(), usage=d_usage, io_counter=d_io_counter))

        # Network
        # net_conns = [conn._asdict() for conn in psutil.net_connections(kind="all")]
        # for conn in net_conns:
        #     conn['raddr'] = tuple(conn['raddr']) or ('127.0.0.1', 0)
        #     conn['laddr'] = tuple(conn['laddr']) or ('127.0.0.1', 0)

        # We only collect isup=True network
        net_if_stats = {nic: stat._asdict() for nic, stat in psutil.net_if_stats().items() if stat.isup is True}
        net_io_counters = {nic: counter._asdict() for nic, counter in psutil.net_io_counters(pernic=True).items()
                           if nic in net_if_stats}
        net_if_addrs = {nic: [addr._asdict() for addr in addrs] for nic, addrs in psutil.net_if_addrs().items()
                        if nic in net_if_stats}

        return SERVER_SNAPSHOT(
            start_time=start_time,
            end_time=datetime.now(tz=timezone.utc),
            cpu_times=_CPU_TIMES(**cpu_times._asdict()),
            cpu_stats=_CPU_STATS(**cpu_stats._asdict()),
            mem_virtual=_MEM_VIRTUAL(**mem_virtual._asdict()),
            mem_swap=_MEM_SWAP(**mem_swap._asdict()),
            disk_partitions=c_partitions,

            # net_connections=[_NET_CONN(**conn) for conn in net_conns],
            net_io_counters={nic: _NET_IO_COUNTERS(**counter) for nic, counter in net_io_counters.items()},
            net_if_addrs={nic: [_NET_IF_ADDR(**addr) for addr in addrs] for nic, addrs in net_if_addrs.items()},
            net_if_stats={nic: _NET_IF_STAT(**stat) for nic, stat in net_if_stats.items()}
        )

# ==================================================================================================
_sample_cache: SERVER_SNAPSHOT | None = None

def snapshot_sample(vcpu: int = 4, memory: ByteSize | int = 16 * Gi, hyperthreading: bool = False) -> SERVER_SNAPSHOT:
    global _sample_cache
    if _sample_cache is None:
        # Get the sample of the server snapshot, read as JSON and put as Pydantic model in SERVER_SNAPSHOT
        sample_jsonpath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'sample.json'))
        if not os.path.exists(sample_jsonpath):
            raise FileNotFoundError(f"Sample JSON file not found at {sample_jsonpath}")
        import json
        with open(sample_jsonpath, 'r') as f:
            data = json.load(f)
            _sample_cache = SERVER_SNAPSHOT(**data)

    snapshot: SERVER_SNAPSHOT = _sample_cache.model_copy(deep=True)
    snapshot.physical_cpu_count = vcpu if not hyperthreading else vcpu // 2
    snapshot.logical_cpu_count = vcpu
    snapshot.mem_virtual.total = ByteSize(memory)
    # snapshot.mem_virtual.available = ByteSize(int(memory * snapshot.mem_virtual.percent))
    # We used swap here to prevent incorrect error log
    snapshot.mem_swap.total = ByteSize(max(memory // 4, 4 * Gi))
    return snapshot