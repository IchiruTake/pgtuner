"""
This module include how the tuning items are aligned. The layout is splited between category which shared this
format:

_<Scope>_<Description>_PROFILE = {
    "<tuning_item_name>": {
        "tune_op": Callable(),          # Optional, used to define the function to calculate the value
        "default": <default_value>,     # Must have and a constant and not a function
        "comment": "<description>",     # An optional description
        "instructions": {
            "*_default": <default_value>,  # Optional, used to define the default value for each tuning profile
            "*": Callable(),               # Optional, used to define the function to calculate the value
        }

        # Post-condition is to validate the tuning item after the tuning is applied
        "post-condition": Callable(),
        "post-condition-group": Callable(),
        "post-condition-all": Callable(),
    }
}

"""
from src.static.vars import Ki, K10, Mi
from src.tuner.data.scope import PG_SCOPE

__all__ = ["KERNEL_SYSCTL_PROFILE"]

from src.tuner.profile.common import merge_extra_info_to_profile, type_validation

# =============================================================================
# Kernel tuning profiles for the filesystem
_KERNEL_FS_PROFILE = {
    "fs.nr_open": {
        "instructions": {
            "mini_default": 1 * Mi,
            "medium_default": 2 * Mi,
            "large_default": 3 * Mi,
            "mall_default": 6 * Mi,
            "bigt_default": 8 * Mi,
        },
        "default": Mi * 5 // 2,
        "comment": "The maximum number of file-handles that the Linux kernel will allocate. Limiting this value can "
                   "help to prevent fork bombs from consuming all available file-handles. While these value could "
                   "be large than usual (usually around 128 Ki to 256 Ki), making this large won't impact much on "
                   "the system.",
    },
    "fs.file-max": {
        "instructions": {
            "mini_default": 1 * Mi,
            "medium_default": 2 * Mi,
            "large_default": 3 * Mi,
            "mall_default": 5 * Mi,
            "bigt_default": 8 * Mi,
        },
        "default": Mi * 5 // 2,
        "comment": "The maximum number of file-handles that the Linux kernel will allocate. Limiting this value can "
                   "help to prevent fork bombs from consuming all available file-handles. While these value could "
                   "be large than usual (usually around 128 Ki to 256 Ki), making this large won't impact much on "
                   "the system.",
    }
}

