# PostgreSQL: DBA and Tuner (pgtuner_dba)

## Overview

The :project:`pgtuner` (or PostgreSQL: Tuner as DBA) is a SQL/Python-based project designed to manage and optimize kernel parameters and database settings, focusing on TCP networking on kernel (connection management, retries, timeouts, and **buffering**), and database utilization (memory, disk, integrity); bringing the highest performance with stability, data integrity, and concurrency from various system configurations. The tuning is inspired by many successful world-wide clusters (Notion, Cloudflare, ...) from OS part, many DBA experts at PostgreSQL community (Azure, OnGres, PostgresPro, PostgreSQL core developers, real-world use cases, ...) and my own experience. 

You can experience our on-demand tool under the URL https://pgtuner.onrender.com, or clone our repository and run it on your local machine (follow the instruction below). 

## How tuning works?

The tuning works by analyzing your provided workload model, its sizing, hardware specification (CPU, RAM, Disk, ...), and apply corresponding tuning profiles to optimize them. The tuning consists of two phases: general tuning and correction tuning. The first phase is to directly apply the generic tuning guidelines (usually from the Internet) with some simple adjustments based on your simplest provided configuration into the pool of consideration. The second phase if the fine-tuning process, aiming to delegate and honor your specific requirements, such as workload type, disk sizing, some user-defined configuration, free tuning headroom, risk level, etc. However, not everything can be covered as the database requirements can be changed over time, storage capacity, business changes, hardware degradation; and especially, the tuning is not a silver bullet.

## DISCLAIMER

The tuning is not a silver bullet, and it is not guaranteed to work for all systems. The tuning is based on several tuning profiles and guidelines found on Internet with experiences. Also, it is not bulletproof against all possible scenarios such as business requirements change, non-proper database management, and other factors. It is recommended to test the tuning on a staging environment before applying it to the production environment. 

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

## Build and Test on Local

Build your Docker container in Dockerfile; or create a virtual environment with Python 3.12 and install the dependencies from `requirements.*.txt`. The project is tested on Python 3.12+, but you can free to run at Python 3.11 on local machine. Its web interface is run on the port 8001 by default, but it can be changed by the environment variable `PORT` in the environment file `web.*.env`.

If you decide to work on its backend only, install the `requirements.bump.cli.txt`. If you attempt to improve the frontend server hosting, then install the `requirements.bump.web.txt`. For full development, including the UI change, install both the `requirements.bump.web.txt` and `requirements.html.txt` (for HTML/CSS/JS minification).

## Upcoming Features

Probably in the future, we want to write a full Javascript tuning to host as the static webpages, to provide an easy-to-go tuning guideline for the users around the world. But some difficulties:
- Lambda function with caching during general tuning and correction tuning
- Input validation (not the biggest obstacle) and error handling
- Insertion-ordered dictionary (from Python 3.7+)
- Numeric formating and f-string
- Type-hint for future development

