
// ==================================================================================
/**
 * Original Source File: ./src/tuner/pg_dataclass.py
 */
class PG_TUNE_REQUEST {
    constructor(options) {
        this.options = options.options;
        this.include_comment = options.include_comment ?? false;
        this.custom_style = options.custom_style ?? false;
        this.backup_settings = options.backup_settings ?? true;
        this.analyze_with_full_connection_use = options.analyze_with_full_connection_use ?? true;
        this.ignore_non_performance_setting = options.ignore_non_performance_setting ?? false;
        this.output_format = options.output_format ?? 'file';
    }
}

// This section is managed by the application
class PG_TUNE_RESPONSE {
    constructor() {
        this.outcome = { }
        this.outcome_cache = { }
        this.outcome[PGTUNER_SCOPE.DATABASE_CONFIG] = {};
        this.outcome_cache[PGTUNER_SCOPE.DATABASE_CONFIG] = {};
    }

    get_managed_items(target, scope) {
        if (!this.outcome.hasOwnProperty(target)) {
            this.outcome[target] = {};
        }
        if (!this.outcome[target].hasOwnProperty(scope)) {
            this.outcome[target][scope] = {};
        }

        return this.outcome[target][scope];
    }

    get_managed_cache(target) {
        if (!this.outcome_cache.hasOwnProperty(target)) {
            this.outcome_cache[target] = {};
        }
        return this.outcome_cache[target];
    }

    _file_config(target, request, exclude_names = null) {
        let content = [target.disclaimer(), '\n'];
        if (request.backup_settings === true) {
            content.push(`# User Options: ${JSON.stringify(request.options)}\n`);
        }
        let custom_style = !request.custom_style ? null : 'ALTER SYSTEM SET $1 = $2;';
        for (const [scope, items] of Object.entries(this.outcome[target])) {
            content.push(`## ===== SCOPE: ${scope} ===== \n`);
            for (const [item_name, item] of Object.entries(items)) {
                if (exclude_names === null || !exclude_names.has(item_name)) {
                    content.push(item.out(request.include_comment, custom_style));
                    content.push(request.include_comment ? '\n\n' : '\n');
                }
            }
            content.push(request.include_comment ? '\n\n' : '\n');
        }
        return content.join('');
    }

    _response_config(target, request, exclude_names = null) {
        let content = {};
        for (const [_, items] of Object.entries(this.outcome[target])) {
            for (const [item_name, item] of Object.entries(items)) {
                if (exclude_names === null || !exclude_names.has(item_name)) {
                    content[item_name] = item.out_display(null);
                }
            }
        }
        if (request.output_format === 'conf') {
            return Object.entries(content).map(([k, v]) => `${k} = ${v}`).join('\n');
        }
        return content;
    }

    generate_content(target, request, exclude_names = null) {
        if (exclude_names !== null && Array.isArray(exclude_names)) {
            exclude_names = new Set(exclude_names);
        }
        if (request.output_format === 'file') {
            return this._file_config(target, request, exclude_names);
        } else if (['json', 'conf'].includes(request.output_format)) {
            return this._response_config(target, request, exclude_names);
        } else {
            throw new Error(`Invalid output format: ${request.output_format}. Expected one of "json", "conf", "file".`);
        }
    }

    report(options, use_full_connection = false, ignore_report = true) {
        // Cache result first
        const _kwargs = options.tuning_kwargs;
        const usable_ram_noswap = options.usable_ram;
        const usable_ram_noswap_hr = bytesize_to_hr(usable_ram_noswap);
        const total_ram = options.total_ram;
        const total_ram_hr = bytesize_to_hr(total_ram);
        const usable_ram_noswap_ratio = usable_ram_noswap / total_ram;
        const managed_cache = this.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG);

        // Number of Connections
        const max_user_conns = (managed_cache['max_connections'] - managed_cache['superuser_reserved_connections'] - managed_cache['reserved_connections']);
        const os_conn_overhead = (max_user_conns * _kwargs.single_memory_connection_overhead * _kwargs.memory_connection_to_dedicated_os_ratio);
        let num_user_conns = max_user_conns;
        if (!use_full_connection) {
            num_user_conns = Math.ceil(max_user_conns * _kwargs.effective_connection_ratio);
        }

        // Shared Buffers and WAL buffers
        const shared_buffers = managed_cache['shared_buffers'];
        const wal_buffers = managed_cache['wal_buffers'];