# Kernel tuning profiles for the networking (This is strongly associated to the available network bandwidth,
# latency, the network traffic pattern (of all services), and the connection management of the PostgreSQL server)
# In our tuning guideline, the maximum number of connections used by database is 250
_KERNEL_NETCORE_PROFILE = {
    "net.core.somaxconn": {
        "default": 4 * Ki,  # Default here
        "comment": "The maximum of number of connections that can be queued for a socket. Default as 4096 on Ubuntu "
                   "24.10.",
    },
    "net.core.netdev_budget": {
        "instructions": {
            "large_default": 600,
            "mall_default": 900,
            "bigt_default": 900,
        },
        "default": 450,
        "comment": "Maximum number of packets taken from all interfaces in one polling cycle (NAPI poll). In one "
                   "polling cycle interfaces which are registered to polling are probed in a round-robin manner."
                   "Default is 300/2000 for netdev_budget/netdev_budget_usecs but increasing this range can help"
                   "on busy network. But on system with large network usage, ",
    },
    "net.core.netdev_budget_usecs": {
        "instructions": {
            "large_default": 8 * K10,
            "mall_default": 12 * K10,
            "bigt_default": 12 * K10,
        },
        "default": 6 * K10,
        "comment": "Maximum number of microseconds in one NAPI polling cycle. Polling will exit when either "
                   "netdev_budget_usecs have elapsed during the poll cycle or the number of packets processed reaches "
                   "netdev_budget. Default is 300/2000 for netdev_budget/netdev_budget_usecs but increasing this range "
                   "can help on busy network (with linear scale.",
    },
    "net.core.netdev_max_backlog": {
        "instructions": {
            "large_default": K10,
            "mall_default": K10 * 3 // 2,
            "bigt_default": K10 * 3 // 2,
        },
        "default": K10,  # Default here
        "comment": "Maximum number of packets, queued on the INPUT side, when the interface receives packets "
                   "faster than kernel can process them.",
    },

    "net.core.rmem_default": {
        # Capped and reached the nearest value between min_value <-> max_value
        "instructions": {
            "large_default": 512 * Ki,
            "mall_default": Mi,
            "bigt_default": Mi,
        },
        "default": 256 * Ki,
        "comment": "The default setting of the socket receive buffer in bytes (208 KiB by Linux) in general. It would "
                   "be override when specific net.ipv[4|6].* or net.ipv[4|6].<nic-id>.* is configured at enabled.",
    },
    "net.core.rmem_max": {
        "instructions": {
            "large_default": Mi,
            "mall_default": 2 * Mi,
            "bigt_default": 2 * Mi,
        },
        "default": 512 * Ki,
        "comment": "The maximum setting of the socket receive buffer in bytes (208 KiB by Linux). It would be override "
                   "when specific net.ipv[4|6].* or net.ipv[4|6].<nic-id>.* is configured at enabled.",
    },
    "net.core.wmem_default": {
        "instructions": {
            "large_default": 512 * Ki,
            "mall_default": Mi,
            "bigt_default": Mi,
        },
        "default": 256 * Ki,
        "comment": "The default setting of the socket send buffer in bytes (208 KiB by Linux). It would be override "
                   "when specific net.ipv[4|6].* or net.ipv[4|6].<nic-id>.* is configured at enabled.",
    },
    "net.core.wmem_max": {
        "instructions": {
            "large_default": Mi,
            "mall_default": 2 * Mi,
            "bigt_default": 2 * Mi,
        },
        "default": 512 * Ki,
        "comment": "The maximum setting of the socket send buffer in bytes (208 KiB by Linux). It would be override "
                   "when specific net.ipv[4|6].* or net.ipv[4|6].<nic-id>.* is configured at enabled.",
    },
    "net.core.optmem_max": {
        "instructions": {
            "large_default": Mi,
            "mall_default": 2 * Mi,
            "bigt_default": 2 * Mi,
        },
        "default": 512 * Ki,
        "comment": "The maximum ancillary buffer size allowed per socket. Ancillary data is a sequence of "
                   "struct cmsghdr structures with appended data.",
    },
}

