# PostgreSQL: DBA and Tuner (pgtuner_dba)

## Overview

The :project:`pgtuner_dba` (or PostgreSQL: DBA & Tuner) is a SQL/Python-based project designed to manage and optimize kernel parameters and database settings, focusing on TCP networking (connection management, retries, timeouts, and **buffering**) and memory/VM management (swappiness, dirty ratios, over-commit memory, hugepages, and cache pressure); whilst maintaining high performance, stability, security, and concurrency for various system configurations. The tuning is inspired by many successful world-wide clusters (Notion, Cloudflare, ...) from OS part, and many DBA's experts at PostgreSQL community. This project is a combination of those experiences and designed to be a structured approach for various profiles and settings (easily customizable and extendable). The project also contains a bunch of SQL and Python scripts that can be used to manage a PostgreSQL database under my experience.

## How tuning works?

The tuning works by analyzing the current system sizing using the `psutil` library or taking user input (for sampling) to get the current system configuration (such as CPU, Memory, *). Then the tuning would estimate the sub-category of the tuning variables and map it with several (5) pre-defined profiles in the project (mini, medium, large, mall, bigt, ...), and apply the general tuning guidelines, which is the first-phase of the tuning process. The second phase is the fine-tuning or specific tuning (or correction), in which some variables would be adjusted based on the user tuning options and keywords such as the database workload (PG_WORKLOAD), disk strength (PG_DISK_PERF), optimization risk (PG_PROFILE_OPTMODE), user customization keywords (PG_TUNE_USR_KWARGS). However, not everything can be covered as the  database requirements can be changed over time, network reliability (latency, cross-region DR), storage capacity. 

The reason for two-phase tuning is to ensure that the system is optimized for both the system and the workload. For example, the LOG workload (insert only) have same complexity of the SOLTP (Simple-OLTP) workload, thus they could share some similar tuning strategy. Meanwhile, the OLAP workload, Data Lake, and Data Warehouse usually involved full table analytics, thus they could share similar tuning strategies. 

## DISCLAIMER

The tuning is not a silver bullet, and it is not guaranteed to work for all systems. The tuning is based on several tuning profiles and guidelines found on Internet with experiences. Also,it is not bulletproof against all possible scenarios such as business requirements change, non-proper database management, and other factors. It is recommended to test the tuning on a staging environment before applying it to the production environment. 

## Features

- **TCP Networking Tuning**: Adjusts parameters such as SYN/ACK retries, FIN timeout, keepalive intervals, and more.
- **Memory/VM Management**: Configures settings like swappiness, dirty ratios, over-commit memory, hugepages, and cache pressure for kernel optimization. Optimize memory usage for PostgreSQL with sub-optimal memory for management and other services.
- **Customizable Profiles with Instruction Overrides**: Allows for different tuning profiles (e.g., mini, medium) to suit various system requirements, with the ability to override specific instructions and variable safeguard. 
- **Structured Approach**: Provides a well-documented and structured approach to kernel and database tuning, making it easier to understand and maintain.


## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

## Unresolved Issues

- [ ] Detailed object tuning profile (some are not covered due to overlapping functionality or not yet implemented)
- [ ] More detailed documentation and examples

## Bump to New Dependency

1. Cleanup the old dependencies by backup the current pip and remove venv: `pip freeze > requirements_bkp.txt` and `deactivate` and `rm -rf .venv`
2. Create a new venv: `python3 -m venv .venv` and `source .venv/bin/activate`
3. Install the new dependencies. These are the list of primary packages to update
4. `
*These listed version are the current one, please check the latest version on PyPI*

For internal usage
pydantic~=2.9.2
rich~=13.9.4
toml~=0.10.2

For Web/RestAPI, we can use
fastapi[standard] orjson uvicorn httptools
python-multipart itsdangerous jinja2
uvloop  # Not available on Windows

`
5. Test the application and freeze the new dependencies: `pip freeze  > requirements.txt`

