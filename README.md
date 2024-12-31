# PostgreSQL: DBA and Tuner (pgtuner_dba)

## Overview

The :project:`pgtuner_dba` (or PostgreSQL: DBA & Tuner) is a SQL/Python-based project designed to manage and optimize 
kernel parameters and database settings, focusing on TCP networking (connection management, retries, timeouts, and 
**buffering**) and memory/VM management (swappiness, dirty ratios, over-commit memory, hugepages, and cache pressure); 
whilst maintaining high performance, stability, security, and concurrency for various system configurations. The tuning 
is inspired by many successful world-wide clusters (Notion, Cloudflare, ...), and designed to be a structured approach 
for various profiles and settings.

The project however did not limit itself into the tuning part only, but contains a set of scripts in SQL and Python 
that can be used on manage a PostgreSQL database under my experience, that would works well on production environments,
and applicable to various configuration that you would not bother to rethink why this or those option(s).

## How tuning works?

The tuning works by analyzing the current system using the library :mod:`psutil` to get the current system configuration 
(such as CPU, Memory, Disk, Network, etc.), but also requesting some user's input to get the right settings. Then the 
tuning would apply the :feat:`backup` feature to backup the current configuration such as :mod:`sysctl` and 
:mod:`postgresql.conf`. 

After the backup, the tuning would use a set of pre-defined profiles in the project (mini, medium, large, mall, bigt, 
...) and apply the general tuning guideline. These guidelines can be easily found in the Internet (but most of them 
are lacking the context and risk management for unmatched system configuration). The first tuning process is just the 
phase one, attempting to optimize the kernel parameters and database settings by its near-constant values.

The second phase is the fine-tuning or specific tuning (or correction), where the tuning would ask the user to input 
the specific values based on their need including different optimization risk levels, and the database workload 
(OLTP, OLAP, ...). Our tuning would corporate the report from the first phase, collected hardware profiles (by the 
library :mod:`psutil`), and the user's input to generate the final configuration.

The result is you can have a customized configuration that is optimized for your system and your workload, and you can
bring those changes to your environment for testing and production.

## Why two-phase tunings?

Two-phase tunings ensure that the system is optimized for both the system and the workload. For example, if a system is 
optimized for OLTP but runs OLAP workload, it won't perform well. Instead of asking users to input workload details 
upfront (which usually not have), the first phase applies general settings suitable for most systems. The second phase 
uses specific knowledge and user input to fine-tune the configuration, ensuring optimal performance for the specific 
workload.

## Features

- **TCP Networking Tuning**: Adjusts parameters such as SYN/ACK retries, FIN timeout, keepalive intervals, and more.
- **Memory/VM Management**: Configures settings like swappiness, dirty ratios, over-commit memory, hugepages, and cache pressure.
- **Customizable Profiles**: Allows for different tuning profiles (e.g., mini, medium) to suit various system requirements.
- **Instruction Overrides**: Supports custom instructions for specific parameters.

## Problem Solved

By using the Kernel Tuner, system administrators and developers can:

- Improve network performance by fine-tuning TCP parameters.
- Optimize memory usage and VM management for better system stability and performance.
- Apply consistent and well-documented kernel settings across multiple systems.

## Codepath

1. **Configuration Definition**: Kernel parameters are defined in dictionaries (`_KERNEL_TCP_PROFILE` and `_KERNEL_VM_PROFILE`), including default values and comments.
2. **Profile Application**: Profiles are applied based on system requirements, with the ability to override specific instructions.
3. **Parameter Adjustment**: The system adjusts kernel parameters according to the selected profile, ensuring optimal performance.

## Usage

To use the Kernel Tuner, follow these steps:

1. **Install the package**:
    ```bash
    pip install kernel-tuner
    ```

2. **Import and configure**:
    ```python
    from kernel_tuner import apply_profile

    # Apply a predefined profile
    apply_profile('medium')
    ```

3. **Customize profiles**:
    Modify the `_KERNEL_TCP_PROFILE` and `_KERNEL_VM_PROFILE` dictionaries to suit your specific needs.

### Supported Value

For the tuning phase, we assumes that the value of the kernel parameters are in the following format:



## Why Use This Package?

- **Ease of Use**: Simple configuration and application of kernel tuning profiles.
- **Flexibility**: Easily customizable to fit various system requirements.
- **Documentation**: Well-documented settings and profiles for better understanding and maintenance.
- **Performance**: Helps achieve optimal system performance through fine-tuned kernel parameters.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.