# Network tuning profiles for the IPv4-specific settings. For IPv6, most of the real-world applications are still
# stick to the IPv4
_KERNEL_NETIPV4_PROFILE = {
    "net.ipv4.tcp_max_syn_backlog": {
        "instructions": {
            "large_default": 512,
            "mall_default": 512,
            "bigt_default": 512,
        },
        "default": 256,  # Used for mini and medium profile
        "comment": "The maximum number of remembered connection requests (SYN_RECV), which have not received an "
                   "acknowledgment from connecting client. This is a per-listener limit. A SYNC_RECV request "
                   "socket consumes 304 bytes of memory",
    },
    "net.ipv4.udp_rmem_min": {
        "instructions": {
            "large_default": 8 * Ki,
            "mall_default": 8 * Ki,
            "bigt_default": 8 * Ki,
        },
        "default": 4 * Ki,  # Used for mini and medium profile
        "comment": "The minimum size of the receive buffer for UDP sockets. Each UDP socket is able to use the size for "
                   "receiving data, even if total pages of UDP sockets exceed udp_mem pressure. The unit is byte.",
    },
    "net.ipv4.udp_wmem_min": {
        "instructions": {
            "large_default": 8 * Ki,
            "mall_default": 8 * Ki,
            "bigt_default": 8 * Ki,
        },
        "default": 4 * Ki,  # Used for mini and medium profile
        "comment": "The minimum size of the send buffer for UDP sockets. Each UDP socket is able to use the size for "
                   "sending data, even if total pages of UDP sockets exceed udp_mem pressure. The unit is byte.",
    },
    "net.ipv4.tcp_rmem": {
        "instructions": {
            "mini_default": f"{4 * Ki} {128 * Ki} {16 * Mi}",
            "medium_default": f"{4 * Ki} {256 * Ki} {32 * Mi}",
            "large_default": f"{4 * Ki} {256 * Ki} {64 * Mi}",
            "mall_default": f"{8 * Ki} {512 * Ki} {64 * Mi}",
            "bigt_default": f"{8 * Ki} {512 * Ki} {128 * Mi}",
        },
        "default": f"{4 * Ki} {256 * Ki} {64 * Mi}",
        "comment": "The default, minimum, and maximum size of the receive buffer for TCP sockets. The unit is byte. "
                   "If you want to tune the tcp_rmem:max -> See the net.ipv4.tcp_adv_win_scale as this value is "
                   "dependent on the tcp_adv_win_scale. Default is 4Ki 128Ki 6Mi on Ubuntu 24.10",
    },
    "net.ipv4.tcp_wmem": {
        "instructions": {
            "mini_default": f"{4 * Ki} {32 * Ki} {8 * Mi}",
            "medium_default": f"{4 * Ki} {64 * Ki} {16 * Mi}",
            "large_default": f"{4 * Ki} {64 * Ki} {32 * Mi}",
            "mall_default": f"{8 * Ki} {128 * Ki} {32 * Mi}",
            "bigt_default": f"{8 * Ki} {128 * Ki} {64 * Mi}",
        },
        "default": f"{4 * Ki} {64 * Ki} {32 * Mi}",
        "comment": "The default, minimum, and maximum size of the send buffer for TCP sockets. The unit is byte."
                   "Default is 4Ki 16Ki 4Mi on Ubuntu 24.10",
    },
    "net.ipv4.tcp_adv_win_scale": {
        "default": -2,
        "comment": "The window scaling factor for TCP connections. This is used to increase the maximum window size "
                   "from 64KB to 1GB (The TCP window size used is tcp_rmem:max * ratio (4: 15/16, 3: 7/8, 2: 3/4,"
                   "1: 1/2, 0: 100%, -1: 1/2, -2: 1/4, -3: 1/8, -4: 1/16). See link [12] of Cloudflare for more."
                   "Basically on PostgreSQL, one database connection would ends up in one TCP socket. Default to -2 ("
                   "maximum 1/4 of TCP window is pre-configured).",
    },
    "net.ipv4.tcp_window_scaling": {
        "default": 1,
        "comment": "Enable window scaling as defined in RFC1323. Enable this to let the TCP Window Scaling extends the "
                   "16-bit window size field in the TCP header (maximum 65,535 bytes) to allow much larger windows "
                   "(up to 1 GiB).",
    },
    "net.ipv4.tcp_sack": {
        "default": 1,
        "comment": "Enable selective acknowledgments as defined in RFC2018.",
    },
    "net.ipv4.tcp_moderate_rcvbuf": {
        "default": 1,
        "comment": "Enable automatic tuning of the receive buffer size for TCP sockets. This allows the kernel to "
                   "dynamically adjust the receive buffer size based on the amount of memory available.",
    },
    "net.ipv4.tcp_tw_reuse": {
        "default": 2,
        "comment": "Enable reuse of TIME-WAIT sockets for new connections when it is safe from protocol viewpoint. "
                   "Set to 2 means enable for loopback traffic only",

    },
    "net.ipv4.tcp_notsent_lowat": {
        "default": 128 * Ki,
        "comment": "A TCP socket can control the amount of unsent bytes in its write queue, thanks to TCP_NOTSENT_LOWAT "
                   "socket option. poll()/select()/epoll() reports POLLOUT events if the amount of unsent bytes is "
                   "below a per	socket value, and if the write queue is not full. sendmsg() will also not add new "
                   "buffers if the limit is hit (Default to uint_max). See [13] for more information",

    },
    "net.ipv4.tcp_timestamps": {
        "default": 1,
        "comment": "Enable timestamps as defined in RFC1323. Whilst disable can bring minor performance improvement, "
                   "the timestamps are used for two distinct mechanisms: RTTM (Round Trip Time Measurement) and PAWS "
                   "(Protect Against Wrapped Sequences), which is used on uptime estimation and detect hidden network"
                   "-enabled OS, linking spoofed IP and MAC addresses together, linking IP addresses with Ad-Hoc "
                   "wireless APs, etc. See [14] for more information. Only set to zero if you prior to reduce TCP spike"
                   "and your network is safe from outsider.",
    },
    "net.ipv4.tcp_collapse_max_bytes": {
        "instructions": {
            "mall_default": 12 * Mi,
            "bigt_default": 16 * Mi,
        },
        "default": 4 * Mi,
        "comment": "The maximum number of bytes in a single TCP packet that can be collapsed. A value of 0 disables "
                   "TCP segment collapsing.",

    },
    # TCP packet timeout and retries & Keep-alive connections
    "net.ipv4.tcp_syn_retries": {
        "default": 4,
        "comment": "Number of times initial SYNs for an active TCP connection attempt will be retransmitted. Default "
                   "value is 6 (Ubuntu 24.10), which corresponds to 63 seconds till the last retransmission with the "
                   "current initial RTO of 1 second.",

    },
    "net.ipv4.tcp_synack_retries": {
        "default": 5,
        "comment": "Number of times SYNACKs for a passive TCP connection attempt will be retransmitted. Default value "
                   "is 5, which corresponds to 31 seconds till the last retransmission with the current initial RTO of "
                   "1 second. With this the final timeout for a passive TCP connection will happen after 63 seconds.",
    },
    "net.ipv4.tcp_fin_timeout": {
        "default": 30,
        "comment": "The length of time an orphaned (no longer referenced by any application) connection will remain in "
                   "the FIN_WAIT_2 state before it is aborted at the local end. The default is 60",
    },
    "net.ipv4.tcp_retries1": {
        "default": 3,
        "comment": "The number of times TCP will attempt to retransmit a packet on an established connection normally, "
                   "without the extra effort of getting the network layers involved.. The default is 3",

    },
    "net.ipv4.tcp_retries2": {
        "default": 10,
        "comment": "This value influences the timeout of an alive TCP connection, when RTO retransmissions remain "
                   "unacknowledged. Given a value of N, a hypothetical TCP connection following exponential backoff "
                   "with an initial RTO of TCP_RTO_MIN would retransmit N times before killing the connection at "
                   "the (N+1)th RTO.",
    },
    "net.ipv4.tcp_keepalive_intvl": {
        "default": 45,
        "comment": "How frequently the probes are send out. Multiplied by tcp_keepalive_probes it is time to kill not "
                   "responding connection, after probes started. Default value: 75 seconds i.e. connection will be "
                   "aborted after ~11 minutes of retries.",
    },
    "net.ipv4.tcp_keepalive_probes": {
        "default": 7,
        "comment": "The maximum number of TCP keep-alive probes to send before giving up and killing the connection if "
                   "no response is obtained from the other end. The default is 9 on Ubuntu 24.10",

    },
    "net.ipv4.tcp_keepalive_time": {
        "default": 3600,
        "comment": "The number of seconds a connection needs to be idle before TCP begins sending out keep-alive "
                   "probes. Keep-alives are only sent when the SO_KEEPALIVE socket option is enabled. Our default "
                   "value is 3600 seconds (1 hours). An idle connection is terminated after approximately an "
                   "additional 5.25 minutes (7 probes an interval of 45 seconds apart) when keep-alive is enabled.",
    },
}