        // Temp Buffers and Work Mem
        const temp_buffers = managed_cache['temp_buffers'];
        const work_mem = managed_cache['work_mem'];
        const hash_mem_multiplier = managed_cache['hash_mem_multiplier'];

        // Higher level would assume more hash-based operations, which reduce the work_mem in correction-tuning phase
        // Smaller level would assume less hash-based operations, which increase the work_mem in correction-tuning phase
        // real_world_work_mem = work_mem * hash_mem_multiplier
        const real_world_mem_scale = generalized_mean([1, hash_mem_multiplier], _kwargs.hash_mem_usage_level);
        const real_world_work_mem = work_mem * real_world_mem_scale;
        const total_working_memory = (temp_buffers + real_world_work_mem);
        const total_working_memory_hr = bytesize_to_hr(total_working_memory);

        let max_total_memory_used = shared_buffers + wal_buffers + os_conn_overhead;
        max_total_memory_used += total_working_memory * num_user_conns;
        const max_total_memory_used_ratio = max_total_memory_used / usable_ram_noswap;
        const max_total_memory_used_hr = bytesize_to_hr(max_total_memory_used);

        if (ignore_report && !_kwargs.mem_pool_parallel_estimate) {
            return ['', max_total_memory_used];
        }

        // Work Mem but in Parallel
        const _parallel_report = this.calc_worker_in_parallel(options, num_user_conns);
        const num_parallel_workers = _parallel_report['num_parallel_workers'];
        const num_sessions = _parallel_report['num_sessions'];
        const num_sessions_in_parallel = _parallel_report['num_sessions_in_parallel'];
        const num_sessions_not_in_parallel = _parallel_report['num_sessions_not_in_parallel'];

        const parallel_work_mem_total = real_world_work_mem * (num_parallel_workers + num_sessions_in_parallel);
        const parallel_work_mem_in_session = real_world_work_mem * (1 + managed_cache['max_parallel_workers_per_gather']);

        // Ensure the number of active user connections always larger than the num_sessions
        // The maximum 0 here is meant that all connections can have full parallelism
        const single_work_mem_total = real_world_work_mem * num_sessions_not_in_parallel;
        let max_total_memory_used_with_parallel = shared_buffers + wal_buffers + os_conn_overhead;
        max_total_memory_used_with_parallel += (parallel_work_mem_total + single_work_mem_total);
        max_total_memory_used_with_parallel += temp_buffers * num_user_conns;
        const max_total_memory_used_with_parallel_ratio = max_total_memory_used_with_parallel / usable_ram_noswap;
        const max_total_memory_used_with_parallel_hr = bytesize_to_hr(max_total_memory_used_with_parallel);

        if (ignore_report && _kwargs.mem_pool_parallel_estimate) {
            return ['', max_total_memory_used_with_parallel];
        }

        // Effective Cache Size
        const effective_cache_size = managed_cache['effective_cache_size'];

        // WAL Times
        const wal_throughput = options.wal_spec.perf()[0];
        const wal_writer_delay = managed_cache['wal_writer_delay']
        const wal05 = wal_time(wal_buffers, 0.5, _kwargs.wal_segment_size, wal_writer_delay,
            wal_throughput, options, managed_cache['wal_init_zero']);
        const wal10 = wal_time(wal_buffers, 1.0, _kwargs.wal_segment_size, wal_writer_delay,
            wal_throughput, options, managed_cache['wal_init_zero']);
        const wal15 = wal_time(wal_buffers, 1.5, _kwargs.wal_segment_size, wal_writer_delay,
            wal_throughput, options, managed_cache['wal_init_zero']);
        const wal20 = wal_time(wal_buffers, 2.0, _kwargs.wal_segment_size, wal_writer_delay,
            wal_throughput, options, managed_cache['wal_init_zero']);

        // Vacuum and Maintenance
        let real_autovacuum_work_mem = managed_cache['autovacuum_work_mem'];
        if (real_autovacuum_work_mem === -1) {
            real_autovacuum_work_mem = managed_cache['maintenance_work_mem'];
        }
        if (options.pgsql_version < 17) {
            // The VACUUM use adaptive radix tree which performs better and not being silently capped at 1 GiB
            // since PostgreSQL 17+
            // https://www.postgresql.org/docs/17/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM
            // and https://www.postgresql.org/docs/16/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM
            real_autovacuum_work_mem = Math.min(1 * Gi, real_autovacuum_work_mem);
        }

        // Checkpoint Timing
        const [data_tput, data_iops] = options.data_index_spec.perf()
        const checkpoint_timeout = managed_cache['checkpoint_timeout'];
        const checkpoint_completion_target = managed_cache['checkpoint_completion_target'];
        const _ckpt_iops = PG_DISK_PERF.throughput_to_iops(0.70 * generalized_mean([PG_DISK_PERF.iops_to_throughput(data_iops), data_tput], -2.5));   // The merge between sequential IOPS and random IOPS with weighted average of -2.5 and 70% efficiency
        const ckpt05 = checkpoint_time(checkpoint_timeout, checkpoint_completion_target, shared_buffers, 0.05, effective_cache_size, managed_cache['max_wal_size'], _ckpt_iops);
        const ckpt30 = checkpoint_time(checkpoint_timeout, checkpoint_completion_target, shared_buffers, 0.30, effective_cache_size, managed_cache['max_wal_size'], _ckpt_iops);
        const ckpt95 = checkpoint_time(checkpoint_timeout, checkpoint_completion_target, shared_buffers, 0.95, effective_cache_size, managed_cache['max_wal_size'], _ckpt_iops);

        // Background Writers
        const bgwriter_page_per_second = Math.ceil(managed_cache['bgwriter_lru_maxpages'] * (K10 / managed_cache['bgwriter_delay']));
        const bgwriter_throughput = PG_DISK_PERF.iops_to_throughput(bgwriter_page_per_second);

        // Auto-vacuum and Maintenance
        const vacuum_report = vacuum_time(managed_cache['vacuum_cost_page_hit'], managed_cache['vacuum_cost_page_miss'], managed_cache['vacuum_cost_page_dirty'], managed_cache['autovacuum_vacuum_cost_delay'], managed_cache['vacuum_cost_limit'], data_iops);
        const normal_vacuum = vacuum_scale(managed_cache['autovacuum_vacuum_threshold'], managed_cache['autovacuum_vacuum_scale_factor']);
        const normal_analyze = vacuum_scale(managed_cache['autovacuum_analyze_threshold'], managed_cache['autovacuum_analyze_scale_factor']);
        // See the PostgreSQL source code of how they sample randomly to get statistics
        const _sampling_rows = 300 * managed_cache['default_statistics_target'];

        // Anti-wraparound Vacuum
        // Transaction ID
        const num_hourly_write_transaction = options.num_write_transaction_per_hour_on_workload;
        const min_hr_txid = managed_cache['vacuum_freeze_min_age'] / num_hourly_write_transaction;
        const norm_hr_txid = managed_cache['vacuum_freeze_table_age'] / num_hourly_write_transaction;
        const max_hr_txid = managed_cache['autovacuum_freeze_max_age'] / num_hourly_write_transaction;

        // Row Locking in Transaction
        const min_hr_row_lock = managed_cache['vacuum_multixact_freeze_min_age'] / num_hourly_write_transaction;
        const norm_hr_row_lock = managed_cache['vacuum_multixact_freeze_table_age'] / num_hourly_write_transaction;
        const max_hr_row_lock = managed_cache['autovacuum_multixact_freeze_max_age'] / num_hourly_write_transaction;