# Kernel tuning profiles for the memory and VM management
_KERNEL_VM_PROFILE = {
    "vm.swappiness": {
        "instructions": {
            "mini_default": 15,
            "mall_default": 8,
            "bigt_default": 5,
        },
        "default": 10,
        "comment": "This control is used to define how aggressive the kernel will swap memory pages. Higher values will "
                   "increase aggressiveness, lower values decrease the amount of swap. Default to 10. The value from "
                   "1 to 10 is already optimal and increase it may not provide much benefit",
    },
    "vm.dirty_background_ratio": {
        "default": 10,
        "comment": "Contains, as a percentage of total available memory that contains free pages and reclaimable pages, "
                   "the number of pages at which the background kernel flusher threads will start writing out "
                   "dirty data asynchronously.",

    },
    "vm.dirty_ratio": {
        "instructions": {
            "mall_default": 60,
            "bigt_default": 70,
        },
        "default": 30,
        "comment": "Contains, as a percentage of total available memory that contains free pages and reclaimable pages, "
                   "the number of pages at which a process which is generating disk writes will itself start writing "
                   "out dirty data synchronously. The default value is 30",
    },
    "vm.dirty_expire_centisecs": {
        "default": 3000,
        "comment": "The dirty_expire_centisecs tunable is used to define when dirty data is old enough to be eligible "
                   "for writeout by the kernel flusher threads. The default value is 3000 centiseconds (30 seconds)",
    },
    "vm.dirty_writeback_centisecs": {
        "default": 500,
        "comment": "The dirty_writeback_centisecs tunable is used to define the interval at which the kernel flusher "
                   "threads wake up to write out dirty data. The default value is 500 centiseconds (5 seconds)",
    },
    "vm.page_lock_fairness": {
        "default": 5,
        "comment": "This control is used to define the fairness of the page lock. The default value is 5. See [15] for "
                   "more information",
    },
    "vm.overcommit_memory": {
        "default": 0,
        "comment": "This control is used to define the kernel virtual memory accounting mode. The default value is 0. "
                   "See [03] for more information",
    },
    "vm.overcommit_ratio": {
        "default": 50,
        "comment": "This control is used to define the percentage of physical memory that is allowed to be overcommitted. "
                   "The default value is 50. See [03] for more information",
    },
    "vm.nr_hugepages": {
        "default": 0,
        "comment": "This control is used to define the number of hugepages to allocate at boot. The default value is 0. "
                   "See [03] for more information",
    },
    "vm.nr_hugepages_mempolicy": {
        "default": 0,
        "comment": "This control is used to define the hugepage allocation policy. The default value is 0. See [03] for "
                   "more information",
    },
    "vm.nr_overcommit_hugepages": {
        "default": 0,
        "comment": "This control is used to define the number of hugepages to allocate at boot. The default value is 0. "
                   "See [03] for more information",
    },
    "vm.vfs_cache_pressure": {
        "default": 50,
        "comment": "This percentage value controls the tendency of the kernel to reclaim the memory which is used for "
                   "caching of directory and inode objects. At the default value of vfs_cache_pressure=100 the kernel "
                   "will attempt to reclaim dentries and inodes at a fair rate with respect to pagecache and swapcache "
                   "reclaim.  Decreasing vfs_cache_pressure causes the kernel to prefer to retain dentry and "
                   "inode caches. Default to 50",
    },
}

KERNEL_SYSCTL_PROFILE = {
    'fs-00': (PG_SCOPE.FILESYSTEM, _KERNEL_FS_PROFILE, {'hardware_scope': 'disk'}),
    'net-00': (PG_SCOPE.NETWORK, _KERNEL_NETCORE_PROFILE, {'hardware_scope': 'net'}),
    'net-01': (PG_SCOPE.NETWORK, _KERNEL_NETIPV4_PROFILE, {'hardware_scope': 'net'}),
    'vm-00': (PG_SCOPE.VM, _KERNEL_VM_PROFILE, {'hardware_scope': 'cpu'})
}
merge_extra_info_to_profile(KERNEL_SYSCTL_PROFILE)
type_validation(KERNEL_SYSCTL_PROFILE)