        // Report
        const _report = `
# ===============================================================        
# Memory Estimation Test by ${APP_NAME_UPPER}
From server-side, the PostgreSQL memory usable arena is at most ${usable_ram_noswap_hr} or ${(usable_ram_noswap_ratio * 100).toFixed(2)} (%) of the total RAM (${total_ram_hr}).
    All other variables must be bounded and computed within the available memory.
    CPU: ${options.vcpu} logical cores
RAM: ${total_ram_hr} or ratio: ${((total_ram / options.vcpu / Gi).toFixed(1))}.

Arguments: use_full_connection=${use_full_connection}
Report Summary (memory, over usable RAM):
----------------------------------------
* PostgreSQL memory (estimate): ${max_total_memory_used_hr} or ${(max_total_memory_used_ratio * 100).toFixed(2)} (%) over usable RAM.
    - The Shared Buffers is ${bytesize_to_hr(shared_buffers)} or ${(shared_buffers / usable_ram_noswap * 100).toFixed(2)} (%)
    - The Wal Buffers is ${bytesize_to_hr(wal_buffers)} or ${(wal_buffers / usable_ram_noswap * 100).toFixed(2)} (%)
    - The connection overhead is ${bytesize_to_hr(os_conn_overhead)} with ${num_user_conns} total user connections
        + Active user connections: ${max_user_conns}
        + Peak assumption is at ${bytesize_to_hr(os_conn_overhead / _kwargs.memory_connection_to_dedicated_os_ratio)}
        + Reserved & Superuser Reserved Connections: ${managed_cache['max_connections'] - max_user_conns}
        + Need Connection Pool such as PgBouncer: ${num_user_conns >= 100}
    - The total maximum working memory (assuming with one full use of work_mem and temp_buffers):
        + SINGLE: ${total_working_memory_hr} per user connections or ${(total_working_memory / usable_ram_noswap * 100).toFixed(2)} (%)
            -> Real-World Mem Scale: ${(_kwargs.temp_buffers_ratio + (1 - _kwargs.temp_buffers_ratio) * real_world_mem_scale).toFixed(2)}
            -> Temp Buffers: ${bytesize_to_hr(temp_buffers)} :: Work Mem: ${bytesize_to_hr(work_mem)}
            -> Hash Mem Multiplier: ${hash_mem_multiplier} ::  Real-World Work Mem: ${bytesize_to_hr(real_world_work_mem)}
            -> Total: ${(total_working_memory * num_user_conns / usable_ram_noswap * 100).toFixed(2)} (%)
        + PARALLEL:
            -> Workers :: Gather Workers=${managed_cache['max_parallel_workers_per_gather']} :: Worker in Pool=${managed_cache['max_parallel_workers']} << Workers Process=${managed_cache['max_worker_processes']}
            -> Parallelized Session: ${num_sessions_in_parallel} :: Non-parallelized Session: ${num_sessions_not_in_parallel}
            -> Work memory assuming single query (1x work_mem)
                * Total parallelized sessions = ${num_sessions} with ${num_sessions_in_parallel - num_sessions} leftover session
                * Maximum work memory in parallelized session(s) without temp_buffers :
                    - 1 parallelized session: ${bytesize_to_hr(parallel_work_mem_in_session)} or ${(parallel_work_mem_in_session / usable_ram_noswap * 100).toFixed(2)} (%)
                    - Total (in parallel): ${bytesize_to_hr(parallel_work_mem_total)} or ${(parallel_work_mem_total / usable_ram_noswap * 100).toFixed(2)} (%)
                    - Total (in single): ${bytesize_to_hr(single_work_mem_total)} or ${(single_work_mem_total / usable_ram_noswap * 100).toFixed(2)} (%)
                * Maximum work memory in parallelized session(s) with temp_buffers:
                    - 1 parallelized session: ${bytesize_to_hr(parallel_work_mem_in_session + temp_buffers)} or ${((parallel_work_mem_in_session + temp_buffers) / usable_ram_noswap * 100).toFixed(2)} (%)
                    - Total (in parallel): ${bytesize_to_hr(parallel_work_mem_total + temp_buffers * num_user_conns)} or ${((parallel_work_mem_total + temp_buffers * num_user_conns) / usable_ram_noswap * 100).toFixed(2)} (%)
                    - Total (in single): ${bytesize_to_hr(single_work_mem_total + temp_buffers * num_user_conns)} or ${((single_work_mem_total + temp_buffers * num_user_conns) / usable_ram_noswap * 100).toFixed(2)} (%)
    - Effective Cache Size: ${bytesize_to_hr(effective_cache_size)} or ${(effective_cache_size / usable_ram_noswap * 100).toFixed(2)} (%)

* Zero parallelized session >> Memory in use: ${max_total_memory_used_hr}
    - Memory Ratio: ${(max_total_memory_used_ratio * 100).toFixed(2)} (%)
    - Normal Memory Usage: ${max_total_memory_used_ratio <= Math.min(1.0, _kwargs.max_normal_memory_usage)} (${(_kwargs.max_normal_memory_usage * 100).toFixed(1)} % memory threshold)
    - P3: Generally Safe in Workload: ${max_total_memory_used_ratio <= 0.70} (70 % memory threshold)
    - P2: Sufficiently Safe for Production: ${max_total_memory_used_ratio <= 0.80} (80 % memory threshold)
    - P1: Risky for Production: ${max_total_memory_used_ratio <= 0.90} (90 % memory threshold)
* With parallelized session >> Memory in use: ${max_total_memory_used_with_parallel_hr}
    - Memory Ratio: ${(max_total_memory_used_with_parallel_ratio * 100).toFixed(2)} (%)
    - Normal Memory Usage: ${max_total_memory_used_with_parallel_ratio <= Math.min(1.0, _kwargs.max_normal_memory_usage)} (${(_kwargs.max_normal_memory_usage * 100).toFixed(1)} % memory threshold)
    - P3: Generally Safe in Workload: ${max_total_memory_used_with_parallel_ratio <= 0.70} (70 % memory threshold)
    - P2: Sufficiently Safe for Production: ${max_total_memory_used_with_parallel_ratio <= 0.80} (80 % memory threshold)
    - P1: Risky for Production: ${max_total_memory_used_with_parallel_ratio <= 0.90} (90 % memory threshold)

Report Summary (others):
-----------------------  
* Maintenance and (Auto-)Vacuum:
    - Autovacuum (by definition): ${managed_cache['autovacuum_work_mem']}
        + Working memory per worker: ${bytesize_to_hr(real_autovacuum_work_mem)}
        + Max Workers: ${managed_cache['autovacuum_max_workers']} --> Total Memory: ${bytesize_to_hr(real_autovacuum_work_mem * managed_cache['autovacuum_max_workers'])} or ${(real_autovacuum_work_mem * managed_cache['autovacuum_max_workers'] / usable_ram_noswap * 100).toFixed(2)} (%)
    - Maintenance:
        + Max Workers: ${managed_cache['max_parallel_maintenance_workers']}
        + Total Memory: ${bytesize_to_hr(managed_cache['maintenance_work_mem'] * managed_cache['max_parallel_maintenance_workers'])} or ${(managed_cache['maintenance_work_mem'] * managed_cache['max_parallel_maintenance_workers'] / usable_ram_noswap * 100).toFixed(2)} (%)
        + Parallel table scan size: ${bytesize_to_hr(managed_cache['min_parallel_table_scan_size'])}
        + Parallel index scan size: ${bytesize_to_hr(managed_cache['min_parallel_index_scan_size'])}
    - Autovacuum Trigger (table-level):
        + Vacuum  :: Scale Factor=${(managed_cache['autovacuum_vacuum_scale_factor'] * 100).toFixed(2)} (%) :: Threshold=${managed_cache['autovacuum_vacuum_threshold']}
        + Analyze :: Scale Factor=${(managed_cache['autovacuum_analyze_scale_factor'] * 100).toFixed(2)} (%) :: Threshold=${managed_cache['autovacuum_analyze_threshold']}
        + Insert  :: Scale Factor=${(managed_cache['autovacuum_vacuum_insert_scale_factor'] * 100).toFixed(2)} (%) :: Threshold=${managed_cache['autovacuum_vacuum_insert_threshold']}
        Report when number of dead tuples is reached:
        + 10K rows :: Vacuum=${normal_vacuum['10k']} :: Insert/Analyze=${normal_analyze['10k']}
        + 300K rows :: Vacuum=${normal_vacuum['300k']} :: Insert/Analyze=${normal_analyze['300k']}
        + 10M rows :: Vacuum=${normal_vacuum['10m']} :: Insert/Analyze=${normal_analyze['10m']}
        + 100M rows :: Vacuum=${normal_vacuum['100m']} :: Insert/Analyze=${normal_analyze['100m']}
        + 1B rows :: Vacuum=${normal_vacuum['1b']} :: Insert/Analyze=${normal_analyze['1b']}
    - Cost-based Vacuum:  
        + Page Cost Relative Factor :: Hit=${managed_cache['vacuum_cost_page_hit']} :: Miss=${managed_cache['vacuum_cost_page_miss']} :: Dirty/Disk=${managed_cache['vacuum_cost_page_dirty']}
        + Autovacuum cost: ${managed_cache['autovacuum_vacuum_cost_limit']} --> Vacuum cost: ${managed_cache['vacuum_cost_limit']}
        + Autovacuum delay: ${managed_cache['autovacuum_vacuum_cost_delay']} (ms) --> Vacuum delay: ${managed_cache['vacuum_cost_delay']} (ms)
        + IOPS Spent: ${(data_iops * _kwargs.autovacuum_utilization_ratio).toFixed(1)} pages or ${PG_DISK_PERF.iops_to_throughput((data_iops * _kwargs.autovacuum_utilization_ratio).toFixed(1))} MiB/s
        + Vacuum Report on Worst Case Scenario:
            We safeguard against WRITE since most READ in production usually came from RAM/cache before auto-vacuuming, but not safeguard against pure, zero disk read.
            -> Hit (page in shared_buffers): Maximum ${vacuum_report['max_num_hit_page']} pages or RAM throughput ${(vacuum_report['max_hit_data']).toFixed(2)} MiB/s
                RAM Safety: ${vacuum_report['max_hit_data'] < 10 * K10} (< 10 GiB/s for low DDR3)
            -> Miss (page in disk cache): Maximum ${vacuum_report['max_num_miss_page']} pages or Disk throughput ${(vacuum_report['max_miss_data']).toFixed(2)} MiB/s
                # See encoding here: https://en.wikipedia.org/wiki/64b/66b_encoding; NVME SSD with PCIe 3.0+ or USB 3.1
                NVME10 Safety: ${vacuum_report['max_miss_data'] < 10 / 8 * 64 / 66 * K10} (< 10 GiB/s, 64b/66b encoding)
                SATA3 Safety: ${vacuum_report['max_miss_data'] < 6 / 8 * 6 / 8 * K10} (< 6 GiB/s, 6b/8b encoding)
                Disk Safety: ${vacuum_report['max_num_miss_page'] < data_iops} (< Data Disk IOPS)
            -> Dirty (page in data disk volume): Maximum ${vacuum_report['max_num_dirty_page']} pages or Disk throughput ${(vacuum_report['max_dirty_data']).toFixed(2)} MiB/s
                Disk Safety: ${vacuum_report['max_num_dirty_page'] < data_iops} (< Data Disk IOPS)
        + Other Scenarios with H:M:D ratio as 5:5:1 (frequent), or 1:1:1 (rarely)
            5:5:1 or ${vacuum_report['5:5:1_page'] * 6} disk pages -> IOPS capacity of ${(vacuum_report['5:5:1_data']).toFixed(2)} MiB/s (write=${(vacuum_report['5:5:1_data'] * 1 / 6).toFixed(2)} MiB/s)
            -> Safe: ${vacuum_report['5:5:1_page'] * 6 < data_iops} (< Data Disk IOPS)
            1:1:1 or ${vacuum_report['1:1:1_page'] * 3} disk pages -> IOPS capacity of ${(vacuum_report['1:1:1_data']).toFixed(2)} MiB/s (write=${(vacuum_report['1:1:1_data'] * 1 / 2).toFixed(2)} MiB/s)
            -> Safe: ${vacuum_report['1:1:1_page'] * 3 < data_iops} (< Data Disk IOPS)
    - Transaction (Tran) ID Wraparound and Anti-Wraparound Vacuum:
        + Workload Write Transaction per Hour: ${num_hourly_write_transaction}
        + TXID Vacuum :: Minimum=${min_hr_txid.toFixed(2)} hrs :: Manual=${norm_hr_txid.toFixed(2)} hrs :: Auto-forced=${max_hr_txid.toFixed(2)} hrs
        + XMIN,XMAX Vacuum :: Minimum=${min_hr_row_lock.toFixed(2)} hrs :: Manual=${norm_hr_row_lock.toFixed(2)} hrs :: Auto-forced=${max_hr_row_lock.toFixed(2)} hrs

* Background Writers:
    - Delay: ${managed_cache['bgwriter_delay']} (ms) for maximum ${managed_cache['bgwriter_lru_maxpages']} dirty pages
        + ${bgwriter_page_per_second} pages per second or ${bgwriter_throughput.toFixed(1)} MiB/s in random WRITE IOPs

* Checkpoint:        
    - Effective Timeout: ${(checkpoint_timeout * checkpoint_completion_target).toFixed(1)} seconds (${checkpoint_timeout}::${checkpoint_completion_target})
    - Checkpoint timing analysis at 70% random IOPS:
        + 5% of shared_buffers:
            -> Data Amount: ${bytesize_to_hr(ckpt05['data_amount'])} :: ${ckpt05['page_amount']} pages
            -> Expected Time: ${ckpt05['data_write_time']} seconds with ${ckpt05['data_disk_utilization'] * 100} (%) utilization
            -> Safe Test :: Time-based Check <- ${ckpt05['data_write_time'] <= checkpoint_timeout * checkpoint_completion_target}
        + 30% of shared_buffers:
            -> Data Amount: ${bytesize_to_hr(ckpt30['data_amount'])} :: ${ckpt30['page_amount']} pages
            -> Expected Time: ${ckpt30['data_write_time']} seconds with ${ckpt30['data_disk_utilization'] * 100} (%) utilization
            -> Safe Test :: Time-based Check <- ${ckpt30['data_write_time'] <= checkpoint_timeout * checkpoint_completion_target}
        + 95% of shared_buffers:
            -> Data Amount: ${bytesize_to_hr(ckpt95['data_amount'])} :: ${ckpt95['page_amount']} pages
            -> Expected Time: ${ckpt95['data_write_time']} seconds with ${ckpt95['data_disk_utilization'] * 100} (%) utilization
            -> Safe Test :: Time-based Check <- ${ckpt95['data_write_time'] <= checkpoint_timeout * checkpoint_completion_target}
            
* Query Planning and Optimization:
    - Page Cost :: Sequential=${managed_cache['seq_page_cost'].toFixed(2)} :: Random=${managed_cache['random_page_cost'].toFixed(2)}
    - CPU Cost :: Tuple=${managed_cache['cpu_tuple_cost'].toFixed(4)} :: Index=${managed_cache['cpu_index_tuple_cost'].toFixed(4)} :: Operator=${managed_cache['cpu_operator_cost'].toFixed(4)}
    - Bitmap Heap Planning :: Workload=${managed_cache['effective_io_concurrency']} :: Maintenance=${managed_cache['maintenance_io_concurrency']}
    - Parallelism :: Setup=${managed_cache['parallel_setup_cost']} :: Tuple=${managed_cache['parallel_tuple_cost'].toFixed(2)}
    - Batched Commit Delay: ${managed_cache['commit_delay']} (ms)
    
* Write-Ahead Logging and Data Integrity:
    - WAL Level: ${managed_cache['wal_level']} :: Compression: ${managed_cache['wal_compression']}
    - Single WAL File Size (1 file): ${bytesize_to_hr(_kwargs.wal_segment_size)}
    - Integrity:
        + Synchronous Commit: ${managed_cache['synchronous_commit']}
        + Full Page Writes: ${managed_cache['full_page_writes']}
        + Fsync: ${managed_cache['fsync']}
    - Buffers Write Cycle within Data Loss Time: ${options.max_time_transaction_loss_allow_in_millisecond} ms (depend on WAL volume throughput)
        WAL Buffers: ${bytesize_to_hr(wal_buffers)} or ${(wal_buffers / usable_ram_noswap * 100).toFixed(2)} (%)
        + 0.5x when opt_wal_buffers=${PG_PROFILE_OPTMODE.NONE}:
            -> Elapsed Time :: Rotate: ${wal05['rotate_time'].toFixed(2)} ms :: Write: ${wal05['write_time'].toFixed(2)} ms :: Delay: ${wal05['delay_time'].toFixed(2)} ms
            -> Total Time :: ${wal05['total_time'].toFixed(2)} ms during ${wal05['num_wal_files']} WAL files
            -> Status (O at Best/Avg/Worst): ${wal05['total_time'] <= wal_writer_delay}/${wal05['total_time'] <= wal_writer_delay * 2}/${wal05['total_time'] <= wal_writer_delay * 3}
        + 1.0x when opt_wal_buffers=${PG_PROFILE_OPTMODE.SPIDEY}:
            -> Elapsed Time :: Rotate: ${wal10['rotate_time'].toFixed(2)} ms :: Write: ${wal10['write_time'].toFixed(2)} ms :: Delay: ${wal10['delay_time'].toFixed(2)} ms
            -> Total Time :: ${wal10['total_time'].toFixed(2)} ms during ${wal10['num_wal_files']} WAL files
            -> Status (O at Best/Avg/Worst): ${wal10['total_time'] <= wal_writer_delay}/${wal10['total_time'] <= wal_writer_delay * 2}/${wal10['total_time'] <= wal_writer_delay * 3}
        + 1.5x when opt_wal_buffers=${PG_PROFILE_OPTMODE.OPTIMUS_PRIME}:
            -> Elapsed Time :: Rotate: ${wal15['rotate_time'].toFixed(2)} ms :: Write: ${wal15['write_time'].toFixed(2)} ms :: Delay: ${wal15['delay_time'].toFixed(2)} ms
            -> Total Time :: ${wal15['total_time'].toFixed(2)} ms during ${wal15['num_wal_files']} WAL files
            -> Status (O at Best/Avg/Worst): ${wal15['total_time'] <= wal_writer_delay}/${wal15['total_time'] <= wal_writer_delay * 2}/${wal15['total_time'] <= wal_writer_delay * 3}
        + 2.0x when opt_wal_buffers=${PG_PROFILE_OPTMODE.PRIMORDIAL}:
            -> Elapsed Time :: Rotate: ${wal20['rotate_time'].toFixed(2)} ms :: Write: ${wal20['write_time'].toFixed(2)} ms :: Delay: ${wal20['delay_time'].toFixed(2)} ms
            -> Total Time :: ${wal20['total_time'].toFixed(2)} ms during ${wal20['num_wal_files']} WAL files
            -> Status (O at Best/Avg/Worst): ${wal20['total_time'] <= wal_writer_delay}/${wal20['total_time'] <= wal_writer_delay * 2}/${wal20['total_time'] <= wal_writer_delay * 3}
    - WAL Sizing:  
        + Max WAL Size for Automatic Checkpoint: ${bytesize_to_hr(managed_cache['max_wal_size'])} or ${managed_cache['max_wal_size'] / options.wal_spec.perf()[0]} seconds
        + Min WAL Size for WAL recycle instead of removal: ${bytesize_to_hr(managed_cache['min_wal_size'])}
            -> Disk usage must below ${((1 - managed_cache['min_wal_size'] / options.wal_spec.disk_usable_size) * 100).toFixed(2)} (%)
        + WAL Keep Size for PITR/Replication: ${bytesize_to_hr(managed_cache['wal_keep_size'])} or minimum ${(managed_cache['wal_keep_size'] / options.wal_spec.disk_usable_size * 100).toFixed(2)} (%)
    
* Timeout:
    - Idle-in-Transaction Session Timeout: ${managed_cache['idle_in_transaction_session_timeout']} seconds
    - Statement Timeout: ${managed_cache['statement_timeout']} seconds
    - Lock Timeout: ${managed_cache['lock_timeout']} seconds
        
WARNING (if any) and DISCLAIMER:
------------------------------------------
* These calculations could be incorrect due to capping, precision adjustment, rounding; and it is 
just the estimation. Please take proper consultant and testing to verify the actual memory usage, 
and bottleneck between processes.
* The working memory whilst the most critical part are in the assumption of **basic** full usage 
(one single HASH-based query and one CTE) and all connections are in the same state. It is best 
to test it under your **real** production business workload rather than this estimation report.
* For the autovacuum threshold, it is best to adjust it based on the actual table size, its 
active portion compared to the total size and its time, and the actual update/delete/insert 
rate to avoid bloat rather than using our above setting; but for general use, the current 
default is OK unless you are working on table with billion of rows or more.    
* Update the timeout based on your business requirement, database workload, and the 
application's behavior.
* Not every parameter can be covered or tuned, and not every parameter can be added as-is.
As mentioned, consult with your developer, DBA, and system administrator to ensure the
best performance and reliability of the database system.
# ===============================================================      
        `;
        return [_report, (!_kwargs.mem_pool_parallel_estimate ? max_total_memory_used : max_total_memory_used_with_parallel)];
    }

    calc_worker_in_parallel(options, num_active_user_conns) {
        const managed_cache = this.get_managed_cache(PGTUNER_SCOPE.DATABASE_CONFIG);
        const _kwargs = options.tuning_kwargs;

        // Calculate the number of parallel workers
        const num_parallel_workers = Math.min(managed_cache['max_parallel_workers'], managed_cache['max_worker_processes']);

        // How many sessions can be in parallel
        const remain_workers = num_parallel_workers % managed_cache['max_parallel_workers_per_gather'];

        const num_sessions = Math.floor((num_parallel_workers - remain_workers) / managed_cache['max_parallel_workers_per_gather']);
        const num_sessions_in_parallel = num_sessions + (remain_workers > 0 ? 1 : 0);

        // Ensure the number of active user connections always larger than the num_sessions
        // The maximum 0 here is meant that all connections can have full parallelism
        const num_sessions_not_in_parallel = Math.max(0, num_active_user_conns - num_sessions_in_parallel);

        return {
            'num_parallel_workers': num_parallel_workers,
            'num_sessions': num_sessions,
            'num_sessions_in_parallel': num_sessions_in_parallel,
            'num_sessions_not_in_parallel': num_sessions_not_in_parallel,
            'work_mem_parallel_scale': (num_parallel_workers + num_sessions_in_parallel + num_sessions_not_in_parallel) / num_active_user_conns
        }

    }
}

